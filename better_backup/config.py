from typing import List, Dict

from mcdreforged.api.utils.serializer import Serializable


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
    }
