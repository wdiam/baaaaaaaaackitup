#!/usr/bin/env python3

from baaaaaaaaackitup import BackupManager
import configparser

# Load config
config = configparser.ConfigParser()
config.read('config.ini')

# Create manager
manager = BackupManager(
    backup_dirs=config.get('Backup', 'backup_dirs').strip().split('\n'),
    dest_dir=config.get('Backup', 'dest_dir'),
    backup_file_base=config.get('Backup', 'backup_file_base'),
    password_file=config.get('Backup', 'password_file'),
    max_backups=config.getint('Backup', 'max_backups'),
    preserve_levels=config.getint('Backup', 'preserve_levels', fallback=2)  # Default to 2 if not specified
)

# Run backup
manager.perform_backup()
