import os
import time
from math import ceil
from shutil import rmtree
from typing import Optional

from mcdreforged.api.all import *

from better_backup.config import config
from better_backup.constants import (LIST_PAGE_SIZE, PREFIX,
                                     server_inst)
from better_backup.database import database, load_database
from better_backup.timer import timer
from better_backup.utils import *

game_saved = False
selected_uuid = None
restore_aborted = False


def init_structure(data_dir: str):
    """initialize cache and meta folder"""
    if not os.path.exists(os.path.join(data_dir, CACHE_DIR)):
        os.makedirs(os.path.join(data_dir, CACHE_DIR))
        for i in range(256):
            os.makedirs(
                os.path.join(data_dir, CACHE_DIR, format(i, "02X").lower()),
                exist_ok=True,
            )
    load_database()


def trigger_abort(source: CommandSource):
    global restore_aborted, selected_uuid
    restore_aborted = True
    selected_uuid = None
    print_message(source, "Operation terminated!", reply_source=True)


def game_save_triggered():
    global game_saved
    game_saved = True


def get_uuid(source: CommandSource, keyword: str = None):
    if keyword is None:  # get latest one
        uuid = get_backups(orderby=~database.backups.time)[0].uuid
    elif len(keyword) == 6:  # get by uuid
        uuid = get_backup_row(keyword).uuid
    else:  # get by index
        try:
            index = int(keyword)
            if 0 < index <= config.backup_count_limit:
                uuid = get_backups(orderby=~database.backups.time)[
                    index - 1].uuid
        except:
            uuid = None
    if not uuid:
        print_message(source, tr("unknown_backup"), reply_source=True)
    return uuid


@new_thread(thread_name("create_backup"))
def create_backup(source: CommandSource, message: Optional[str] = None):
    do_create(source, message)


@single_op(tr("operations.create"))
def do_create(source: CommandSource, message: Optional[str] = None):
    global game_saved

    print_message(source, tr("create_backup.start"))
    start_time = time.time()

    # start backup
    game_saved = False
    if config.turn_off_auto_save:
        source.get_server().execute(config.save_command["save-off"])
    source.get_server().execute(config.save_command["save-all flush"])
    while True:
        time.sleep(0.01)
        if game_saved:
            break

    try:
        backup_info = create_backup_util(
            *config.world_names,
            cache_dir=os.path.join(config.backup_data_path, CACHE_DIR),
            message=message,
            src_path=config.server_path,
            config=config,
        )
        print_message(
            source,
            tr(
                "create_backup.success",
                backup_info.uuid,
                round(time.time() - start_time, 1),
                "§l*§r {0} §l*§r {1}".format(
                    format_dir_size(backup_info.size), message
                ),
            ),
        )

        # remove oldest backup if reached max count
        timer.on_backup_created(backup_uuid=backup_info.uuid)
        if config.auto_remove:
            removed_uuids = auto_remove_util(
                limit=config.backup_count_limit,
            )
            if len(removed_uuids) == 0:
                print_message(source, tr("auto_remove.no_one_removed"))
            else:
                print_message(
                    source, tr("auto_remove.removed",
                               " §l*§r ".join(removed_uuids))
                )

    except ModuleNotFoundError as e:
        print_message(source, tr("create_backup.fail", e))
    finally:
        if config.turn_off_auto_save:  # ! reopen autosave
            source.get_server().execute(config.save_command["save-on"])


@new_thread(thread_name("remove_backup"))
@single_op(tr("operations.remove"))
def remove_backup(
    source: CommandSource, kw: Optional[str] = None, index: Optional[int] = None
):
    uuid_result = get_uuid(source, kw)
    if uuid_result is None:
        print_message(source, tr("unknown_backup"))
        return

    remove_backup_util(backup_uuid=uuid_result)
    print_message(source, tr("remove_backup.success", uuid_result))


def restore_backup(source: CommandSource, kw: Optional[str] = None):
    global selected_uuid, restore_aborted
    restore_aborted = False
    selected_uuid = get_uuid(source, kw)
    if selected_uuid is None:
        return
    # uuid_selected = uuid

    print_message(source, tr("restore_backup.echo_action", selected_uuid))
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


@new_thread(thread_name("restore_backup"))
@single_op(tr("operations.confirm"))
def confirm_restore(source: CommandSource):
    # !!bb confirm
    global selected_uuid, restore_aborted
    if selected_uuid is None:
        print_message(
            source, tr("confirm_restore.nothing_to_confirm"), reply_source=True
        )
        return
    # !!bb abort
    print_message(source, tr("do_restore.countdown.intro"))
    for countdown in range(1, 10):
        print_message(
            source,
            command_run(
                tr(
                    "do_restore.countdown.text",
                    10 - countdown,
                    selected_uuid,
                ),
                tr("do_restore.countdown.hover"),
                "{} abort".format(PREFIX),
            ),
        )
        for _ in range(3):
            time.sleep(0.1)
            if restore_aborted:
                print_message(source, tr("do_restore.abort"))
                return
    operation_lock.release()
    do_restore(source)


@single_op(tr("operations.restore"))
def do_restore(source: CommandSource):
    global selected_uuid
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
        server_inst.logger.info(f"Restore backup §e{selected_uuid}§r")

        backup_info = restore_backup_util(
            backup_uuid=selected_uuid,
            dst_dir=config.server_path,
        )
        source.get_server().start()
        print_message(source, tr("restore_backup.success",
                      backup_info.uuid))
    except:
        server_inst.logger.exception(
            tr(
                "restore_backup.fail",
                selected_uuid,
                source,
            )
        )
        restore_temp(
            config.world_names,
            os.path.join(config.backup_data_path,
                         config.overwrite_backup_folder),
            config,
        )
    finally:
        clear_temp(
            temp_dir=os.path.join(
                config.backup_data_path, config.overwrite_backup_folder
            )
        )
        selected_uuid = None


def list_backups(source: CommandSource, page_num: int = 1):
    all_backup_info = get_backups(orderby=~database.backups.time) or []
    if len(all_backup_info) == 0:
        text = RTextList(tr("no_one_backup") + "\n")
        header_text = tr("list_backup.title") + "\n"
    elif LIST_PAGE_SIZE * (page_num - 1) >= len(all_backup_info) or page_num <= 0:
        print_message(source, tr(
            "list_backup.page.page_not_found"), reply_source=True)
        return
    else:
        text = RTextList()
        header_text = tr("list_backup.title") + "\n"
        for _i in range(((page_num - 1) * LIST_PAGE_SIZE), page_num * LIST_PAGE_SIZE):
            if _i <= (len(all_backup_info) - 1):
                backup_info = all_backup_info[_i]
                text += RTextList(
                    RText(
                        f'[§e{str((_i+1)).zfill(len(str(LIST_PAGE_SIZE)))}§r] [§e{backup_info.uuid}§r] '
                    ),
                    RText("[▷] ", color=RColor.green)
                    .h(tr("list_backup.restore_hint", backup_info.uuid))
                    .c(
                        RAction.suggest_command,
                        f'{PREFIX} restore {backup_info.uuid}',
                    ),
                    RText("[x] ", color=RColor.green)
                    .h(tr("list_backup.remove_hint", backup_info.uuid))
                    .c(
                        RAction.suggest_command,
                        f'{PREFIX} remove {backup_info.uuid}',
                    ),
                    RText(
                        f'{time.strftime(r"%Y-%m-%d %H:%M:%S", time.localtime(backup_info.time))}  §l*§r {format_dir_size(backup_info.size).ljust(10)} §l*§r '
                        + tr("empty_comment") if backup_info.message is None else backup_info.message
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
            RText(f" {page_num}/{ceil(len(all_backup_info) / LIST_PAGE_SIZE)} "),
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
        text += " §l*§r "

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


@new_thread(thread_name("reset_cache"))
@single_op(tr("operations.reset"))
def reset_cache(source: CommandSource):
    print_message(source, tr("reset_backup.start"))
    # database.close()
    rmtree(config.backup_data_path)
    init_structure(config.backup_data_path)
    print_message(source, tr("reset_backup.success"))


@new_thread(thread_name("export_backup"))
@single_op(tr("operations.export"))
def export_backup(
    source: CommandSource,
    uuid: Optional[str] = None,
    format: Optional[str] = None,
    compress_level: Optional[int] = None,
):
    uuid_result = get_uuid(source, uuid)
    if uuid_result is None:
        return
    print_message(source, tr("export_backup.start"), reply_source=True)

    output_path = export_backup_util(
        uuid_result,
        output_dir=os.path.join(config.backup_data_path,
                                config.export_backup_folder),
        export_format=ExportFormat.of(format)
        if format is not None
        else ExportFormat.of(config.export_backup_format),
        compress_level=compress_level
        if compress_level is not None
        else config.export_backup_compress_level,
    )
    print_message(
        source,
        tr(
            "export_backup.success",
            os.path.abspath(output_path),
        ),
        reply_source=True,
    )
