[中文](README.md) | **English**

# Better_Backup

An MCDR plugin for efficient backup and restore, with less disk usage and no duplicate files.

! [image](https://github.com/z0z0r4/better_backup/assets/45303195/1f586ea7-a7f2-456d-bc19-09eade53f798)

> ⚠️ **Warning:**  
> Version >=2.0.0 does not compatible with old JSON backup data from previous versions.  
> Version >=2.1.0 does not compatible with old HASH data from previous versions.  
> **Please [migrate](https://github.com/z0z0r4/better_backup/blob/main/scripts/migrate.py), or clear all data in `better_backup`before updating**.

## Features

- Avoid duplicate files, save 20% ~ 90% backup space compared to [QuickBackupM](https://github.com/TISUnion/QuickBackupM).  
  Significantly outperforms [QuickBackupM](https://github.com/TISUnion/QuickBackupM) for large backups and HHD.
- Built-in timed backups
- Supports zstd compression, which saves extra 50% backup space without affecting archive speed.
- xxHash for hash values, saving 20% ~ 70% of computing time.
- Supports automatic deletion of old backups and retaining the specified number of backups.
- Easily export full backups

---

The backup archive will be stored in the `better_backup` folder with the following directory format:
```python
mcd_root/
    better_backup/
        cache/ # Backup files
            00/
                ...
            0a/
            0a/ ... 0b/
            ...

        export_backup/
            ...

        overwrite/
            ...
        
        storage.db # database
```

## Configuration

The configuration file is `config/better_backup.json`. It will be automatically generated the first time it's run, with the following default values (comments are not really supported):

## 配置文件选项说明

配置文件为 `config/better_backup.json`。它会在第一次运行时自动生成，默认值如下（不支持注释）：

```json5
{
    "size_display": true,
    "turn_off_auto_save": true,
    "ignored_files": [
        "session.lock"
    ],
    "ignored_folders": [],
    "ignored_extensions": [
        ".lock"
    ],
    "world_names": [
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
    "backup_data_path": "./better_backup",
    "server_path": "./server",
    "overwrite_backup_folder": "overwrite",
    "backup_compress_level": 3, // 1~22
    "export_backup_folder": "./export_backup",
    "export_backup_format": "tar_gz", // plain, tar, tar_gz, tar_xz
    "export_backup_compress_level": 1,
    "auto_remove": true,
    "backup_count_limit": 20,
    "minimum_permission_level": {
        "make": 1,
        "restore": 2,
        "remove": 2,
        "confirm": 1,
        "abort": 1,
        "reload": 2,
        "list": 0,
        "reset": 2,
        "timer": 2,
        "export": 4
    },
    "timer_enabled": true,
    "timer_interval": 5.0
}
```
