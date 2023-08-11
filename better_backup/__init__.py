from shutil import rmtree
import os
import time
import json
import re
from mcdreforged.api.all import *
from better_backup.config import Configuration
from typing import Optional, Any, Callable
from threading import Lock
import functools

from better_backup.utils import *
from better_backup.timer import Timer
from better_backup.config import CONFIG_FILE

PREFIX = "!!bb"
TimerPREFIX = "!!bb timer"


operation_lock = Lock()
operation_name = RText("?")
game_saved = False
uuid_selected = None
abort_restore = False
timer: Timer
timer_run_flag: bool = False


def init_folder(data_dir: str):
    os.makedirs(os.path.join(data_dir, METADATA_DIR), exist_ok=True)
    if not os.path.exists(os.path.join(data_dir, CACHE_DIR)):
        os.makedirs(os.path.join(data_dir, CACHE_DIR))
        for i in range(256):
            os.makedirs(
                os.path.join(data_dir, CACHE_DIR, format(i, "02X").lower()),
                exist_ok=True,
            )
    if not os.path.exists(os.path.join(data_dir, METADATA_DIR, "cache_index.json")):
        with open(
            os.path.join(data_dir, METADATA_DIR, "cache_index.json"),
            "w",
            encoding="UTF-8",
        ) as f:
            json.dump({}, f)


def command_run(message: Any, text: Any, command: str) -> RTextBase:
    fancy_text = message.copy() if isinstance(message, RTextBase) else RText(message)
    return fancy_text.set_hover_text(text).set_click_event(RAction.run_command, command)


def print_unknown_argument_message(source: CommandSource, error: UnknownArgument):
    print_message(
        source,
        command_run(
            tr("unknown_command.text", PREFIX), tr("unknown_command.hover"), PREFIX
        ),
        reply_source=True,
    )


def single_op(name: RTextBase):
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
                    operation_lock.release()
            else:
                print_message(
                    source, tr("lock.warning", operation_name), reply_source=True
                )

        return wrap

    return wrapper


def load_config():
    global config
    config = server_inst.load_config_simple(
        CONFIG_FILE,
        target_class=Configuration,
        in_data_folder=False,
        source_to_reply=None,
    )


def save_config():
    server_inst.save_config_simple(config, CONFIG_FILE, in_data_folder=False)


def show_timer_status(source: CommandSource):
    print_message(
        source, Timer.tr("status.clock_enabled", timer.is_enabled), reply_source=True
    )
    print_message(
        source,
        Timer.tr("status.clock_interval", round(config.timer_interval, 2)),
        reply_source=True,
    )
    if timer.is_enabled:
        print_message(source, timer.get_next_backup_message(), reply_source=True)


def timer_set_enabled(source: CommandSource, value: bool, echo_to_player: bool = True):
    config.timer_enabled = value
    timer.set_enabled(value)
    save_config()
    print_message(
        source,
        Timer.tr(
            "set_enabled.timer",
            Timer.tr("set_enabled.start") if value else Timer.tr("set_enabled.stop"),
        ),
        only_server=not echo_to_player,
    )
    if value:
        timer.broadcast_next_backup_time()


def timer_set_interval(source: CommandSource, interval: float):
    config.timer_interval = interval
    save_config()
    timer.set_interval(interval)
    source.reply(Timer.tr("set_interval", interval))
    timer.broadcast_next_backup_time()


def reset_timer(source: CommandSource):
    timer.reset_timer()
    source.reply(Timer.tr("reset_timer"))
    timer.broadcast_next_backup_time()


@new_thread("BB - timer")
def timer_run(timer: Timer):
    global timer_run_flag
    while True:  # loop until stop
        while True:  # loop for backup interval
            time.sleep(0.1)
            if not timer_run_flag:
                return
            if time.time() - timer.time_since_backup > timer.get_backup_interval():
                break
        if timer.is_enabled and timer.server.is_server_startup():
            timer.broadcast(timer.tr("run.trigger_time", timer.get_interval()))
            timer.is_backup_triggered = False

            do_create(
                timer.server.get_plugin_command_source(),
                str(timer.tr("run.timed_backup", "timer")),
            )

            if timer.is_backup_triggered:
                timer.broadcast(timer.tr("on_backup_succeed"))
            else:
                timer.broadcast(timer.tr("on_backup_failed"))
                timer.reset_timer()
                timer.broadcast_next_backup_time()


def trigger_abort(source: CommandSource):
    global abort_restore, uuid_selected
    abort_restore = True
    uuid_selected = None
    print_message(source, "Operation terminated!", reply_source=True)


def process_uuid(source: CommandSource, keyword: str):
    if keyword is None:
        keyword = get_latest_backup_uuid(
            os.path.join(config.backup_data_path, METADATA_DIR)
        )
        if keyword is None:
            print_message(source, tr("no_one_backup"), reply_source=True)
            return
    else:
        keyword = get_backup_uuid_by_keyword(
            keyword=keyword,
            metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
        )
        if keyword == 0:
            print_message(source, tr("no_one_backup"), reply_source=True)
            return
        elif keyword is None:
            print_message(source, tr("unknown_backup", keyword), reply_source=True)
            return
    return keyword


@new_thread("BB - create")
def create_backup(source: CommandSource, message: Optional[str]):
    do_create(source, message)


@single_op(tr("operations.create"))
def do_create(source: CommandSource, message: Optional[str]):
    print_message(source, tr("create_backup.start"))
    start_time = time.time()

    # start backup
    global game_saved
    game_saved = False
    if config.turn_off_auto_save:
        source.get_server().execute("save-off")
    source.get_server().execute("save-all flush")
    while True:
        time.sleep(0.01)
        if game_saved:
            break

    backup_info = make_backup_util(
        *config.world_names,
        metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
        cache_dir=os.path.join(config.backup_data_path, CACHE_DIR),
        message=message,
        src_path=config.server_path,
        config=config,
    )
    print_message(
        source,
        tr(
            "create_backup.success",
            backup_info["backup_uuid"],
            round(time.time() - start_time, 1),
            "§l*§r {0} §l*§r {1}".format(
                format_dir_size(backup_info["backup_size"]), message
            ),
        ),
    )
    if config.turn_off_auto_save:
        source.get_server().execute("save-on")

    timer.on_backup_created(backup_uuid=backup_info["backup_uuid"])
    if config.auto_remove:
        removed_uuids = auto_remove_util(
            metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
            cache_dir=os.path.join(config.backup_data_path, CACHE_DIR),
            limit=config.backup_count_limit,
        )
        print_message(source, tr("auto_remove", " §l*§r ".join(removed_uuids)))


@new_thread("BB - remove")
@single_op(tr("operations.remove"))
def remove_backup(source: CommandSource, uuid: Optional[str]):
    uuid_result = process_uuid(source, uuid)
    if uuid_result is None:
        return

    all_backup_info = get_all_backup_info(
        metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR)
    )
    for backup_info in all_backup_info:
        if uuid_result == backup_info["backup_uuid"]:
            remove_backup_util(
                backup_uuid=uuid,
                metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
                cache_dir=os.path.join(config.backup_data_path, CACHE_DIR),
            )
    print_message(source, tr("remove_backup.success", uuid_result))


def restore_backup(source: CommandSource, uuid: Optional[str]):
    global uuid_selected, abort_restore
    abort_restore = False
    uuid_selected = process_uuid(source, uuid)
    if uuid_selected is None:
        return
    uuid_selected = uuid

    print_message(source, tr("restore_backup.echo_action", uuid_selected))
    text = RTextList(
        RText(tr("restore_backup.confirm_hint", PREFIX))
        .h(tr("restore_backup.confirm_hover"))
        .c(
            RAction.suggest_command,
            f"{PREFIX} confirm",
        ),
        ", ",
        RText(tr("restore_backup.abort_hint", PREFIX))
        .h(tr("restore_backup.abort_hover"))
        .c(
            RAction.suggest_command,
            f"{PREFIX} abort",
        ),
    )
    print_message(
        source,
        text,
    )


@new_thread("BB - restore")
def confirm_restore(source: CommandSource):
    # !!bb confirm
    global uuid_selected
    if uuid_selected is None:
        print_message(
            source, tr("confirm_restore.nothing_to_confirm"), reply_source=True
        )
        return
    # !!bb abord
    print_message(source, tr("do_restore.countdown.intro"))
    for countdown in range(1, 10):
        print_message(
            source,
            command_run(
                tr(
                    "do_restore.countdown.text",
                    10 - countdown,
                    uuid_selected,
                ),
                tr("do_restore.countdown.hover"),
                "{} abort".format(PREFIX),
            ),
        )
        for i in range(10):
            time.sleep(0.1)
            global abort_restore
            if abort_restore:
                print_message(source, tr("do_restore.abort"))
                return
    do_restore(source)


@single_op(tr("operations.restore"))
def do_restore(source: CommandSource):
    global uuid_selected
    try:
        source.get_server().stop()
        server_inst.logger.info("Wait for server to stop")
        source.get_server().wait_for_start()

        server_inst.logger.info("Backup current world to avoid idiot")
        temp_src_folder(
            *config.world_names,
            temp_dir=os.path.join(
                config.backup_data_path, config.overwrite_backup_folder
            ),
            src_path=config.server_path,
        )
        server_inst.logger.info(f"Restore backup {uuid_selected}")

        backup_info = restore_backup_util(
            backup_uuid=uuid_selected,
            metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
            cache_dir=os.path.join(config.backup_data_path, CACHE_DIR),
            dst_dir=config.server_path,
        )
        source.get_server().start()
        print_message(source, tr("restore_backup.success", backup_info["backup_uuid"]))
    except:
        server_inst.logger.exception(
            tr(
                "restore_backup.fail",
                uuid_selected,
                source,
            )
        )
        restore_temp(
            config.world_names,
            os.path.join(config.backup_data_path, config.overwrite_backup_folder),
            config,
        )
    finally:
        clear_temp(
            temp_dir=os.path.join(
                config.backup_data_path, config.overwrite_backup_folder
            )
        )
        uuid_selected = None


LIST_PAGE_SIZE = 10


def list_backups(source: CommandSource, page_num: int = 1):
    all_backup_info = get_all_backup_info_sort_by_timestamp(
        metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR)
    )
    if len(all_backup_info) == 0:
        text = RTextList(tr("no_one_backup") + "\n")
        header_text = tr("list_backup.title") + "\n"
    elif (
        LIST_PAGE_SIZE * (page_num - 1) >= len(all_backup_info) or page_num <= 0
    ):  # 不存在这一页
        print_message(source, tr("list_backup.page.page_not_found"), reply_source=True)
        return
    else:
        text = RTextList()
        header_text = tr("list_backup.title") + "\n"
        for _i in range(((page_num - 1) * LIST_PAGE_SIZE), page_num * LIST_PAGE_SIZE):
            if _i <= (len(all_backup_info) - 1):
                backup_info = all_backup_info[_i]
                text += RTextList(
                    RText(f'[§e{_i+1}§r] [§e{backup_info["backup_uuid"]}§r] '),
                    RText("[▷] ", color=RColor.green)
                    .h(tr("list_backup.restore_hint", backup_info["backup_uuid"]))
                    .c(
                        RAction.suggest_command,
                        f'{PREFIX} restore {backup_info["backup_uuid"]}',
                    ),
                    RText("[x] ", color=RColor.green)
                    .h(tr("list_backup.remove_hint", backup_info["backup_uuid"]))
                    .c(
                        RAction.suggest_command,
                        f'{PREFIX} remove {backup_info["backup_uuid"]}',
                    ),
                    RText(
                        backup_info["backup_time"]
                        + " §l*§r "
                        + format_dir_size(backup_info["backup_size"]).ljust(10)
                        + " §l*§r "
                        + (
                            tr("empty_comment")
                            if backup_info["backup_message"] is None
                            else backup_info["backup_message"]
                        )
                    )
                    + "\n",
                )
            else:
                break
        page_info = RTextList(
            RText("[<<] ", color=RColor.green)
            .h(tr("list_backup.previous_page.hits"))
            .c(
                RAction.run_command,
                f"{PREFIX} list {page_num-1}",
            ),
            RText(f" {page_num}/{int(len(all_backup_info) / LIST_PAGE_SIZE) + 1} "),
            RText("[>>] ", color=RColor.green)
            .h(tr("list_backup.previous_page.hits"))
            .c(
                RAction.run_command,
                f"{PREFIX} list {page_num+1}",
            ),
            "\n",
        )
        text += page_info
        text += RText(tr("list_backup.page.total_info", len(all_backup_info)))
        text += " "

    total_space_text = RText(
        tr(
            "list_backup.total_space",
            format_dir_size(
                get_dir_size(os.path.join(config.backup_data_path, CACHE_DIR))
            ),
        ),
    )
    print_message(
        source, header_text + text + total_space_text, prefix="", reply_source=True
    )


@new_thread("BB - help")
def print_help_message(source: CommandSource):
    if source.is_player:
        source.reply("")
    with source.preferred_language_context():
        for line in HelpMessage.to_plain_text().splitlines():
            prefix = re.search(r"(?<=§7){}[\w ]*(?=§)".format(PREFIX), line)
            if prefix is not None:
                print_message(
                    source,
                    RText(line).set_click_event(
                        RAction.suggest_command, prefix.group()
                    ),
                    prefix="",
                    reply_source=True,
                )
            else:
                print_message(source, line, prefix="", reply_source=True)
        print_message(
            source,
            tr("print_help.hotbar")
            + "\n"
            + RText(tr("print_help.click_to_create.text"))
            .h(tr("print_help.click_to_create.hover"))
            .c(
                RAction.suggest_command,
                tr("print_help.click_to_create.command", PREFIX).to_plain_text(),
            )
            + "\n"
            + RText(tr("print_help.click_to_restore.text"))
            .h(tr("print_help.click_to_restore.hover"))
            .c(
                RAction.suggest_command,
                tr("print_help.click_to_restore.command", PREFIX).to_plain_text(),
            ),
            prefix="",
            reply_source=True,
        )


@new_thread("BB - reset")
@single_op(tr("operations.reset"))
def reset_cache(source: CommandSource):
    print_message(source, tr("reset_backup.start"))
    backup_data_path = os.path.join(config.backup_data_path)
    rmtree(backup_data_path)
    os.makedirs(backup_data_path)
    init_folder(data_dir=backup_data_path)
    print_message(source, tr("reset_backup.success"))


@new_thread("BB - export")
@single_op(tr("operations.export"))
def export_backup(source: CommandSource, uuid: str):
    uuid_result = process_uuid(source, uuid)
    if uuid_result is None:
        return
    print_message(source, tr("export_backup.start"), reply_source=True)
    export_backup_util(
        uuid_result,
        metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
        cache_dir=os.path.join(config.backup_data_path, CACHE_DIR),
        dst_dir=os.path.join(config.backup_data_path, config.export_backup_folder),
    )
    print_message(
        source,
        tr(
            "export_backup.success",
            os.path.abspath(
                os.path.join(config.backup_data_path, config.export_backup_folder)
            ),
        ),
        reply_source=True,
    )


def register_command(server: PluginServerInterface):
    def get_literal_node(literal):
        lvl = config.minimum_permission_level.get(literal, 0)
        return (
            Literal(literal)
            .requires(lambda src: src.has_permission(lvl))
            .on_error(
                RequirementNotMet,
                lambda src: print_message(
                    src, tr("command.permission_denied"), reply_source=True
                ),
                handled=True,
            )
        )

    server.register_command(
        Literal(PREFIX)
        .runs(lambda src: print_help_message(src))
        .on_error(UnknownArgument, print_unknown_argument_message, handled=True)
        .then(
            get_literal_node("make")
            .runs(lambda src: create_backup(src, None))
            .then(
                GreedyText("message").runs(
                    lambda src, ctx: create_backup(src, ctx["message"])
                )
            )
        )
        .then(
            get_literal_node("restore")
            .runs(lambda src: restore_backup(src, None))
            .then(
                GreedyText("uuid").runs(
                    lambda src, ctx: restore_backup(src, ctx["uuid"])
                )
            )
        )
        .then(
            get_literal_node("remove")
            .runs(lambda src: remove_backup(src, None))
            .then(
                GreedyText("uuid").runs(
                    lambda src, ctx: remove_backup(src, ctx["uuid"])
                )
            )
        )
        .then(
            get_literal_node("list")
            .runs(lambda src: list_backups(src))
            .then(Integer("page").runs(lambda src, ctx: list_backups(src, ctx["page"])))
        )
        .then(get_literal_node("confirm").runs(confirm_restore))
        .then(get_literal_node("abort").runs(trigger_abort))
        .then(get_literal_node("reload").runs(load_config))
        .then(get_literal_node("help").runs(lambda src: print_help_message(src)))
        .then(get_literal_node("reset").runs(lambda src: reset_cache(src)))
        .then(
            get_literal_node("export")
            .runs(lambda src: export_backup(src, None))
            .then(
                GreedyText("uuid").runs(
                    lambda src, ctx: export_backup(src, ctx["uuid"])
                )
            )
        )
        .then(get_literal_node("export").runs(lambda src: export_backup(src)))
        .then(
            get_literal_node("timer")
            .runs(lambda src: show_timer_status(src))
            .then(Literal("enable").runs(lambda src: timer_set_enabled(src, True)))
            .then(Literal("disable").runs(lambda src: timer_set_enabled(src, False)))
            .then(
                Literal("set_interval").then(
                    Float("interval")
                    .at_min(0.1)
                    .runs(lambda src, ctx: timer_set_interval(src, ctx["interval"]))
                )
            )
            .then(Literal("reset").runs(lambda src: reset_timer(src)))
        )
    )


def on_load(server: PluginServerInterface, old):
    global operation_lock, server_inst, HelpMessage, timer, timer_run_flag
    server_inst = server
    load_config()
    if hasattr(old, "operation_lock") and type(old.operation_lock) == type(
        operation_lock
    ):
        operation_lock = old.operation_lock
    server.register_help_message(PREFIX, "Show the usage of Better Backup")

    meta = server.get_self_metadata()
    HelpMessage = tr("help_message", PREFIX, meta.name, meta.version)
    timer = Timer(server=server_inst)
    timer_set_enabled(
        server.get_plugin_command_source(), config.timer_enabled, echo_to_player=False
    )
    timer_run_flag = True
    timer_run(timer)
    init_folder(config.backup_data_path)
    register_command(server)
    server.logger.info("Better Backup Loaded!")


def on_info(server: PluginServerInterface, info: Info):
    if not info.is_user:
        if info.content in [
            "Saved the game",  # 1.13+
            "Saved the world",  # 1.12-
        ]:
            global game_saved
            game_saved = True


def on_unload(server):
    global abort_restore, timer_run_flag
    abort_restore = True
    timer_run_flag = False


def on_remove(server):
    global abort_restore, timer_run_flag
    abort_restore = True
    timer_run_flag = False
