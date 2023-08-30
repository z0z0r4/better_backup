**中文** | [English](README_en.md)

# Better_Backup

> [!WARNING]
> **Better Backup 目前正处于试验阶段。强烈建议您不要在生产环境使用，并做好重要数据备份。**  
> 在报告问题前，请留意您正使用的是否为最新版本。

一个高效备份回档、更少磁盘占用、避免重复文件的 MCDR 插件。

![image](https://github.com/z0z0r4/better_backup/assets/45303195/1f586ea7-a7f2-456d-bc19-09eade53f798)

> [!IMPORTANT]
> v2.0.0 起使用 SQlite 不兼容以前版本的 JSON 备份数据  
> v2.1.0 起使用 xxHash 不兼容以前版本的哈希数据  
> **请使用[迁移脚本](https://github.com/z0z0r4/better_backup/blob/main/scripts/migrate.py)，或在旧版本提前清除 `better_backup` 文件夹内所有数据**

## 特性

- 避免重复文件，比 [QuickBackupM](https://github.com/TISUnion/QuickBackupM) 节省 20% ~ 90% 备份空间  
  对于大存档和读写性能低下的硬盘，速度显著优于 [QuickBackupM](https://github.com/TISUnion/QuickBackupM) ([基准测试](https://github.com/z0z0r4/better_backup/issues/5))
- 内置定时备份
- 支持 zstd 压缩，额外节省 50% 以上备份空间，且不影响回档速度
- xxHash 计算哈希值，节省 20% ~ 70% 运算时间
- 支持自动删除过旧备份，保留指定数量的备份
- 轻松导出完整备份

---

备份的存档将会存放至 `better_backup` 文件夹中，文件目录格式如下：
```python
mcd_root/
    better_backup/
        cache/ # 备份文件
            00/
                ...
            0a/
            0b/
            ...

        export_backup/ # 导出
            ...

        overwrite/ # 留底
            ...
        
        storage.db # 数据库
```

## 命令格式说明

`!!bb` 显示帮助信息

`!!bb make [<message>]` 创建备份。`<message>` 为可选存档注释

`!!bb restore [<uuid|index>]` 回档为槽位 `<uuid|index>` 的存档

`!!bb remove [<uuid|index>]` 删除槽位 `<uuid|index>` 的存档

`!!bb confirm` 在执行 `!!bb restore [<uuid|index>]` 后使用，再次确认是否进行回档

`!!bb abort` 在任何时候键入此指令可中断回档

`!!bb list [<page>]` 显示分页存档信息，默认为第一页

`!!bb reload` 重新加载配置文件

`!!bb reset` 重置存档数据

`!!bb export [<uuid|index>] [plain|tar|tar_gz|tar_xz] [compress_level]` 导出备份数据

`!!bb lock [<uuid|index>]` 锁定或解锁备份点。锁定的备份点将在自动删除时被忽略，不计入数量限制中

当 `<uuid|index>` 未设置或为 1 时为最新备份点的 uuid

如 `2` 为由新到旧的第二个备份点，此处不考虑 `page`，需自行计算

`!!bb timer` 显示定时器状态

`!!bb timer enable` 启动备份定时器

`!!bb timer disable` 关闭备份定时器

`!!bb timer set_interval §6<minutes>` 设置备份定时器时间间隔，单位分钟

`!!bb timer reset` 重置备份定时器

## 配置文件选项说明

配置文件为 `config/better_backup.json`。它会在第一次运行时自动生成，默认值如下（不支持注释）：

```json5
{
    "size_display": true, // 是否显示文件大小信息
    "turn_off_auto_save": true, // 是否关闭自动保存
    "ignored_files": [ // 不备份的文件
        "session.lock"
    ],
    "ignored_folders": [], // 不备份的目录
    "ignored_extensions": [ // 不备份的扩展名
        ".lock"
    ],
    "world_names": [ // 要备份的世界列表
        "world"
    ],
    "save_command": {
        "save-off": "save-off",
        "save-all flush": "save-all flush",
        "save-on": "save-on"
    },
    "saved_output": [
        "Saved the game",
        "Saved the world"
    ],
    "backup_data_path": "./better_backup", // 备份路径
    "server_path": "./server", // 服务端位置
    "overwrite_backup_folder": "overwrite", // 覆盖备份文件夹名称
    "backup_compress_level": 3, // 备份 zst 压缩等级 (1~22)，为 0 时禁用
    "export_backup_folder": "./export_backup", // 备份导出路径
    "export_backup_format": "tar_gz", // 备份导出格式 (plain, tar, tar_gz, tar_xz)
    "export_backup_compress_level": 1, // 备份压缩等级
    "auto_remove": true, // 自动删除旧备份
    "backup_count_limit": 20, // 备份留存数量
    "minimum_permission_level": { // MCDR 指令权限等级
        "make": 1, // 创建
        "restore": 2, // 回档
        "remove": 2, // 删除
        "confirm": 1, // 确认
        "abort": 1, // 终止
        "reload": 2, // 重载
        "list": 0, // 查看列表
        "reset": 2, // 重置
        "timer": 2, // 操作定时器
        "export": 4 // 导出
    },
    "timer_enabled": true, // 是否启用定时备份
    "timer_interval": 5.0 // 定时间隔
}
```

## Todo list

已基本完成，目前主要进行 Bug 修复

以下 TODO 优先级从高到低

- [x] 支持锁定指定备份不被自动删除
- [x] 文件链接处理
- [x] SQlite 支持
- [x] 导出支持 `.tar.zst`
- [x] xxHash
- [ ] 忽略文件/目录时支持通配符
- [ ] 备份和还原文件 stat

## Won't do

- [ ] ~~云备份，包括各家对象存储和 WebDav，不考虑无接口官方 API 网盘~~
- [ ] ~~多盘备份，将备份同步保存到多个路径~~
- [ ] ~~支持 Diff 备份数据库~~
- [ ] ~~支持修改备份点注释~~
