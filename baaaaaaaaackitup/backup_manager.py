# baaaaaaaaackitup/baaaaaaaaackitup/backup_manager.py

import tarfile
import gzip
import subprocess
from datetime import datetime
from pathlib import Path
import shutil
import tempfile
import logging
import sys
import os
from typing import List, Optional
from .exceptions import BackupError, EncryptionError, CompressionError, DirectoryError

class BackupManager:
    """Main class for handling backup operations."""
    
    def __init__(self, 
                 backup_dirs: List[str],
                 dest_dir: str,
                 backup_file_base: str,
                 password_file: str,
                 max_backups: int = 10,
                 preserve_levels: int = 2):
        """
        Initialize the backup manager.
        
        Args:
            backup_dirs: List of directories to backup
            dest_dir: Destination directory for backups
            backup_file_base: Base name for backup files
            password_file: Path to GPG password file
            max_backups: Maximum number of backups to keep
            preserve_levels: Number of directory levels to preserve in backup
        """
        self.backup_dirs = [Path(d) for d in backup_dirs]
        self.dest_dir = Path(dest_dir)
        self.backup_file_base = backup_file_base
        self.password_file = Path(password_file)
        self.max_backups = max_backups
        self.preserve_levels = preserve_levels
        self.setup_logging()

    def setup_logging(self):
        """Configure logging to output to both file and console"""
        self.logger = logging.getLogger('backup_manager')
        self.logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Console handler with custom formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_format = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s',
                                         datefmt='%Y-%m-%d %H:%M:%S')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler for warnings/errors
        warning_log = self.dest_dir / 'backup_warnings.log'
        file_handler = logging.FileHandler(warning_log)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(console_format)
        self.logger.addHandler(file_handler)

    def should_exclude(self, path: str) -> bool:
        """
        Check if a path should be excluded from backup.
        
        Args:
            path: Path to check
            
        Returns:
            bool: True if path should be excluded
        """
        exclude_patterns = [
            '/.git/',
            '/.git',
            '__pycache__',
            '*.pyc',
            '*.pyo'
        ]
        
        return any(pattern in path for pattern in exclude_patterns)
    
    def get_preserved_path(self, full_path: Path, backup_dir: Path) -> Path:
        """
        Get the preserved path that includes:
        1. The last preserve_levels directories from the backup directory's parent path
        (or all available levels if preserve_levels is larger)
        2. The complete path structure beneath the backup directory
        
        Args:
            full_path: Full path to the file/directory
            backup_dir: The directory being backed up (from backup_dirs list)
            
        Returns:
            Path: Path with preserved directory structure
        """
        try:
            # Get the backup directory parts
            backup_parts = list(backup_dir.parts)
            
            # Handle case where preserve_levels is larger than available parts
            num_levels = min(self.preserve_levels, len(backup_parts))
            preserved_parents = backup_parts[-num_levels:]
            
            # Get the path relative to the backup directory
            relative_part = full_path.relative_to(backup_dir)
            
            # Combine the preserved parent structure with the relative path
            return Path(*preserved_parents) / relative_part
                
        except ValueError:
            self.logger.warning(f"Path {full_path} is not relative to {backup_dir}")
            return Path(full_path.name)

    def create_tar_archive(self, staging_dir: Path, tar_path: Path):
        """
        Create a tar archive of the backup directories.
        """
        total_source_size = 0
        total_tar_size = 0
        files_processed = 0
        
        with tarfile.open(tar_path, 'w') as tar:
            for dir_path in self.backup_dirs:
                if not dir_path.exists():
                    self.logger.warning(f"Directory does not exist: {dir_path}")
                    continue
                
                self.logger.info(f"Backing up: {dir_path}")
                try:
                    # Track skipped files
                    skipped_files = []
                    
                    # Walk through directory
                    for root, dirs, files in os.walk(dir_path):
                        # Skip excluded directories
                        dirs[:] = [d for d in dirs if not self.should_exclude(f"{root}/{d}")]
                        
                        # Process directories first
                        for name in dirs:
                            dir_full_path = Path(root) / name
                            if not self.should_exclude(str(dir_full_path)):
                                try:
                                    # Get preserved path relative to backup directory
                                    preserved_path = self.get_preserved_path(dir_full_path, dir_path)
                                    self.logger.debug(f"Adding directory as: {preserved_path}")
                                    
                                    # Create a TarInfo object for the directory
                                    tarinfo = tarfile.TarInfo(str(preserved_path))
                                    tarinfo.type = tarfile.DIRTYPE
                                    tar.addfile(tarinfo)
                                except PermissionError:
                                    skipped_files.append(str(dir_full_path))
                                    self.logger.warning(f"Permission denied, skipping directory: {dir_full_path}")
                        
                        # Process files
                        for name in files:
                            file_full_path = Path(root) / name
                            if not self.should_exclude(str(file_full_path)):
                                try:
                                    # Get preserved path relative to backup directory
                                    preserved_path = self.get_preserved_path(file_full_path, dir_path)
                                    self.logger.debug(f"Adding file as: {preserved_path}")
                                    
                                    # Get source file size before adding
                                    try:
                                        source_size = os.path.getsize(str(file_full_path))
                                        total_source_size += source_size
                                    except OSError:
                                        self.logger.warning(f"Could not get size for: {file_full_path}")
                                    
                                    # Record tar position before adding file
                                    tar_pos_before = tar_path.stat().st_size if tar_path.exists() else 0
                                    
                                    # Add file with preserved path
                                    tar.add(str(file_full_path), arcname=str(preserved_path))
                                    files_processed += 1
                                    
                                    # Calculate how much this file added to the tar
                                    if tar_path.exists():
                                        tar_pos_after = tar_path.stat().st_size
                                        tar_size_delta = tar_pos_after - tar_pos_before
                                        total_tar_size += tar_size_delta
                                        
                                        # Log significant size differences
                                        if tar_size_delta > source_size * 2:
                                            self.logger.warning(
                                                f"Large size increase for {file_full_path}: "
                                                f"Source={source_size/1024/1024:.2f}MB, "
                                                f"Tar addition={tar_size_delta/1024/1024:.2f}MB"
                                            )
                                            
                                except PermissionError:
                                    skipped_files.append(str(file_full_path))
                                    self.logger.warning(f"Permission denied, skipping file: {file_full_path}")
                    
                    if skipped_files:
                        self.logger.warning(
                            f"Skipped {len(skipped_files)} files/directories due to permissions in {dir_path}. "
                            "Consider running with elevated privileges if these files are critical."
                        )
                        
                except Exception as e:
                    if isinstance(e, PermissionError):
                        self.logger.warning(f"Permission error accessing {dir_path}: {str(e)}")
                        continue
                    raise DirectoryError(f"Error processing {dir_path}: {str(e)}")
            
            # Log final statistics
            self.logger.info(
                f"Backup statistics:\n"
                f"Files processed: {files_processed:,}\n"
                f"Source data size: {total_source_size/1024/1024/1024:.2f}GB\n"
                f"Tar file size: {total_tar_size/1024/1024/1024:.2f}GB\n"
                f"Size ratio: {total_tar_size/total_source_size:.2f}x"
            )


    def compress_file(self, input_path: Path, output_path: Path):
        """
        Compress a file using pigz (parallel gzip).
        If pigz is not available, falls back to regular gzip.
        
        Args:
            input_path: Path to the input file
            output_path: Path where the compressed file should be saved
            
        Raises:
            CompressionError: If compression fails
        """
        try:
            # Try pigz first (parallel compression)
            try:
                self.logger.info("Using pigz for parallel compression...")
                proc = subprocess.Popen(
                    ['pigz', '-c'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                with open(input_path, 'rb') as f_in:
                    stdout, stderr = proc.communicate(f_in.read())
                
                if proc.returncode == 0:
                    with open(output_path, 'wb') as f_out:
                        f_out.write(stdout)
                    self.logger.info("Parallel compression completed successfully")
                    return
                else:
                    self.logger.warning(f"pigz failed: {stderr.decode()}, falling back to gzip")
                    
            except FileNotFoundError:
                self.logger.warning("pigz not found, falling back to gzip")
            
            # Fallback to regular gzip
            self.logger.info("Using standard gzip compression...")
            with open(input_path, 'rb') as f_in:
                with gzip.open(output_path, 'wb', compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            self.logger.info("Standard compression completed successfully")
                    
        except Exception as e:
            raise CompressionError(f"Failed to compress file: {str(e)}")

    def encrypt_file(self, input_path: Path, output_path: Path) -> bool:
        """
        Encrypt a file using GPG.
        
        Args:
            input_path: Path to the input file
            output_path: Path where the encrypted file should be saved
            
        Returns:
            bool: True if encryption was successful
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            cmd = [
                'gpg',
                '--batch',
                '--yes',
                '--passphrase-file', str(self.password_file),
                '-c',
                str(input_path)
            ]
            
            result = subprocess.run(cmd, 
                                  capture_output=True, 
                                  text=True)
            
            if result.stderr:
                self.logger.warning(f"GPG output: {result.stderr}")
            
            if result.returncode != 0:
                raise EncryptionError(f"GPG encryption failed: {result.stderr}")
                
            return True
            
        except Exception as e:
            raise EncryptionError(f"Encryption error: {str(e)}")

    def generate_backup_name(self) -> str:
        """
        Generate backup filename with timestamp.
        Returns filename without the .gpg extension since that's added during encryption.
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{self.backup_file_base}.{timestamp}.gz"


    def rotate_old_backups(self):
        """
        Remove old backups keeping only the most recent ones.
        
        This method keeps the number of backups specified by self.max_backups,
        removing the oldest ones if necessary.
        """
        pattern = f"{self.backup_file_base}.*.gz.gpg"
        backups = sorted([
            b for b in self.dest_dir.glob(pattern) 
            if b.is_file()  # Only include files that actually exist
        ])
        
        while len(backups) > self.max_backups:
            oldest = backups.pop(0)
            if oldest.exists():  # Double check before trying to delete
                self.logger.info(f"Removing old backup: {oldest.name}")
                try:
                    oldest.unlink()
                except Exception as e:
                    self.logger.warning(f"Failed to remove old backup {oldest.name}: {str(e)}")
                    # Continue with rotation even if one deletion fails

    def perform_backup(self) -> bool:
        """
        Perform the complete backup process.
        
        This method orchestrates the entire backup process:
        1. Creates a tar archive of specified directories
        2. Compresses the archive
        3. Encrypts the compressed archive
        4. Rotates old backups
        
        Returns:
            bool: True if backup was successful
            
        Raises:
            BackupError: If any part of the backup process fails
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                staging_dir = Path(temp_dir)
                self.logger.info(f"Created staging directory: {staging_dir}")

                # Stage 1: Create tar archive
                self.logger.info("=== Stage 1: Creating tar archive ===")
                tar_path = staging_dir / "backup.tar"
                self.create_tar_archive(staging_dir, tar_path)

                # Stage 2: Compress
                self.logger.info("=== Stage 2: Compressing archive ===")
                compressed_path = staging_dir / "backup.tar.gz"
                self.compress_file(tar_path, compressed_path)
                tar_path.unlink()  # Remove uncompressed tar

                # Stage 3: Encrypt
                self.logger.info("=== Stage 3: Encrypting archive ===")
                backup_name = self.generate_backup_name()
                final_path = self.dest_dir / backup_name
                shutil.copy2(compressed_path, final_path)
                
                if not self.encrypt_file(final_path, Path(str(final_path) + '.gpg')):
                    raise EncryptionError("Encryption failed")
                
                final_path.unlink()  # Remove unencrypted file

                # Stage 4: Rotate old backups
                self.logger.info("=== Stage 4: Rotating old backups ===")
                self.rotate_old_backups()

                final_backup_name = backup_name + '.gpg'
                self.logger.info(f"Backup completed successfully: {final_backup_name}")
                return True

        except Exception as e:
            self.logger.error(f"Backup failed: {str(e)}")
            raise BackupError(f"Backup process failed: {str(e)}")