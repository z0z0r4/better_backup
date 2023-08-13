# Better_Backup

更少的磁盘占用，永远不会有重复文件。

一个支持文件去重的高效备份/回档 MCDR 插件

![image](https://github.com/z0z0r4/better_backup/assets/78744121/7a5464d0-229b-47bf-aa8a-9abb02dd1f5c)

## 特性

- 无数备份点只占用不到两个存档的空间，只取决于服务器活跃程度而非备份频率
- 自带定时器，无需单独安装插件
- zstd 压缩，节省一半空间，毫不影响回档速度
- 支持自动删除过旧备份，只保留指定数量的备份
- 轻松导出备份为压缩包
- 针对大存档和读写性能低下的机械硬盘，速度显著快于 [QuickBackupM](https://github.com/TISUnion/QuickBackupM) [基准测试](https://github.com/z0z0r4/better_backup/issues/5)

---

备份的存档将会存放至 `better_backup` 文件夹中，文件目录格式如下：
```
mcd_root/
    better_backup/
        cache/
            ...

        metadata/
            ...

        export_backup/
            ...

        overwrite/
            world/
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

当 `<uuid|index>` 未设置或为 1 时为最新备份点的 uuid

如 `2` 为由新到旧的第二个备份点

但此处 `index` 不考虑 `page`，请自行计算

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
    "backup_data_path": "./better_backup", // 备份路径
    "server_path": "./server", // 服务端位置
    "overwrite_backup_folder": "overwrite", // 覆盖备份文件夹名称
    "backup_compress_level": 3, // 备份压缩等级 (1~22)，为 0 时禁用
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

## TODO
以下 TODO 优先级从高到低，可遇见的是不会实现
- [ ] 支持锁定指定备份不被自动删除
- [ ] 支持修改备份点注释
- [ ] 文件链接处理
- [ ] SQlite 支持
- [ ] 备份点还原文件 stat
- [ ] 支持正则忽略文件/目录
- [ ] 补完 xxHash 功能 [Branch xxHash](https://github.com/z0z0r4/better_backup/tree/xxhash)
- [ ] 云备份，包括各家对象存储和 WebDav，不考虑无接口官方 API 网盘
- [ ] 多盘备份，将备份同步保存到多个路径
- [ ] 支持 Diff 备份数据库
