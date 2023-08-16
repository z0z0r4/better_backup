import re

from mcdreforged.api.all import *

from better_backup.config import config
from better_backup.constants import OLD_METADATA_DIR, PREFIX, server_inst
from better_backup.database import database
from better_backup.operations import (confirm_restore, create_backup,
                                      export_backup, init_structure,
                                      list_backups, operation_lock,
                                      remove_backup, reset_cache,
                                      restore_backup, trigger_abort)
from better_backup.timer import timer
from better_backup.utils import *


def print_unknown_argument_message(source: CommandSource, error: UnknownArgument):
    print_message(
        source,
        command_run(
            tr("unknown_command.text", PREFIX), tr(
                "unknown_command.hover"), PREFIX
        ),
        reply_source=True,
    )


# @new_thread(thread_name("help"))
def print_help_message(source: CommandSource):
    meta = server_inst.get_self_metadata()
    msg = tr("help_message", PREFIX, meta.name, meta.version)
    if source.is_player:
        source.reply("")
    with source.preferred_language_context():
        for line in msg.to_plain_text().splitlines():
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
            .runs(lambda src: create_backup(src))
            .then(
                GreedyText("message").runs(
                    lambda src, ctx: create_backup(src, ctx["message"])
                )
            )
        )
        .then(
            get_literal_node("restore")
            .runs(lambda src: restore_backup(src))
            .then(Text("uuid|index").runs(lambda src, ctx: restore_backup(src, ctx["uuid|index"])))
        )
        .then(
            get_literal_node("remove")
            .runs(lambda src: remove_backup(src))
            .then(Text("uuid|index").runs(lambda src, ctx: remove_backup(src, ctx["uuid|index"])))
        )
        .then(
            get_literal_node("list")
            .runs(lambda src: list_backups(src))
            .then(
                Integer("page")
                .at_min(1)
                .runs(lambda src, ctx: list_backups(src, ctx["page"]))
            )
        )
        .then(get_literal_node("confirm").runs(confirm_restore))
        .then(get_literal_node("abort").runs(trigger_abort))
        .then(
            get_literal_node("reload").runs(
                lambda src: src.get_server().reload_plugin("better_backup")
            )
        )
        .then(get_literal_node("help").runs(lambda src: print_help_message(src)))
        .then(get_literal_node("reset").runs(lambda src: reset_cache(src)))
        .then(
            get_literal_node("export")
            .runs(lambda src: export_backup(src))
            .then(
                Text("uuid")
                .runs(lambda src, ctx: export_backup(src, ctx["uuid"]))
                .then(
                    Enumeration("format", ExportFormat)
                    .runs(
                        lambda src, ctx: export_backup(
                            src, ctx["uuid"], ctx["format"])
                    )
                    .then(
                        Integer("compress_level")
                        .at_min(1)
                        .at_max(9)
                        .runs(
                            lambda src, ctx: export_backup(
                                src, ctx["uuid"], ctx["format"], ctx["compress_level"]
                            )
                        )
                    )
                )
            )
        )
        .then(
            get_literal_node("timer")
            .runs(lambda src: timer.show_status(src))
            .then(Literal("enable").runs(lambda src: timer.set_status(src, True)))
            .then(Literal("disable").runs(lambda src: timer.set_status(src, False)))
            .then(
                Literal("set_interval").then(
                    Float("interval")
                    .at_min(0.1)
                    .runs(lambda src, ctx: timer.set_interval(src, ctx["interval"]))
                )
            )
            .then(Literal("reset").runs(lambda src: timer.reset(src)))
        )
    )


def on_info(server: PluginServerInterface, info: Info):
    if not info.is_user:
        if info.content in config.saved_output:
            global game_saved
            game_saved = True


def on_load(server: PluginServerInterface, old):
    global operation_lock
    if hasattr(old, "operation_lock") and type(old.operation_lock) == type(
        operation_lock
    ):
        operation_lock = old.operation_lock
    if os.path.isdir(os.path.join(config.backup_data_path, OLD_METADATA_DIR)):
        raise MetadataError(tr("metadata_conflict"))
    server.register_help_message(PREFIX, tr("help_title"))

    init_structure(config.backup_data_path)
    register_command(server)
    server.logger.info("Better Backup Loaded!")


def on_unload(server):
    on_remove(server)


def on_remove(server: PluginServerInterface):
    trigger_abort(server.get_plugin_command_source())
    database.close()
    timer.stop()
