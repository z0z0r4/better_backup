"""
用于从 v1.x 迁移到 v2.x

如非默认，请将 better_backup 数据所在写入 BACKUP_DATA_PATH

并将此文件放于所在 MCDR 的根目录下运行
"""

import os

from shutil import rmtree
import json
from pydal import DAL, Field
import datetime

database: DAL = None

BACKUP_DATA_PATH = "better_backup"
if os.path.exists(BACKUP_DATA_PATH):
    print(f"已找到 {BACKUP_DATA_PATH}")
else:
    print(f"未找到 {BACKUP_DATA_PATH}，请确认better_backup 数据所在")
    exit(1)


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
            database.files.insert(
                backup_uuid=backup_uuid,
                name=info,
                path=root_path,
                hash=backup_info[info]["md5"],
                hash_type="md5",
            )
        elif backup_info[info]["type"] == "dir":
            scan_backup_info(
                backup_uuid,
                backup_info[info]["files"],
                root_path=os.path.join(root_path, info),
            )


if __name__ == "__main__":
    load_database()
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
    rmtree(os.path.join(BACKUP_DATA_PATH, "metadata"))
    # print(f"已完成，请在备份后手动删除 {BACKUP_DATA_PATH}/metadata 文件夹")
