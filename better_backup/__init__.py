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

SRC_DIR = "src"
METADATA_DIR = "metadata"
CACHE_DIR = "cache"
TEMP_DIR = "temp"

PREFIX = "!!bb"

CONFIG_FILE = os.path.join("config", "Better_Backup.json")
operation_lock = Lock()
operation_name = RText("?")
game_saved = False
uuid_selected = None
abort_restore = False


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





def format_dir_size(size: int) -> str:
    if size < 2**30:
        return "{} MB".format(round(size / 2**20, 2))
    else:
        return "{} GB".format(round(size / 2**30, 2))

def tr(translation_key: str, *args) -> RTextMCDRTranslation:
    return ServerInterface.get_instance().rtr(
        "better_backup.{}".format(translation_key), *args
    )

def command_run(message: Any, text: Any, command: str) -> RTextBase:
    fancy_text = message.copy() if isinstance(message, RTextBase) else RText(message)
    return fancy_text.set_hover_text(text).set_click_event(RAction.run_command, command)

def print_message(source: CommandSource, msg, tell=True, prefix="§a[Better Backup]§r "):
    msg = RTextList(prefix, msg)
    if source.is_player and not tell:
        source.get_server().say(msg)
    else:
        source.reply(msg)

def print_unknown_argument_message(source: CommandSource, error: UnknownArgument):
	print_message(source, command_run(
		tr('unknown_command.text', PREFIX),
		tr('unknown_command.hover'),
		PREFIX
    ))

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
                print_message(source, tr("lock.warning", operation_name))

        return wrap

    return wrapper





def trigger_abort(source: CommandSource):
    global abort_restore, uuid_selected
    abort_restore = True
    uuid_selected = None
    print_message(source, "Operation terminated!", tell=False)


def load_config():
    global config
    config = server_inst.load_config_simple(
        CONFIG_FILE,
        target_class=Configuration,
        in_data_folder=False,
        source_to_reply=None,
    )


def on_load(server: PluginServerInterface, old):
    global operation_lock, server_inst, HelpMessage
    server_inst = server
    load_config()
    if hasattr(old, "operation_lock") and type(old.operation_lock) == type(
        operation_lock
    ):
        operation_lock = old.operation_lock
    server.register_help_message(PREFIX, "Show the usage of Better Backup")

    meta = server.get_self_metadata()
    HelpMessage = tr("help_message", PREFIX, meta.name, meta.version)

    init_folder(config.backup_data_path)
    register_command(server)
    server.logger.info("Better Backup Loaded!")


def register_command(server: PluginServerInterface):
    def get_literal_node(literal):
        lvl = config.minimum_permission_level.get(literal, 0)
        return (
            Literal(literal)
            .requires(lambda src: src.has_permission(lvl))
            .on_error(
                RequirementNotMet,
                lambda src: src.reply(tr("command.permission_denied")),
                handled=True,
            )
        )

    server.register_command(
        Literal(PREFIX)
        .runs(print_help_message)
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
        .then(get_literal_node("list").runs(lambda src: list_backups(src)))
        .then(get_literal_node("confirm").runs(confirm_restore))
        .then(get_literal_node("abort").runs(trigger_abort))
        .then(get_literal_node("reload").runs(load_config))
        .then(get_literal_node("help").runs(lambda src: print_help_message(src)))
        .then(get_literal_node("reset").runs(lambda src: reset_cache(src)))
    )





@new_thread("BB - create")
@single_op(tr("operations.create"))
def create_backup(source: CommandSource, message: Optional[str]):
    print_message(source, tr("create_backup.start"), tell=False)
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
        tell=False,
    )
    if config.turn_off_auto_save:
        source.get_server().execute("save-on")


@new_thread("BB - remove")
@single_op(tr("operations.remove"))
def remove_backup(source: CommandSource, uuid: Optional[str]):
    if uuid is None:
        uuid = get_latest_backup_uuid(
            os.path.join(config.backup_data_path, METADATA_DIR)
        )
        if uuid is None:
            print_message(source, tr("no_one_backup"))
            return
    elif not check_backup_uuid_available(
        backup_uuid=uuid,
        metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
    ):
        print_message(source, tr("unknown_slot", uuid))

    all_backup_info = get_all_backup_info(
        metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR)
    )
    for backup_info in all_backup_info:
        if uuid == backup_info["backup_uuid"]:
            remove_backup_util(
                backup_uuid=uuid,
                metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
                cache_dir=os.path.join(config.backup_data_path, CACHE_DIR),
            )
    print_message(source, tr("remove_backup.success", uuid), tell=False)


def restore_backup(source: CommandSource, uuid: Optional[str]):
    global uuid_selected, abort_restore
    abort_restore = False
    if uuid is None:
        uuid = get_latest_backup_uuid(
            os.path.join(config.backup_data_path, METADATA_DIR)
        )
        if uuid is None:
            print_message(source, tr("no_one_backup"))
            return
        uuid_selected = uuid
    elif check_backup_uuid_available(
        backup_uuid=uuid,
        metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
    ):
        uuid_selected = uuid
    else:
        print_message(source, tr("unknown_slot", uuid))
        return
    print_message(source, tr("restore_backup.echo_action", uuid_selected), tell=False)
    text = RTextList(
        RText(tr("restore_backup.confirm_hint", PREFIX))
        .h(tr("restore_backup.confirm_hover"))
        .c(
            RAction.suggest_command,
            f'{PREFIX} confirm',
        ),
        ", ",
        RText(tr("restore_backup.abort_hint", PREFIX))
        .h(tr("restore_backup.abort_hover"))
        .c(
            RAction.suggest_command,
            f'{PREFIX} abort',
        ),
    )
    print_message(
        source,
        text,
        tell=False,
    )


@new_thread("BB - restore")
def confirm_restore(source: CommandSource):
    # !!bb confirm
    global uuid_selected
    if uuid_selected is None:
        print_message(source, tr("confirm_restore.nothing_to_confirm"))
        return
    # !!bb abord
    print_message(source, tr("do_restore.countdown.intro"), tell=False)
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
            tell=False,
        )
        for i in range(10):
            time.sleep(0.1)
            global abort_restore
            if abort_restore:
                print_message(source, tr("do_restore.abort"), tell=False)
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
            temp_dir=os.path.join(config.backup_data_path, TEMP_DIR),
            src_path=config.server_path,
        )
        server_inst.logger.info(f"Restore backup {uuid_selected}")

        backup_info = restore_backup_util(
            backup_uuid=uuid_selected,
            metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR),
            dst_dir=config.server_path,
            config=config,
        )
        source.get_server().start()
        print_message(
            source, tr("restore_backup.success", backup_info["backup_uuid"]), tell=False
        )
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
            os.path.join(config.backup_data_path, TEMP_DIR),
            config.server_path,
        )
    uuid_selected = None


def list_backups(source: CommandSource):
    all_backup_info = get_all_backup_info_sort_by_timestamp(
        metadata_dir=os.path.join(config.backup_data_path, METADATA_DIR)
    )
    if len(all_backup_info) == 0:
        text = RTextList(tr("no_one_backup") + "\n")
        header_text = tr("list_backup.title") + "\n"
    else:
        text = RTextList()
        header_text = tr("list_backup.title") + "\n"
        for backup_info in all_backup_info:
            text += RTextList(
                RText(f'[§e{backup_info["backup_uuid"]}§r] '),
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
    total_space_text = RText(
        tr(
            "list_backup.total_space",
            format_dir_size(
                get_dir_size(os.path.join(config.backup_data_path, CACHE_DIR))
            ),
        ),
    )
    print_message(source, header_text + text + total_space_text, prefix="")


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
                )
            else:
                print_message(source, line, prefix="")
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
        )


@new_thread("BB - reset")
@single_op(tr("reset_backup.start", "§cReseting§r"))
def reset_cache(source: CommandSource):
    print_message(source, tr("reset_backup.start"), tell=False)
    backup_data_path = os.path.join(config.backup_data_path)
    rmtree(backup_data_path)
    os.makedirs(backup_data_path)
    init_folder(data_dir=backup_data_path)
    print_message(source, tr("reset_backup.success"), tell=False)

def on_info(server: PluginServerInterface, info: Info):
    if not info.is_user:
        if info.content in [
            "Saved the game",  # 1.13+
            "Saved the world",  # 1.12-
        ]:
            global game_saved
            game_saved = True
            
def on_unload(server):
	global abort_restore
	abort_restore = True