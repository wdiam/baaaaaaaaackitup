class BackupError(Exception):
    """Base exception for backup-related errors."""
    pass

class EncryptionError(BackupError):
    """Raised when encryption fails."""
    pass

class CompressionError(BackupError):
    """Raised when compression fails."""
    pass

class DirectoryError(BackupError):
    """Raised when there are issues with directories."""
    pass

class RestoreError(BackupError):
    """Raised when restore operations fail."""
    pass