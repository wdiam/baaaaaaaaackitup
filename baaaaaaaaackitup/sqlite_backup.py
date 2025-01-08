from pathlib import Path
import logging
import sqlite3
import time
from typing import List, Tuple
import shutil

class SQLiteBackupHandler:
    """Handler for safely backing up SQLite databases."""
    
    def __init__(self, warning_log_path: Path):
        """Initialize the SQLite backup handler."""
        self.setup_logging(warning_log_path)
        
    def setup_logging(self, warning_log_path: Path):
        """Configure logging with both console and file output"""
        self.logger = logging.getLogger('sqlite_backup')
        self.logger.setLevel(logging.INFO)
        
        # Create formatter that includes logger name
        log_format = logging.Formatter(
            '[%(levelname)s] %(asctime)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        self.logger.addHandler(console_handler)
        
        # File handler for warnings/errors
        file_handler = logging.FileHandler(warning_log_path)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(log_format)
        self.logger.addHandler(file_handler)

    def is_valid_sqlite_db(self, path: Path) -> bool:
        """Check if a file is a valid SQLite database."""
        if not path.is_file() or path.suffix.lower() != '.db':
            return False
            
        try:
            with sqlite3.connect(path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                return True
        except sqlite3.Error:
            return False
        except Exception as e:
            self.logger.debug(f"Error checking {path}: {e}")
            return False

    def backup_database(self, db_path: Path, backup_path: Path) -> bool:
        """Safely backup a SQLite database using SQLite's backup API."""
        try:
            size_before = db_path.stat().st_size
            self.logger.info(f"Starting backup of database: {db_path.name} (Size: {size_before/1024/1024:.2f}MB)")
            
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            start_time = time.time()
            with sqlite3.connect(db_path) as source_conn:
                with sqlite3.connect(backup_path) as backup_conn:
                    source_conn.backup(backup_conn)
            
            backup_time = time.time() - start_time
            size_after = backup_path.stat().st_size
            
            self.logger.info(
                f"Database backup complete: {db_path.name}\n"
                f"  Time taken: {backup_time:.2f} seconds\n"
                f"  Original size: {size_before/1024/1024:.2f}MB\n"
                f"  Backup size: {size_after/1024/1024:.2f}MB"
            )
            return True
                
        except Exception as e:
            self.logger.error(f"Failed to backup {db_path.name}: {str(e)}")
            return False

    def handle_path(self, source_path: Path, backup_base: Path, relative_to: Path) -> bool:
        """
        Handle a path during backup - if it's a SQLite database, back it up safely,
        otherwise just copy it.
        
        Args:
            source_path: Path to the source file
            backup_base: Base directory for the backup
            relative_to: Path to calculate relative paths from
            
        Returns:
            bool: True if handled successfully
        """
        try:
            # Calculate relative path for backup
            rel_path = source_path.relative_to(relative_to)
            backup_path = backup_base / rel_path
            
            # Ensure parent directory exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # If it's a valid SQLite database, back it up safely
            if self.is_valid_sqlite_db(source_path):
                self.logger.info(f"Found SQLite database: {source_path}")
                return self.backup_database(source_path, backup_path)
            
            # Otherwise, just copy the file
            else:
                shutil.copy2(source_path, backup_path)
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to handle {source_path}: {str(e)}")
            return False
        