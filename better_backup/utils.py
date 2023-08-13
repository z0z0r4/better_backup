from shutil import copytree, copyfile, rmtree
import os
import hashlib
import time
import json
import uuid
import tarfile
import importlib
import sys
from mcdreforged.api.all import *
from better_backup.config import config, Configuration
from typing import Optional
from enum import Enum


pyzstd = None
try:
    pyzstd = importlib.import_module("pyzstd")
except ModuleNotFoundError as e:
    pass

SRC_DIR = "src"
METADATA_DIR = "metadata"
CACHE_DIR = "cache"
TEMP_DIR = "overwrite"
ZST_EXT = ".zst"


class ExportFormat(Enum):
    plain = ("", False)
    tar = (".tar", False)
    tar_gz = (".tar.gz", True)
    tar_xz = (".tar.xz", False)

    def __init__(self, suffix, supports_compress_level):
        self.suffix = suffix
        self.supports_compress_level = supports_compress_level

    @classmethod
    def of(cls, mode: str) -> "ExportFormat":
        try:
            return cls[mode]
        except KeyError:
            return cls.plain

    def get_file_name(self, base_name: str) -> str:
        return base_name + self.suffix


def tr(translation_key: str, *args) -> RTextMCDRTranslation:
    return ServerInterface.get_instance().rtr(
        "better_backup.{}".format(translation_key), *args
    )


def print_message(
    source: CommandSource,
    msg,
    only_player=False,
    only_server=False,
    reply_source=False,
    prefix="§a[Better Backup]§r ",
):
    msg = RTextList(prefix, msg)
    if reply_source:
        source.reply(msg)
    elif only_player:
        source.get_server().say(msg)
    elif only_server:
        source.get_server().logger.info(msg)
    else:
        source.get_server().broadcast(msg)


def format_dir_size(size: int) -> str:
    if size < 2**30:
        return "{} MB".format(round(size / 2**20, 2))
    else:
        return "{} GB".format(round(size / 2**30, 2))


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
                    # "mtime": f_stat.st_mtime,
                    # "size": f_stat.st_size,
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


def get_file_md5_by_file_obj(obj, range_size: int = 131072) -> str:
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
    os.makedirs(os.path.split(src_file)[0], exist_ok=True)
    with open(src_file, "rb") as fsrc:
        md5 = get_file_md5_by_file_obj(fsrc)
        dst_file = os.path.join(cache_folder, md5[:2], md5[2:])
        zst_dst_file = dst_file + ZST_EXT
        fsrc.seek(0, 0)
        if not (os.path.exists(dst_file) or os.path.exists(zst_dst_file)):
            if config.backup_compress_level:
                if pyzstd is None:  # just raise
                    raise ModuleNotFoundError(
                        tr("create_backup.zstd_not_found", sys.executable)
                    )
                with open(zst_dst_file, "wb") as fdst:
                    pyzstd.compress_stream(
                        fsrc, fdst, level_or_option=config.backup_compress_level
                    )
            else:
                with open(dst_file, "wb") as fdst:
                    while True:
                        data = fsrc.read(131072)
                        if not data:
                            break
                        fdst.write(data)
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


def clear_temp(temp_dir: str = TEMP_DIR):
    rmtree(temp_dir)


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


def get_backup_uuid_by_keyword(keyword: str, metadata_dir: str):
    try:
        if len(keyword) == 6:
            if check_backup_uuid_available(
                backup_uuid=keyword, metadata_dir=metadata_dir
            ):
                return keyword
        elif len(keyword) < 6:
            all_info = get_all_backup_info_sort_by_timestamp(metadata_dir=metadata_dir)
            if len(all_info) == 0:
                return 0
            elif len(all_info) >= (int(keyword)) and int(keyword) > 0:
                return all_info[int(keyword) - 1]["backup_uuid"]
    except:
        return


def check_backup_uuid_available(backup_uuid: str, metadata_dir: str) -> bool:
    try:
        get_backup_info(backup_uuid=backup_uuid, metadata_dir=metadata_dir)
        return True
    except:
        return False


def scan_backup_info_get_md5_set(backup_info: dict):
    md5_set = set()
    for info in backup_info:
        if backup_info[info]["type"] == "file":
            hash = backup_info[info]["md5"]
            md5_set.add(hash)
        elif backup_info[info]["type"] == "dir":
            kid_md5_set = scan_backup_info_get_md5_set(backup_info[info]["files"])
            md5_set = md5_set.union(kid_md5_set)
    return md5_set


def add_cache_index_count(metadata_dir: str, backup_info: dict):
    with open(os.path.join(metadata_dir, f"cache_index.json"), encoding="UTF-8") as f:
        cache_info = json.load(f)
        md5_set = scan_backup_info_get_md5_set(backup_info["backup_files"])
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
        md5_set = scan_backup_info_get_md5_set(backup_info["backup_files"])
        for md5 in md5_set:
            cache_info[md5] -= 1
            if cache_info[md5] == 0:
                if os.path.exists(os.path.join(cache_dir, md5[:2], md5[2:])):
                    os.remove(os.path.join(cache_dir, md5[:2], md5[2:]))
                elif os.path.exists(
                    os.path.join(cache_dir, md5[:2], md5[2:]) + ZST_EXT
                ):
                    os.remove(os.path.join(cache_dir, md5[:2], md5[2:]) + ZST_EXT)
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
            ignored_folders=config.ignored_folders,
        )
        total_files_info[src_dir] = {
            "type": "dir",
            # "size": files_size,
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
    backup_uuid: str, metadata_dir: str, cache_dir: str, dst_dir: str
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
                src = os.path.join(
                    cache_dir,
                    backup_info[info]["md5"][:2],
                    backup_info[info]["md5"][2:],
                )
                zst_src = src + ZST_EXT  # md5.zst
                dst = os.path.join(dst_dir, info)
                # Try .zst first
                # 既然 config 默认开启那就应该先用 .zst
                if os.path.exists(zst_src):
                    if pyzstd is None:
                        raise ModuleNotFoundError(
                            str(tr("restore_backup.zstd_not_found", sys.executable))
                        )
                    with open(zst_src, "rb") as fsrc:
                        with open(dst, "wb") as fdst:
                            pyzstd.decompress_stream(fsrc, fdst)
                elif os.path.exists(src):
                    copyfile(
                        os.path.join(
                            cache_dir,
                            backup_info[info]["md5"][:2],
                            backup_info[info]["md5"][2:],
                        ),
                        dst,
                    )

    restore(
        dst_dir=dst_dir,
        backup_info=backup_info["backup_files"],
        cache_dir=cache_dir,
    )
    return backup_info


def remove_backup_util(backup_uuid: str, metadata_dir: str, cache_dir: str):
    backup_info = get_backup_info(backup_uuid=backup_uuid, metadata_dir=metadata_dir)
    subtract_cache_index_count(metadata_dir, cache_dir, backup_info)
    os.remove(
        os.path.join(metadata_dir, f"backup_{backup_info['backup_uuid']}_info.json")
    )


def auto_remove_util(metadata_dir: str, cache_dir: str, limit: int) -> list:
    all_backup_info = get_all_backup_info_sort_by_timestamp(metadata_dir)
    count = len(all_backup_info)
    removed_uuids = []
    if count > limit:
        for backup_info in all_backup_info[limit:]:
            remove_backup_util(
                backup_uuid=backup_info["backup_uuid"],
                metadata_dir=metadata_dir,
                cache_dir=cache_dir,
            )
            removed_uuids.append(backup_info["backup_uuid"])
    return removed_uuids


def export_backup_util(
    backup_uuid: str,
    metadata_dir: str,
    cache_dir,
    dst_dir: str,
    export_format: ExportFormat,
    compress_level: int = 1,
):
    if export_format == ExportFormat.plain:
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        rmtree(dst_dir)
        backup_info = get_backup_info(backup_uuid, metadata_dir=metadata_dir)
        restore_backup_util(
            backup_uuid=backup_info["backup_uuid"],
            metadata_dir=metadata_dir,
            cache_dir=cache_dir,
            dst_dir=dst_dir,
        )
        output_path = dst_dir
    else:
        output_path = export_backup_tar_util(
            backup_uuid, metadata_dir, cache_dir, dst_dir, export_format, compress_level
        )
    return output_path


def get_export_file_name(backup_format: ExportFormat, backup_uuid: str):
    if backup_format == ExportFormat.plain:
        raise ValueError("plain mode is not supported")
    return backup_format.get_file_name(backup_uuid)


def export_backup_tar_util(
    backup_uuid: str,
    metadata_dir: str,
    cache_dir,
    dst_dir: str,
    export_format: ExportFormat = ExportFormat.tar,
    compress_level: int = 1,
) -> str:
    backup_info = get_backup_info(backup_uuid=backup_uuid, metadata_dir=metadata_dir)

    def add_files_into_tar(
        tar_file_obj: tarfile.TarFile,
        parent_dir: str,
        cache_dir: str,
        backup_info: dict,
    ):
        for info in backup_info:
            if backup_info[info]["type"] == "dir":
                tar_file_obj = add_files_into_tar(
                    tar_file_obj=tar_file_obj,
                    parent_dir=os.path.join(parent_dir, info),
                    backup_info=backup_info[info]["files"],
                    cache_dir=cache_dir,
                )
            elif backup_info[info]["type"] == "file":
                tar_file_obj.add(
                    name=os.path.join(
                        cache_dir,
                        backup_info[info]["md5"][:2],
                        backup_info[info]["md5"][2:],
                    ),
                    arcname=os.path.join(parent_dir, info),
                )
        return tar_file_obj

    if export_format == ExportFormat.tar_gz:
        tar_mode = "w:gz"
    elif export_format == ExportFormat.tar_xz:
        tar_mode = "w:xz"
    elif tar_mode == ExportFormat.tar:
        tar_mode = "w"
    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    tar_path = os.path.join(dst_dir, get_export_file_name(export_format, backup_uuid))
    kwargs = {}
    if export_format.supports_compress_level and 1 <= compress_level <= 9:
        kwargs["compresslevel"] = compress_level
    with tarfile.open(tar_path, tar_mode, **kwargs) as backup_tar_obj:
        add_files_into_tar(
            tar_file_obj=backup_tar_obj,
            cache_dir=cache_dir,
            backup_info=backup_info["backup_files"],
            parent_dir=backup_info["backup_uuid"],
        )
    return tar_path
