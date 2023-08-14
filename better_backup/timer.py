import time

from mcdreforged.api.all import *

import better_backup.operations
from better_backup.config import config
from better_backup.constants import server_inst
from better_backup.utils import *


class Timer():
    def __init__(self, server: PluginServerInterface):
        self.running = False
        self.time_since_backup = time.time()
        self.timer_interval: float = config.timer_interval
        self.server = server
        self.is_enabled = config.timer_enabled
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

    def _set_interval(self, timer_interval: float):
        self.timer_interval = timer_interval
        config.timer_interval = timer_interval
        config.save()
        self._reset()

    def set_interval(self, source: CommandSource, interval: float):
        self._set_interval(interval)
        source.reply(Timer.tr("set_interval", interval))
        self.broadcast_next_backup_time()

    def broadcast(self, message):
        if self.server.is_server_startup():
            print_message(self.server.get_plugin_command_source(), message)
        else:
            print_message(self.server.get_plugin_command_source(),
                          message, only_server=True)

    def set_enabled(self, value: bool = True):
        self.is_enabled = value
        self._reset()

    def _reset(self):
        self.time_since_backup = time.time()

    def reset(self, source: CommandSource):
        self._reset()
        source.reply(Timer.tr("reset_timer"))
        self.broadcast_next_backup_time()

    def get_next_backup_message(self):
        return self.tr(
            "get_next_backup_message",
            time.strftime(
                "%Y/%m/%d %H:%M:%S",
                time.localtime(self.time_since_backup +
                               self.get_backup_interval()),
            ),
        )

    def broadcast_next_backup_time(self):
        self.broadcast(self.get_next_backup_message())

    def on_backup_created(self, backup_uuid: dict):
        self.broadcast(self.tr("on_backup_created"))
        self._reset()
        self.broadcast_next_backup_time()
        self.is_backup_triggered = True

    @new_thread(thread_name("timer"))
    def run(self):
        self.running = True
        while self.running:  # loop until stop
            while self.running:  # loop for backup interval
                time.sleep(0.1)
                if time.time() - self.time_since_backup > self.get_backup_interval():
                    break
            if self.is_enabled and self.server.is_server_startup():
                self.broadcast(
                    self.tr("run.trigger_time", self.get_interval()))
                self.is_backup_triggered = False

                better_backup.operations.do_create(
                    self.server.get_plugin_command_source(),
                    str(self.tr("run.timed_backup", "timer")),
                )

                if self.is_backup_triggered:
                    self.broadcast(self.tr("on_backup_succeed"))
                else:
                    self.broadcast(self.tr("on_backup_failed"))
                    self._reset()
                    self.broadcast_next_backup_time()

    def stop(self):
        self.running = False

    def show_status(self, source: CommandSource):
        print_message(
            source, Timer.tr("status.clock_enabled", self.is_enabled), reply_source=True
        )
        print_message(
            source,
            Timer.tr("status.clock_interval", round(config.timer_interval, 2)),
            reply_source=True,
        )
        if self.is_enabled:
            print_message(source, self.get_next_backup_message(),
                          reply_source=True)

    def set_status(self, source: CommandSource, value: bool, echo_to_player: bool = True):
        config.timer_enabled = value
        self.set_enabled(value)
        config.save()
        print_message(
            source,
            Timer.tr(
                "set_enabled.timer",
                Timer.tr("set_enabled.start") if value else Timer.tr(
                    "set_enabled.stop"),
            ),
            only_server=not echo_to_player,
        )
        if value:
            self.broadcast_next_backup_time()


timer = Timer(server_inst)
timer.run()
