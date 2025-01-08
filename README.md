# baaaaaaaaackitup

A backup utility designed for homelab setups, with special emphasis on safely handling SQLite databases.

## Features

- Automatic safe backup of SQLite databases using SQLite's backup API
- Special handling for Plex (databases only, skips media files)
- Configurable backup rotation
- Compression with parallel gzip (pigz) when available
- GPG encryption of backups
- Configurable directory structure preservation

## Safety Features

- Automatic SQLite database detection and verification
- Size monitoring to detect abnormal compression or backup issues
- Permission error tracking and warnings
- Comprehensive logging of backup operations
- Optional use of atomic operations for database backups

## Configuration

Copy `config.ini.example` to `config.ini` and modify:

```ini
[Backup]
backup_dirs = 
    /path/to/first/dir
    /path/to/second/dir
dest_dir = /path/to/backup/storage
backup_file_base = my_backup
password_file = /path/to/encryption/key
max_backups = 10
preserve_levels = 2

[Plex]
enabled = true
dir = /path/to/plex
```

## Usage

### Backup
```bash
./run_backup.py
```

### Restore
```bash
./run_restore.py
```

## Requirements

- Python 3.8+
- GPG for encryption
- pigz (optional, for parallel compression)

## How It Works

1. Scans configured directories for backup
2. Automatically detects and safely backs up SQLite databases
3. For Plex, only backs up essential databases (when enabled)
4. Creates a compressed, encrypted tar archive
5. Rotates old backups based on configuration

## Notes

- SQLite databases are automatically detected and backed up using SQLite's backup API to ensure data integrity
- Regular files are added directly to the backup
- File sizes are monitored during backup to detect potential issues
- Warning logs track any skipped files or permission issues