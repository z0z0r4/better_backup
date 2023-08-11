import time
from threading import Thread, Event

from mcdreforged.api.all import *

from better_backup.config import Configuration, CONFIG_FILE
from better_backup.utils import *

config: Configuration


def load_config(server: PluginServerInterface):
    global config
    config = server.load_config_simple(
        CONFIG_FILE,
        target_class=Configuration,
        in_data_folder=False,
        source_to_reply=None,
        echo_in_console=False,
    )


class Timer():
    def __init__(self, server: PluginServerInterface):
        load_config(server)
        self.time_since_backup = time.time()
        self.timer_interval: float = config.timer_interval
        self.server = server
        self.is_enabled = False
        self.is_backup_triggered = False

    @staticmethod
    def get_interval() -> float:
        return config.timer_interval

    @classmethod
    def get_backup_interval(cls):
        return cls.get_interval() * 60

    @staticmethod
    def tr(translation_key: str, *args) -> RTextMCDRTranslation:
        return ServerInterface.get_instance().rtr(
            "better_backup.timer.{}".format(translation_key), *args
        )

    def set_interval(self, timer_interval: float):
        self.timer_interval = timer_interval
        self.reset_timer()

    def broadcast(self, message):
        rtext = RTextList("[{}] ".format("Timer"), message)
        if self.server.is_server_startup():
            print_message(self.server.get_plugin_command_source(), rtext)
        else:
            print_message(self.server.get_plugin_command_source(), rtext, only_server=True)

    def set_enabled(self, value: bool = True):
        self.is_enabled = value
        self.reset_timer()

    def reset_timer(self):
        self.time_since_backup = time.time()

    def get_next_backup_message(self):
        return self.tr(
            "get_next_backup_message",
            time.strftime(
                "%Y/%m/%d %H:%M:%S",
                time.localtime(self.time_since_backup + self.get_backup_interval()),
            ),
        )

    def broadcast_next_backup_time(self):
        self.broadcast(self.get_next_backup_message())

    def on_backup_created(self, backup_uuid: dict):
        self.broadcast(self.tr("on_backup_created"))
        self.reset_timer()
        self.broadcast_next_backup_time()
        self.is_backup_triggered = True