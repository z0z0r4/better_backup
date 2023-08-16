from mcdreforged.api.types import ServerInterface

PLUGIN_ID = "better_backup"
PREFIX = "!!bb"

OLD_METADATA_DIR = "metadata"

CACHE_DIR = "cache"
TEMP_DIR = "override"

LIST_PAGE_SIZE = 10

ZST_EXT = ".zst"

# this is an official api now btw
server_inst = ServerInterface.get_instance().as_plugin_server_interface()
