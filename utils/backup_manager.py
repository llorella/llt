import os
import shutil
import json
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path
from utils.colors import Colors

class BackupManager:
    """Manage file backups with versioning."""
    
    def __init__(self, backup_dir: str = ".backups"):
        self.backup_dir = backup_dir
        self.manifest_path = os.path.join(backup_dir, "manifest.json")
        self._load_manifest()
        
    def _load_manifest(self) -> None:
        """Load or initialize backup manifest."""
        os.makedirs(self.backup_dir, exist_ok=True)
        try:
            if os.path.exists(self.manifest_path):
                with open(self.manifest_path, 'r') as f:
                    self.manifest = json.load(f)
            else:
                self.manifest = {"files": {}}
        except Exception as e:
            Colors.print_colored(f"Error loading backup manifest: {e}", Colors.RED)
            self.manifest = {"files": {}}
            
    def _save_manifest(self) -> None:
        """Save backup manifest."""
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump(self.manifest, f, indent=2)
        except Exception as e:
            Colors.print_colored(f"Error saving backup manifest: {e}", Colors.RED)
            
    def create_backup(self, filepath: str) -> Optional[str]:
        """Create a new backup version of a file."""
        if not os.path.exists(filepath):
            return None
            
        try:
            rel_path = os.path.relpath(filepath)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{os.path.basename(filepath)}.{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            # Create backup
            shutil.copy2(filepath, backup_path)
            
            # Update manifest
            if rel_path not in self.manifest["files"]:
                self.manifest["files"][rel_path] = []
            self.manifest["files"][rel_path].append({
                "timestamp": timestamp,
                "backup_path": backup_name
            })
            
            self._save_manifest()
            return backup_path
            
        except Exception as e:
            Colors.print_colored(f"Error creating backup of {filepath}: {e}", Colors.RED)
            return None
            
    def restore_backup(self, filepath: str, version: Optional[str] = None) -> bool:
        """Restore a specific or latest backup version."""
        try:
            rel_path = os.path.relpath(filepath)
            if rel_path not in self.manifest["files"]:
                return False
                
            versions = self.manifest["files"][rel_path]
            if not versions:
                return False
                
            if version:
                backup_info = next(
                    (v for v in versions if v["timestamp"] == version),
                    None
                )
            else:
                backup_info = versions[-1]  
                
            if not backup_info:
                return False
                
            backup_path = os.path.join(self.backup_dir, backup_info["backup_path"])
            if not os.path.exists(backup_path):
                return False
                
            # Create new backup of current state if it exists
            if os.path.exists(filepath):
                self.create_backup(filepath)
                
            # Restore backup
            shutil.copy2(backup_path, filepath)
            return True
            
        except Exception as e:
            Colors.print_colored(f"Error restoring backup: {e}", Colors.RED)
            return False
            
    def list_backups(self, filepath: Optional[str] = None) -> Dict[str, List[Dict]]:
        """List available backups for file or all files."""
        if filepath:
            rel_path = os.path.relpath(filepath)
            return {
                rel_path: self.manifest["files"].get(rel_path, [])
            }
        return self.manifest["files"]
        
    def cleanup_old_backups(self, max_versions: int = 5, filepath: Optional[str] = None) -> None:
        """Remove old backup versions keeping last N."""
        try:
            files = [os.path.relpath(filepath)] if filepath else list(self.manifest["files"].keys())
            
            for file in files:
                versions = self.manifest["files"].get(file, [])
                if len(versions) > max_versions:
                    # Remove old versions
                    for version in versions[:-max_versions]:
                        backup_path = os.path.join(
                            self.backup_dir,
                            version["backup_path"]
                        )
                        if os.path.exists(backup_path):
                            os.remove(backup_path)
                    
                    # Update manifest
                    self.manifest["files"][file] = versions[-max_versions:]
                    
            self._save_manifest()
            
        except Exception as e:
            Colors.print_colored(f"Error cleaning up old backups: {e}", Colors.RED) 