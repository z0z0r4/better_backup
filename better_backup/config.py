from typing import List, Dict
import os

from mcdreforged.api.utils.serializer import Serializable

CONFIG_FILE = os.path.join("config", "Better_Backup.json")
class Configuration(Serializable):
    size_display: bool = True
    turn_off_auto_save: bool = True
    ignored_files: List[str] = ["session.lock"]
    ignored_folders: List[str] = []
    ignored_extensions: List[str] = [".lock"]
    world_names: List[str] = [
		'world'
	]
    backup_data_path: str = "./better_backup"
    server_path: str = "./server"
    overwrite_backup_folder: str = "overwrite"
    export_backup_folder: str = "export_backup"
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
        "export": 4
    }
    timer_enabled: bool = True
    timer_interval: float = 5.0  # minutes