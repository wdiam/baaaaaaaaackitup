#!/usr/bin/env python3

from baaaaaaaaackitup import RestoreManager
import configparser
import sys
from pathlib import Path

def main():
    # Load config
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # Check if Restore section exists
    if 'Restore' not in config:
        print("Error: 'Restore' section not found in config.ini")
        sys.exit(1)
    
    try:
        # Create extract directory first, before initializing RestoreManager
        extract_path = Path(config.get('Restore', 'extract_path'))
        extract_path.mkdir(parents=True, exist_ok=True)
        print(f"Extraction directory created/verified: {extract_path}")
        
        # Now create restore manager (after directory exists)
        restorer = RestoreManager(
            backup_file=config.get('Restore', 'backup_file'),
            password_file=config.get('Backup', 'password_file'),  # Reuse from Backup section
            extract_path=str(extract_path)
        )
        
        # Run restore
        restorer.restore()
        print("Restore completed successfully")
        
    except configparser.Error as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Restore failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()