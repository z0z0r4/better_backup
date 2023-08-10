from shutil import copytree, copyfile, rmtree
import os
import hashlib
import time
import json
import uuid
from mcdreforged.api.all import *
from better_backup.config import Configuration
from typing import Optional

SRC_DIR = "src"
METADATA_DIR = "metadata"
CACHE_DIR = "cache"
TEMP_DIR = "temp"


def walk_and_cache_files(
    dir_path: str,
    cache_folder: str,
    ignored_files: list = [],
    ignored_folders: list = [],
    ignored_extensions: list = [],
) -> dict:
    """获取文件夹内包括子文件夹的文件列表以及文件夹大小"""
    total_size: int = 0
    result: dict = {}
    for name in os.listdir(dir_path):
        if all(
            [
                name not in ignored_files,
                name not in ignored_folders,
                os.path.splitext(name)[1] not in ignored_extensions,
            ]
        ):
            full_path = os.path.join(dir_path, name)
            if os.path.isfile(full_path):
                f_stat = os.stat(full_path)
                result[name] = {
                    "type": "file",
                    "md5": get_file_md5_and_cache(full_path, cache_folder),
                    "mtime": f_stat.st_mtime,
                    "size": f_stat.st_size,
                }
                total_size += f_stat.st_size
            else:
                walk_files_info, _total_size = walk_and_cache_files(
                    full_path,
                    cache_folder,
                    ignored_files,
                    ignored_folders,
                    ignored_extensions,
                )
                result[name] = {
                    "type": "dir",
                    "files": walk_files_info,
                }
                total_size += _total_size
    return result, total_size


def get_file_md5_by_file_obj(obj, range_size: int = 1024 * 1024) -> str:
    """通过文件对象获取文件的md5值"""
    md5 = hashlib.md5()
    while True:
        data = obj.read(range_size)
        if not data:
            break
        md5.update(data)
    return md5.hexdigest()


def get_file_md5_and_cache(src_file: str, cache_folder: str):
    """获取文件的md5值，并将文件复制到缓存文件夹中"""
    if not os.path.exists(os.path.split(src_file)[0]):
        os.makedirs(os.path.split(src_file)[0])
    with open(src_file, "rb") as f:
        md5 = get_file_md5_by_file_obj(f)
        dst_file = os.path.join(cache_folder, md5[:2], md5[2:])
        f.seek(0, 0)
        if not os.path.exists(dst_file):
            with open(dst_file, "wb") as f2:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    f2.write(data)
    return md5


def get_dir_size(dir_path: str) -> int:
    size = 0
    for root, dirs, files in os.walk(dir_path):
        size += sum([os.path.getsize(os.path.join(root, name)) for name in files])
    return size


def temp_src_folder(*src_dirs: str, temp_dir: str = TEMP_DIR, src_path: str = None):
    os.makedirs(temp_dir, exist_ok=True)
    for src_dir in src_dirs:
        copytree(
            os.path.join(src_path, src_dir),
            os.path.join(temp_dir, src_dir),
            dirs_exist_ok=True,
            # ignore=ignore_files_and_folders, # copy all files including ignore files
        )
    # copy all then delete all
    for src_dir in src_dirs:
        rmtree(os.path.join(src_path, src_dir))
        os.makedirs(os.path.join(src_path, src_dir))


def restore_temp(
    *src_dirs: str,
    temp_dir: str = TEMP_DIR,
    config: Configuration = None,
):
    def ignore_files_and_folders(src: str, names: list) -> list:
        ignore_names = []
        for name in names:
            if (
                name in (config.ignored_files or config.ignored_folders)
                and os.path.splitext(name)[1] in config.ignored_extensions
            ):
                ignore_names.append(name)
        return ignore_names

    src_path = config.server_path
    for src_dir in src_dirs:
        os.removedirs(os.path.join(src_path, src_dir))
        os.makedirs(os.path.join(src_path, src_dir))

        copytree(
            os.path(temp_dir, src_dir),
            os.path.join(src_path, src_dir),
            dirs_exist_ok=True,
            ignore=ignore_files_and_folders,
        )


def clear_temp(temp_dir: str = TEMP_DIR, src_path: str = None):
    rmtree(os.path.join(src_path, temp_dir))


def get_backup_info(backup_uuid: str, metadata_dir: str) -> dict:
    with open(
        os.path.join(metadata_dir, f"backup_{backup_uuid}_info.json"), encoding="UTF-8"
    ) as f:
        return json.load(f)


def save_backup_info(backup_info: str, metadata_dir: str):
    with open(
        os.path.join(metadata_dir, f"backup_{backup_info['backup_uuid']}_info.json"),
        "w",
        encoding="UTF-8",
    ) as f:
        json.dump(backup_info, f, indent=4)


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


def get_all_backup_info_sort_by_timestamp(metadata_dir: str) -> list:
    result = sorted(
        get_all_backup_info(metadata_dir=metadata_dir),
        key=lambda backup_info: backup_info["backup_time"],
        reverse=True,
    )
    return result


def get_latest_backup_uuid(metadata_dir: str) -> Optional[str]:
    result = get_all_backup_info_sort_by_timestamp(metadata_dir)
    if result != []:
        return result[0]["backup_uuid"]


def check_backup_uuid_available(backup_uuid: str, metadata_dir: str) -> bool:
    try:
        get_backup_info(backup_uuid=backup_uuid, metadata_dir=metadata_dir)
        return True
    except:
        return False


def scan_backup_info(backup_info: dict):
    md5_set = set()
    for info in backup_info:
        if backup_info[info]["type"] == "file":
            hash = backup_info[info]["md5"]
            md5_set.add(hash)
        elif backup_info[info]["type"] == "dir":
            kid_md5_set = scan_backup_info(backup_info[info]["files"])
            md5_set = md5_set.union(kid_md5_set)
    return md5_set


def add_cache_index_count(metadata_dir: str, backup_info: dict):
    with open(os.path.join(metadata_dir, f"cache_index.json"), encoding="UTF-8") as f:
        cache_info = json.load(f)
        md5_set = scan_backup_info(backup_info["backup_files"])
        for md5 in md5_set:
            if md5 in cache_info:
                cache_info[md5] += 1
            else:
                cache_info[md5] = 1
    with open(
        os.path.join(metadata_dir, f"cache_index.json"), "w", encoding="UTF-8"
    ) as f:
        json.dump(cache_info, f, indent=4)


def subtract_cache_index_count(metadata_dir: str, cache_dir: str, backup_info: dict):
    with open(os.path.join(metadata_dir, f"cache_index.json"), encoding="UTF-8") as f:
        cache_info = json.load(f)
        md5_set = scan_backup_info(backup_info["backup_files"])
        for md5 in md5_set:
            cache_info[md5] -= 1
            if cache_info[md5] == 0:
                os.remove(os.path.join(cache_dir, md5[:2], md5[2:]))
                del cache_info[md5]
    with open(
        os.path.join(metadata_dir, f"cache_index.json"), "w", encoding="UTF-8"
    ) as f:
        json.dump(cache_info, f, indent=4)


def make_backup_util(
    *src_dirs: str,
    metadata_dir: str = METADATA_DIR,
    cache_dir: str = CACHE_DIR,
    message: Optional[str] = None,
    src_path: str = None,
    config: Configuration = None,
) -> dict:
    create_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    backup_uuid = uuid.uuid4().hex[:6]  # 6 位 UUID 不可能撞吧...
    total_files_info = {}
    total_size = 0
    for src_dir in src_dirs:
        walk_files_info, files_size = walk_and_cache_files(
            os.path.join(src_path, src_dir),
            cache_folder=cache_dir,
            ignored_files=config.ignored_files,
            ignored_extensions=config.ignored_extensions,
        )
        total_files_info[src_dir] = {
            "type": "dir",
            "size": files_size,
            "files": walk_files_info,
        }
        total_size += files_size
    backup_info = {
        "backup_uuid": backup_uuid,
        "backup_time": create_time,
        "backup_size": total_size,
        "backup_files": total_files_info,
        "backup_message": message,
    }
    save_backup_info(backup_info, metadata_dir)
    add_cache_index_count(metadata_dir, backup_info)
    return backup_info


def restore_backup_util(
    backup_uuid: str, metadata_dir: str, dst_dir: str, config: Configuration
):
    backup_info = get_backup_info(backup_uuid=backup_uuid, metadata_dir=metadata_dir)

    def restore(dst_dir: str, cache_dir: str, backup_info: dict):
        for info in backup_info:
            if backup_info[info]["type"] == "dir":
                os.makedirs(os.path.join(dst_dir, info), exist_ok=True)
                restore(
                    dst_dir=os.path.join(dst_dir, info),
                    backup_info=backup_info[info]["files"],
                    cache_dir=cache_dir,
                )
            elif backup_info[info]["type"] == "file":
                copyfile(
                    os.path.join(
                        config.backup_data_path,
                        cache_dir,
                        backup_info[info]["md5"][:2],
                        backup_info[info]["md5"][2:],
                    ),
                    os.path.join(dst_dir, info),
                )

    restore(
        dst_dir=dst_dir,
        backup_info=backup_info["backup_files"],
        cache_dir=CACHE_DIR,
    )
    return backup_info


def remove_backup_util(backup_uuid: str, metadata_dir: str, cache_dir: str):
    backup_info = get_backup_info(backup_uuid=backup_uuid, metadata_dir=metadata_dir)
    subtract_cache_index_count(metadata_dir, cache_dir, backup_info)
    os.remove(
        os.path.join(metadata_dir, f"backup_{backup_info['backup_uuid']}_info.json")
    )
