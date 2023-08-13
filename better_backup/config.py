from typing import List, Dict
import os

from mcdreforged.api.utils.serializer import Serializable
from mcdreforged.api.all import ServerInterface

CONFIG_FILE = os.path.join("config", "Better_Backup.json")


class Configuration(Serializable):
    size_display: bool = True
    turn_off_auto_save: bool = True

    ignored_files: List[str] = ["session.lock"]
    ignored_folders: List[str] = []
    ignored_extensions: List[str] = [".lock"]

    world_names: List[str] = ["world"]
    # 自定义保存命令
    save_command: Dict[str, str] = {
        "save-off": "save-off",
        "save-all flush": "save-all flush",
        "save-on": "save-on",
    }
    # 自定义保存输出
    saved_output: List[str] = [
        "Saved the game",  # 1.13+
        "Saved the world",  # 1.12-
    ]
    backup_data_path: str = "./better_backup"
    server_path: str = "./server"
    overwrite_backup_folder: str = "overwrite"
    backup_compress_level: int = 3  # 0 to disable

    export_backup_folder: str = "./export_backup"
    export_backup_format: str = "tar_gz"  # plain / tar / tar_gz / tar_xz
    export_backup_compress_level: int = 1

    auto_remove: bool = True
    backup_count_limit: int = 20

    # 0:guest 1:user 2:helper 3:admin 4:owner
    minimum_permission_level: Dict[str, int] = {
        "make": 1,
        "restore": 2,
        "remove": 2,
        "confirm": 1,
        "abort": 1,
        "reload": 2,
        "list": 0,
        "reset": 2,
        "timer": 2,
        "export": 4,
    }

    timer_enabled: bool = True
    timer_interval: float = 5.0  # minutes


config = (
    ServerInterface.get_instance()
    .as_plugin_server_interface()
    .load_config_simple(
        CONFIG_FILE,
        target_class=Configuration,
        in_data_folder=False,
        source_to_reply=None,
    )
)
