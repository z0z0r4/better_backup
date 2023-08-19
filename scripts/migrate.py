"""
用于跨版本迁移数据，强烈建议清除数据而非迁移，不保证成功

如非默认，请将 better_backup 数据所在写入 BACKUP_DATA_PATH

并将此文件放于所在 MCDR 的根目录下运行
"""

import os

# from shutil import rmtree
import json
from pydal import DAL, Field
import datetime
import pyzstd

database: DAL = None

ZST_EXT = ".zst"
BACKUP_DATA_PATH = "D:/projects/mcdr/better_backup"

input(f"""
用于跨版本迁移数据，强烈建议清除数据而非迁移，不保证成功\n
如非默认，请将 better_backup 数据所在写入 BACKUP_DATA_PATH\n
并将此文件放于所在 MCDR 的根目录下运行\n
请先备份 {BACKUP_DATA_PATH} 下所有文件，确认后按下任意键
""")

MIGRATE_POLICY = int(
    input(
        """
迁移策略
1. v1.x -> 2.1.x
2. v1.x -> 2.0.x
3. v2.0.x -> 2.1.x
直接输入对应数字
"""
    )
)

if MIGRATE_POLICY in [1, 3]:
    import xxhash

if not MIGRATE_POLICY in range(1, 4):
    raise ValueError


if os.path.exists(BACKUP_DATA_PATH):
    print(f"已找到 {BACKUP_DATA_PATH}")
else:
    print(f"未找到 {BACKUP_DATA_PATH}，请确认better_backup 数据所在")
    exit(1)


def get_file_hash(file_path, range_size: int = 1024 * 128) -> str:
    with open(file_path, "rb") as obj:
        hash = xxhash.xxh3_64()
        while True:
            data = obj.read(range_size)
            if not data:
                break
            hash.update(data)
        return hash.hexdigest()


def decompress_zstd(zst_src: str, dst_file: str):
    if os.path.exists(zst_src):
        with open(zst_src, "rb") as fsrc:
            with open(dst_file, "wb") as fdst:
                pyzstd.decompress_stream(fsrc, fdst)


def load_database():
    global database
    os.makedirs(BACKUP_DATA_PATH, exist_ok=True)
    database = DAL("sqlite://storage.db", folder=BACKUP_DATA_PATH)

    if "files" not in database.tables:
        database.define_table(
            "files",
            Field("backup_uuid"),
            Field("name"),
            Field("hash"),
            Field("hash_type"),
            Field("path"),
        )
    if "backups" not in database.tables:
        database.define_table(
            "backups",
            Field("uuid"),
            Field("time", type="integer"),
            Field("size", type="integer"),
            Field("message"),
        )

    if "count" not in database.tables:
        database.define_table(
            "count", Field("hash"), Field("count", type="integer", default=0)
        )


def get_all_backup_info(metadata_dir: str) -> list:
    all_backup_info = []
    for backup in os.listdir(metadata_dir):
        if (
            not backup == "cache_index.json"
            and os.path.isfile(os.path.join(metadata_dir, backup))
            and backup[-5:] == ".json"
        ):
            backup_path = os.path.join(metadata_dir, backup)
            with open(backup_path, encoding="UTF-8") as f:
                all_backup_info.append(json.load(f))
    return all_backup_info


def scan_backup_info(backup_uuid: str, backup_info: dict, root_path: str = ""):
    for info in backup_info:
        if backup_info[info]["type"] == "file":
            # 策略 1 / 2 的是否处理 xxhash
            if MIGRATE_POLICY == 2:
                database.files.insert(
                    backup_uuid=backup_uuid,
                    name=info,
                    path=root_path,
                    hash=backup_info[info]["md5"],
                    hash_type="md5",
                )
                database(database.count.hash == backup_info[info]["md5"]).update(hash=xxhash_result) # for table count
            elif MIGRATE_POLICY == 1:
                # 转换到 xxhash
                if not os.path.exists(
                    os.path.join(
                        BACKUP_DATA_PATH,
                        "cache",
                        backup_info[info]["md5"][:2],
                        backup_info[info]["md5"][2:],
                    )
                ) and os.path.exists(
                    os.path.join(
                        BACKUP_DATA_PATH,
                        "cache",
                        backup_info[info]["md5"][:2],
                        backup_info[info]["md5"][2:],
                    )
                    + ZST_EXT
                ):
                    decompress_zstd(
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            backup_info[info]["md5"][:2],
                            backup_info[info]["md5"][2:],
                        )
                        + ZST_EXT,
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            backup_info[info]["md5"][:2],
                            backup_info[info]["md5"][2:],
                        ),
                    )
                    xxhash_result = get_file_hash(
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            backup_info[info]["md5"][:2],
                            backup_info[info]["md5"][2:],
                        )
                    )
                    os.remove(
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            backup_info[info]["md5"][:2],
                            backup_info[info]["md5"][2:],
                        )
                    )
                    os.rename(
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            backup_info[info]["md5"][:2],
                            backup_info[info]["md5"][2:] + ZST_EXT,
                        ),
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            xxhash_result[:2],
                            xxhash_result[2:],
                        )
                        + ZST_EXT,
                    )
                else:
                    xxhash_result = get_file_hash(
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            backup_info[info]["md5"][:2],
                            backup_info[info]["md5"][2:],
                        )
                    )
                    os.rename(
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            backup_info[info]["md5"][:2],
                            backup_info[info]["md5"][2:],
                        ),
                        os.path.join(
                            BACKUP_DATA_PATH,
                            "cache",
                            xxhash_result[:2],
                            xxhash_result[2:],
                        ),
                    )

                database.files.insert(
                    backup_uuid=backup_uuid,
                    name=info,
                    path=root_path,
                    hash=xxhash_result,
                    hash_type="xxhash",
                )
            database(database.count.hash == backup_info[info]["md5"]).update(hash=xxhash_result) # for table count
        elif backup_info[info]["type"] == "dir":
            scan_backup_info(
                backup_uuid,
                backup_info[info]["files"],
                root_path=os.path.join(root_path, info),
            )


if __name__ == "__main__":
    load_database()
    if MIGRATE_POLICY in [1, 2]:  # 2.0.x 不用处理 xxhash
        # 1.x to 2.0.x
        all_info = get_all_backup_info(os.path.join(BACKUP_DATA_PATH, "metadata"))
        for backup_info in all_info:
            database.backups.insert(
                uuid=backup_info["backup_uuid"],
                time=int(
                    datetime.datetime.strptime(
                        backup_info["backup_time"], "%Y-%m-%d %H:%M:%S"
                    ).timestamp()
                ),
                size=backup_info["backup_size"],
                message=backup_info["backup_message"],
            )
            scan_backup_info(
                backup_uuid=backup_info["backup_uuid"],
                backup_info=backup_info["backup_files"],
            )
            print(f'已迁移 {backup_info["backup_uuid"]}')
        database.commit()
        # rmtree(os.path.join(BACKUP_DATA_PATH, "metadata"))
        print(f"已完成，请在备份 {BACKUP_DATA_PATH}/metadata 文件夹后确认插件运行正常，再手动删除")
    elif MIGRATE_POLICY == 3:
        all_files_info = database((database.files.hash_type == "md5")).select()
        for file_info in all_files_info:
            old_hash = file_info.hash
            decompress_zstd(
                os.path.join(BACKUP_DATA_PATH, "cache", old_hash[:2], old_hash[2:])
                + ZST_EXT,
                os.path.join(BACKUP_DATA_PATH, "cache", old_hash[:2], old_hash[2:]),
            )
            xxhash_result = get_file_hash(
                os.path.join(BACKUP_DATA_PATH, "cache", old_hash[:2], old_hash[2:])
            )
            os.rename(
                os.path.join(BACKUP_DATA_PATH, "cache", old_hash[:2], old_hash[2:])
                + ZST_EXT,
                os.path.join(
                    BACKUP_DATA_PATH, "cache", xxhash_result[:2], xxhash_result[2:]
                )
                + ZST_EXT,
            )
            os.remove(
                os.path.join(BACKUP_DATA_PATH, "cache", old_hash[:2], old_hash[2:])
            )
            database(
                (database.files.hash == old_hash) | (database.files.hash_type == "md5")
            ).update(hash=xxhash_result, hash_type="xxhash")
            database(database.count.hash == old_hash).update(hash=xxhash_result) # for table count
        database.commit()
        print("已经将数据库内所有 md5 替换为 xxhash")
