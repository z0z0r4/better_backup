# Better_Backup
Less disk usage, never duplicate files

更少的磁盘占用，永远不会有重复文件。

A plugin that supports efficient backup/rollback with file deduplication

一个支持文件去重的高效备份/回档 MCDR 插件

![image](https://github.com/z0z0r4/better_backup/assets/78744121/7a5464d0-229b-47bf-aa8a-9abb02dd1f5c)

备份的存档将会存放至 `better_backup` 文件夹中，文件目录格式如下：
```
mcd_root/
    server.py

    server/
        world/

    better_backup/
        cache/
            ...
        metadata/
            ...

        temp/
            world/
```


## 命令格式说明

`!!bb` 显示帮助信息

`!!bb make [<message>]` 创建备份。`<message>` 为可选存档注释

`!!bb restore [<uuid>]` 回档为槽位 `<uuid>` 的存档

`!!bb remove [<uuid>]` 删除槽位 `<uuid>` 的存档

`!!bb confirm` 在执行 `!!bb restore [<uuid>]` 后使用，再次确认是否进行回档

`!!bb abort` 在任何时候键入此指令可中断回档

`!!bb list` 显示所有存档信息

`!!bb reload` 重新加载配置文件

`!!bb reset` 重置存档数据

当 `<uuid>` 未被指定时默认选择最新备份

## 配置文件选项说明

配置文件为 `config/better_backup.json`。它会在第一次运行时自动生成

## `size_display` 

默认值: `True`

控制是否显示文件大小信息。

## `turn_off_auto_save` 

默认值: `True`

控制是否关闭自动保存功能。

## `ignored_files` 

默认值: `["session.lock"]`

指定要忽略的文件列表。

## `ignored_folders` 

默认值: `[]`

指定要忽略的文件夹列表。

## `ignored_extensions` 

默认值: `[".lock"]`

指定要忽略的文件扩展名列表。

## `world_names` 

默认值: `['world']`

指定世界名称列表。

## `backup_data_path` 

默认值: `"./better_backup"`

指定备份数据的路径。

## `server_path` 

默认值: `"./server"`

指定服务器路径。

## `overwrite_backup_folder` 

默认值: `"overwrite"`

指定覆盖备份文件夹名称。

## `minimum_permission_level` 

默认值: 
```json
{
  "make": 1,
  "restore": 2,
  "remove": 2,
  "confirm": 1,
  "abort": 1,
  "reload": 2,
  "list": 0,
  "reset": 2
}
```

指定各操作的最低权限级别要求。

- `make`: 创建备份操作所需的最低权限级别。
- `restore`: 恢复备份操作所需的最低权限级别。
- `remove`: 删除备份操作所需的最低权限级别。
- `confirm`: 确认操作所需的最低权限级别。
- `abort`: 取消操作所需的最低权限级别。
- `reload`: 重新加载操作所需的最低权限级别。
- `list`: 列出操作所需的最低权限级别。
- `reset`: 重置操作所需的最低权限级别。

Based on [QuickBackupM](https://github.com/TISUnion/QuickBackupM)
