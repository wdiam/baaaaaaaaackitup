#!/usr/bin/env python3

from baaaaaaaaackitup import BackupManager
from baaaaaaaaackitup.plex_backup import PlexBackupHandler
import configparser
import os
from pathlib import Path

# Load config
config = configparser.ConfigParser()
script_dir = Path(__file__).parent
config.read(script_dir / 'config.ini')

# Set up paths
dest_dir = Path(config.get('Backup', 'dest_dir'))
warning_log = dest_dir / 'backup_warnings.log'

# Initialize Plex handler if enabled
plex_handler = None
if 'Plex' in config and config.getboolean('Plex', 'enabled', fallback=False):
    plex_handler = PlexBackupHandler(
        plex_base_dir=config.get('Plex', 'plex_dir'),
        warning_log_path=warning_log
    )

# Create manager
manager = BackupManager(
    backup_dirs=config.get('Backup', 'backup_dirs').strip().split('\n'),
    dest_dir=config.get('Backup', 'dest_dir'),
    backup_file_base=config.get('Backup', 'backup_file_base'),
    password_file=config.get('Backup', 'password_file'),
    max_backups=config.getint('Backup', 'max_backups'),
    preserve_levels=config.getint('Backup', 'preserve_levels', fallback=2),
    plex_handler=plex_handler
)

# Run backup
manager.perform_backup()
