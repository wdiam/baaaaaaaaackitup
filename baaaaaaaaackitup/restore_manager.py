import subprocess
import tempfile
import shutil
from pathlib import Path
import logging
import sys
import gzip
import tarfile
from .exceptions import RestoreError, EncryptionError, CompressionError, DirectoryError

class RestoreManager:
    """Handles restoration of encrypted backups."""
    
    def __init__(self, 
                 backup_file: str,
                 password_file: str,
                 extract_path: str):
        """
        Initialize the restore manager.
        
        Args:
            backup_file: Path to the encrypted backup file (.gz.gpg)
            password_file: Path to the GPG password file
            extract_path: Directory where files should be extracted
        """
        self.backup_file = Path(backup_file)
        self.password_file = Path(password_file)
        self.extract_path = Path(extract_path)
        self.setup_logging()
        
    def setup_logging(self):
        """Configure logging to output to both file and console"""
        self.logger = logging.getLogger('restore_manager')
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
        warning_log = Path(self.extract_path) / 'restore_warnings.log'
        file_handler = logging.FileHandler(warning_log)
        file_handler.setLevel(logging.WARNING)
        file_handler.setFormatter(console_format)
        self.logger.addHandler(file_handler)

    def decrypt_file(self, output_path: Path) -> bool:
        """
        Decrypt the backup file using GPG.
        
        Args:
            output_path: Where to save the decrypted file
            
        Returns:
            bool: True if decryption was successful
            
        Raises:
            EncryptionError: If decryption fails
        """
        try:
            self.logger.info("Decrypting backup file...")
            cmd = [
                'gpg',
                '--batch',
                '--yes',
                '--passphrase-file', str(self.password_file),
                '--output', str(output_path),
                '--decrypt', str(self.backup_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.stderr:
                self.logger.warning(f"GPG output: {result.stderr}")
            
            if result.returncode != 0:
                raise EncryptionError(f"GPG decryption failed: {result.stderr}")
            
            return True
            
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {str(e)}")

    def decompress_file(self, input_path: Path, output_path: Path):
        """
        Decompress a gzipped file.
        
        Args:
            input_path: Path to the compressed file
            output_path: Where to save the decompressed file
            
        Raises:
            CompressionError: If decompression fails
        """
        try:
            self.logger.info("Decompressing backup file...")
            with gzip.open(input_path, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        except Exception as e:
            raise CompressionError(f"Decompression failed: {str(e)}")

    def extract_tar(self, tar_path: Path):
        """
        Extract the tar archive to the specified location.
        
        Args:
            tar_path: Path to the tar file
            
        Raises:
            DirectoryError: If extraction fails or unsafe paths are found
        """
        try:
            self.logger.info(f"Extracting files to {self.extract_path}...")
            with tarfile.open(tar_path, 'r') as tar:
                # Check for any harmful files
                for member in tar.getmembers():
                    if member.name.startswith('/') or '..' in member.name:
                        raise DirectoryError(f"Potentially unsafe path in archive: {member.name}")
                
                tar.extractall(path=self.extract_path)
        except Exception as e:
            raise DirectoryError(f"Extraction failed: {str(e)}")

    def restore(self) -> bool:
        """
        Perform the complete restore process.
        
        Returns:
            bool: True if restoration was successful
            
        Raises:
            RestoreError: If any part of the restore process fails
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                self.logger.info("Starting restore process...")

                # Stage 1: Decrypt
                decrypted_path = temp_path / "backup.gz"
                if not self.decrypt_file(decrypted_path):
                    raise RestoreError("Decryption failed")

                # Stage 2: Decompress
                decompressed_path = temp_path / "backup.tar"
                self.decompress_file(decrypted_path, decompressed_path)

                # Stage 3: Extract
                self.extract_tar(decompressed_path)

                self.logger.info("Restore completed successfully")
                return True

        except Exception as e:
            self.logger.error(f"Restore failed: {str(e)}")
            raise RestoreError(f"Restore process failed: {str(e)}")