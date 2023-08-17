import pyzstd
import functools
import hashlib
import importlib
import os
import tarfile
import time
import uuid
from enum import Enum
from shutil import copyfile, copytree, rmtree
from threading import Lock
from typing import Any, Callable, Optional

from mcdreforged.api.all import *

from better_backup.config import Configuration, config
from better_backup.constants import CACHE_DIR, PLUGIN_ID, TEMP_DIR, ZST_EXT
from better_backup.database import database

pyzstd = None
try:
    pyzstd = importlib.import_module("pyzstd")
except ModuleNotFoundError as e:
    pass


operation_lock = Lock()
operation_name = RText("?")


class ExportFormat(Enum):
    plain = ("", False)
    tar = (".tar", False)
    tar_gz = (".tar.gz", True, 9)
    tar_xz = (".tar.xz", False)
    tar_zst = (".tar.zst", True, 22)

    def __init__(self, suffix, supports_compress_level, max_level=9):
        self.suffix = suffix
        self.supports_compress_level = supports_compress_level
        self.max_level = max_level

    @classmethod
    def of(cls, mode: str) -> "ExportFormat":
        try:
            return cls[mode]
        except KeyError:
            return cls.plain

    def get_file_name(self, base_name: str) -> str:
        return base_name + self.suffix


class ZstdTarFile(tarfile.TarFile):
    def __init__(self, name, mode='r', *, compresslevel=None, zstd_dict=None, **kwargs):
        if pyzstd is None:
            raise ModuleNotFoundError(
                tr("export_backup.zstd_not_found")
            )
        self.zstd_file = pyzstd.ZstdFile(name, mode,
                                         level_or_option=compresslevel,
                                         zstd_dict=zstd_dict)
        try:
            super().__init__(fileobj=self.zstd_file, mode=mode, **kwargs)
        except:
            self.zstd_file.close()
            raise

    def close(self):
        try:
            super().close()
        finally:
            self.zstd_file.close()


class Backup:
    uuid: str
    time: int
    size: int
    message: str

    def __init__(self, uuid, time, size, message) -> None:
        self.uuid = uuid
        self.time = time
        self.size = size
        self.message = message

    @classmethod
    def insert_new(cls, uuid, time, size, message) -> 'Backup':
        backup = Backup(uuid, time, size, message)
        database.backups.insert(
            uuid=uuid,
            time=time,
            size=size,
            message=message
        )
        database.commit()
        return backup

    @classmethod
    def from_row(cls, row):
        return Backup(row.uuid, row.time, row.size, row.message)


class MetadataError(SyntaxError):
    pass


def tr(translation_key: str, *args) -> RTextMCDRTranslation:
    return ServerInterface.get_instance().rtr(
        "better_backup.{}".format(translation_key), *args
    )


def thread_name(operation):
    return f"{PLUGIN_ID}:{operation}"


def command_run(message: Any, text: Any, command: str) -> RTextBase:
    fancy_text = message.copy() if isinstance(
        message, RTextBase) else RText(message)
    return fancy_text.set_hover_text(text).set_click_event(RAction.run_command, command)


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


def single_op(name: RTextBase):
    """ensure operation lock"""
    def wrapper(func: Callable):
        @functools.wraps(func)
        def wrap(source: CommandSource, *args, **kwargs):
            global operation_name
            acq = operation_lock.acquire(blocking=False)
            if acq:
                operation_name = name
                try:
                    func(source, *args, **kwargs)
                finally:
                    try:
                        operation_lock.release()
                    except:
                        pass
            else:
                print_message(
                    source, tr("lock.warning", operation_name), reply_source=True
                )

        return wrap

    return wrapper


def format_dir_size(size: int) -> str:
    if size < 2**30:
        return "{} MB".format(round(size / 2**20, 2))
    else:
        return "{} GB".format(round(size / 2**30, 2))


def get_stream_md5(obj, range_size: int = 131072) -> str:
    """通过文件对象获取文件的md5值"""
    md5 = hashlib.md5()
    while True:
        data = obj.read(range_size)
        if not data:
            break
        md5.update(data)
    return md5.hexdigest()


def cache_file(src_file: str):
    """获取文件的md5值，并将文件复制到缓存文件夹中"""
    # os.makedirs(os.path.split(src_file)[0], exist_ok=True)
    with open(src_file, "rb") as fsrc:
        hash = get_stream_md5(fsrc)
        dst_file = get_cached_file(hash)
        zst_dst_file = dst_file + ZST_EXT
        fsrc.seek(0, 0)
        if os.path.exists(zst_dst_file):
            size = os.path.getsize(zst_dst_file)
        elif os.path.exists(dst_file):
            size = os.path.getsize(dst_file)
        else:
            if config.backup_compress_level:
                if pyzstd is None:  # just raise
                    raise ModuleNotFoundError(
                        tr("create_backup.zstd_not_found")
                    )
                with open(zst_dst_file, "wb") as fdst:
                    pyzstd.compress_stream(
                        fsrc, fdst, level_or_option=config.backup_compress_level
                    )
                    size = fdst.tell()
            else:
                with open(dst_file, "wb") as fdst:
                    while True:
                        data = fsrc.read(131072)
                        if not data:
                            break
                        fdst.write(data)
    return size, hash


def get_dir_size(dir_path: str) -> int:
    size = 0
    for root, _, files in os.walk(dir_path):
        size += sum([os.path.getsize(os.path.join(root, name))
                    for name in files])
    return size

def ignore_files_and_folders(src: str, names: list) -> list:
    ignore_names = []
    for name in names:
        if (
            name in (config.ignored_files or config.ignored_folders)
            and os.path.splitext(name)[1] in config.ignored_extensions
        ):
            ignore_names.append(name)
    return ignore_names

def temp_src_folder(*src_dirs: str, temp_dir: str = TEMP_DIR, src_path: str = None):
    os.makedirs(temp_dir, exist_ok=True)
    for src_dir in src_dirs:
        copytree(
            os.path.join(src_path, src_dir),
            os.path.join(temp_dir, src_dir),
            dirs_exist_ok=True,
            ignore=ignore_files_and_folders,
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


def get_cached_file(hash: str):
    return os.path.join(config.backup_data_path, CACHE_DIR, hash[:2], hash[2:])


def get_backup_files(uuid: str) -> list:
    return database(database.files.backup_uuid == uuid).select(database.files.ALL)


def get_backup_row(uuid: str):
    return get_backups(database.backups.uuid == uuid).first()


def get_backups(filter=None, orderby=None):
    return database(filter).select(database.backups.ALL, orderby=orderby) or []


def get_files(filter=None, orderby=None):
    return database(filter).select(database.files.ALL, orderby=orderby)


def create_backup_util(
    *src_dirs: str,
    cache_dir: str = CACHE_DIR,
    message: Optional[str] = None,
    src_path: str = None,
    config: Configuration = None,
) -> dict:
    create_time = time.time()
    backup_uuid = uuid.uuid4().hex[:6]  # 6 位 UUID 不可能撞吧...
    total_size = 0
    for src_dir in src_dirs:
        dir_path = os.path.join(src_path, src_dir)
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if not (filename in config.ignored_files or os.path.splitext(filename)[1] in config.ignored_extensions or os.path.split(root)[1] in config.ignored_folders):
                    path = os.path.relpath(root, src_path)
                    file = os.path.join(root, filename)
                    size, hash = cache_file(file)
                    total_size += size
                    database.files.insert(
                        backup_uuid=backup_uuid,
                        name=filename,
                        path=path,
                        hash=hash,
                        hash_type="md5"
                    )
    database.commit()

    backup_info = Backup.insert_new(
        backup_uuid, create_time, total_size, message)
    return backup_info


def restore_backup_util(
    backup_uuid: str, dst_dir: str
) -> Backup:
    backup_info = Backup.from_row(get_backup_row(backup_uuid))

    files = get_backup_files(backup_uuid)

    for file in files:
        src_file = get_cached_file(file.hash)  # md5
        zst_src = src_file + ZST_EXT  # md5.zst

        fin_dst_dir = os.path.join(dst_dir, file.path)  # server/world
        os.makedirs(fin_dst_dir, exist_ok=True)
        # server/world/level.dat
        dst_file = os.path.join(fin_dst_dir, file.name)

        if os.path.exists(zst_src):  # Try .zst first
            if pyzstd is None:
                raise ModuleNotFoundError(
                    str(tr("restore_backup.zstd_not_found"))
                )
            with open(zst_src, "rb") as fsrc:
                with open(dst_file, "wb") as fdst:
                    pyzstd.decompress_stream(fsrc, fdst)
        elif os.path.exists(src_file):
            copyfile(src_file, dst_file)

    return backup_info


def remove_backup_util(backup_uuid: str):
    files = get_backup_files(backup_uuid)
    for file in files:
        hash = file.hash
        file.delete_record()
        if database(database.files.hash == hash).isempty():  # remove file record if useless
            path = get_cached_file(hash)
            zst_path = path + ZST_EXT
            if os.path.exists(zst_path):
                os.remove(zst_path)
            elif os.path.exists(path):
                os.remove(path)
    database.commit()
    database(database.backups.uuid == backup_uuid).delete() # remove backup record
    database.commit()


def auto_remove_util(limit: int) -> list:
    all_backup_info = get_backups((database.backups.locked == False) | (database.backups.locked == None), orderby=database.backups.time)
    count = len(all_backup_info)
    removed_uuids = []
    if count > limit:
        for backup_info in all_backup_info[limit:]:
            remove_backup_util(backup_info.uuid)
            removed_uuids.append(backup_info.uuid)
    return removed_uuids


def export_backup_util(
    backup_uuid: str,
    output_dir: str,
    export_format: ExportFormat,
    compress_level: int = 1,
):
    dst_dir = os.path.join(output_dir, backup_uuid)
    if os.path.isdir(dst_dir):
        rmtree(dst_dir)
    restore_backup_util(  # plain export first
        backup_uuid=backup_uuid,
        dst_dir=dst_dir
    )
    output_path = dst_dir
    if export_format != ExportFormat.plain:  # pack to tar if required
        output_path = add_to_tar(
            backup_uuid, dst_dir, output_dir, export_format, compress_level
        )
        rmtree(dst_dir)
    return output_path


def get_export_file_name(backup_format: ExportFormat, backup_uuid: str):
    if backup_format == ExportFormat.plain:
        raise ValueError("plain mode is not supported")
    return backup_format.get_file_name(backup_uuid)


def add_to_tar(
    backup_uuid: str,
    src_dir: str,
    dst_dir: str,
    export_format: ExportFormat = ExportFormat.tar,
    compress_level: int = 1,
) -> str:

    tar_builder = tarfile.open
    if export_format == ExportFormat.tar_gz:
        tar_mode = "w:gz"
    elif export_format == ExportFormat.tar_xz:
        tar_mode = "w:xz"
    elif export_format == ExportFormat.tar:
        tar_mode = "w"
    elif export_format == ExportFormat.tar_zst:
        tar_mode = "w"
        tar_builder = ZstdTarFile

    kwargs = {}
    if export_format.supports_compress_level and 1 <= compress_level <= export_format.max_level:
        kwargs["compresslevel"] = compress_level

    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    tar_path = os.path.join(
        dst_dir, get_export_file_name(export_format, backup_uuid))

    with tar_builder(tar_path, tar_mode, **kwargs) as f:
        f.add(src_dir, arcname=backup_uuid)

    return tar_path
