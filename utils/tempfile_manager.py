import os
import tempfile
from typing import Optional, ContextManager
from contextlib import contextmanager
from utils.colors import Colors

class TempFileManager:
    """Manage temporary files with cleanup."""
    
    def __init__(self):
        self.temp_files = set()
        
    def create(self, suffix: Optional[str] = None, content: Optional[str] = None) -> str:
        """Create a temporary file with optional content."""
        try:
            fd, path = tempfile.mkstemp(suffix=suffix)
            self.temp_files.add(path)
            
            if content is not None:
                with os.fdopen(fd, 'w') as f:
                    f.write(content)
            else:
                os.close(fd)
                
            return path
            
        except Exception as e:
            Colors.print_colored(f"Error creating temporary file: {e}", Colors.RED)
            if 'fd' in locals():
                os.close(fd)
            raise
            
    @contextmanager
    def temp_file(self, suffix: Optional[str] = None, content: Optional[str] = None) -> ContextManager[str]:
        """Context manager for temporary file usage."""
        path = None
        try:
            path = self.create(suffix, content)
            yield path
        finally:
            if path:
                self.cleanup(path)
                
    def cleanup(self, path: Optional[str] = None) -> None:
        """Clean up specific or all temporary files."""
        if path is None:
            # Cleanup all temp files
            while self.temp_files:
                path = self.temp_files.pop()
                try:
                    if os.path.exists(path):
                        os.remove(path)
                except Exception as e:
                    Colors.print_colored(f"Error removing temporary file {path}: {e}", Colors.RED)
        elif path in self.temp_files:
            # Cleanup specific file
            try:
                if os.path.exists(path):
                    os.remove(path)
                self.temp_files.remove(path)
            except Exception as e:
                Colors.print_colored(f"Error removing temporary file {path}: {e}", Colors.RED)
                
    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup() 