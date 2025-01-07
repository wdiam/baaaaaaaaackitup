from pathlib import Path
import logging
import sqlite3
import tempfile
import shutil
import sys
import time
from typing import List, Tuple

class PlexBackupHandler:
    """Handler for Plex database backups."""
    
    def __init__(self, plex_base_dir: str, warning_log_path: Path):
        """
        Initialize the Plex backup handler.
        
        Args:
            plex_base_dir: Base Plex directory
            warning_log_path: Path to the shared warning log file
        """
        self.base_dir = Path(plex_base_dir)
        self.setup_logging(warning_log_path)
        self.logger.info(f"Initialized with base_dir: {self.base_dir}")

    def setup_logging(self, warning_log_path: Path):
        """Configure logging with both console and file output"""
        self.logger = logging.getLogger('plex_backup')
        self.logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Create formatter that includes logger name
        log_format = logging.Formatter(
            '[%(levelname)s] %(asctime)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_format)
        self.logger.addHandler(console_handler)
        
        # File handler for warnings/errors (shared with BackupManager)
        file_handler = logging.FileHandler(warning_log_path)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(log_format)
        self.logger.addHandler(file_handler)

    def find_databases(self) -> List[Tuple[Path, Path]]:
        """Recursively find all SQLite databases under the base directory."""
        databases = []
        try:
            self.logger.info(f"Scanning for databases in: {self.base_dir}")
            db_count = 0
            total_size = 0
            
            for path in self.base_dir.rglob("*.db"):
                db_count += 1
                self.logger.debug(f"Checking potential database: {path}")
                if self.is_valid_sqlite_db(path):
                    size = path.stat().st_size
                    total_size += size
                    rel_path = path.relative_to(self.base_dir)
                    self.logger.info(f"Found valid database: {rel_path} (Size: {size/1024/1024:.2f}MB)")
                    databases.append((path, rel_path))
                else:
                    self.logger.debug(f"Skipping invalid database: {path}")
                    
            self.logger.info(f"Database scan complete: Found {len(databases)} valid databases out of {db_count} .db files")
            self.logger.info(f"Total database size: {total_size/1024/1024:.2f}MB")
                
        except Exception as e:
            self.logger.error(f"Error scanning for databases: {e}")
                
        return databases

    def find_preferences(self) -> List[Tuple[Path, Path]]:
        """Find Plex preference files."""
        pref_files = []
        total_size = 0
        try:
            self.logger.info(f"Scanning for preference files in: {self.base_dir}")
            
            for path in self.base_dir.rglob("Preferences.xml"):
                size = path.stat().st_size
                total_size += size
                rel_path = path.relative_to(self.base_dir)
                self.logger.info(f"Found preferences file: {rel_path} (Size: {size/1024/1024:.2f}MB)")
                pref_files.append((path, rel_path))
                    
            self.logger.info(f"Found {len(pref_files)} preference files, total size: {total_size/1024/1024:.2f}MB")
                
        except Exception as e:
            self.logger.error(f"Error scanning for preference files: {e}")
                
        return pref_files

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
        """Safely backup a Plex database using SQLite's backup API."""
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

    def prepare_backup(self, temp_dir: Path) -> bool:
        """Prepare Plex backup in a temporary directory."""
        success = True
        total_size = 0
        files_processed = 0
        
        try:
            self.logger.info(f"Starting Plex backup preparation from: {self.base_dir}")
            start_time = time.time()

            # Find all databases and preference files
            databases = self.find_databases()
            pref_files = self.find_preferences()
            
            if not databases and not pref_files:
                self.logger.warning("No Plex files found to backup!")
                return False

            # Create Plex backup structure
            plex_backup_dir = temp_dir / "plex"
            
            # Backup databases
            for db_path, rel_path in databases:
                backup_path = plex_backup_dir / rel_path
                size = db_path.stat().st_size
                total_size += size
                files_processed += 1
                if not self.backup_database(db_path, backup_path):
                    success = False

            # Backup preference files
            for pref_path, rel_path in pref_files:
                try:
                    backup_path = plex_backup_dir / rel_path
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(pref_path, backup_path)
                    size = pref_path.stat().st_size
                    total_size += size
                    files_processed += 1
                    self.logger.info(f"Backed up: {rel_path} (Size: {size/1024/1024:.2f}MB)")
                except Exception as e:
                    self.logger.error(f"Failed to backup {rel_path}: {e}")
                    success = False

            time_taken = time.time() - start_time
            self.logger.info(
                f"Plex backup preparation completed:\n"
                f"  Success: {success}\n"
                f"  Time taken: {time_taken:.2f} seconds\n"
                f"  Files processed: {files_processed}\n"
                f"  Total size: {total_size/1024/1024:.2f}MB"
            )

            return success

        except Exception as e:
            self.logger.error(f"Failed to prepare Plex backup: {str(e)}")
            return False