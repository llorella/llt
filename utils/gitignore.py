import os
from pathlib import Path
from typing import List, Optional
import fnmatch

def get_gitignore_patterns(root_dir: str = None) -> List[str]:
    """
    Get patterns from .gitignore files, searching up the directory tree.
    
    Args:
        root_dir: Starting directory (defaults to current working directory)
    
    Returns:
        List of gitignore patterns
    """
    if root_dir is None:
        root_dir = os.getcwd()
    
    patterns = []
    current_dir = Path(root_dir).resolve()
    
    while True:
        gitignore_path = current_dir / '.gitignore'
        if gitignore_path.exists():
            try:
                with open(gitignore_path) as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith('#'):
                            patterns.append(line)
            except Exception as e:
                print(f"Warning: Failed to read {gitignore_path}: {e}")
        
        # Stop at filesystem root
        parent = current_dir.parent
        if parent == current_dir:
            break
        current_dir = parent
    
    return patterns

def should_ignore(path: str, patterns: List[str], is_dir: bool = False) -> bool:
    """
    Check if a path should be ignored based on gitignore patterns.
    
    Args:
        path: Path to check
        patterns: List of gitignore patterns
        is_dir: Whether the path is a directory
    
    Returns:
        True if path should be ignored, False otherwise
    """
    path = os.path.normpath(path)
    
    for pattern in patterns:
        # Handle negation patterns
        if pattern.startswith('!'):
            if _matches_pattern(path, pattern[1:], is_dir):
                return False
            continue
            
        if _matches_pattern(path, pattern, is_dir):
            return True
    
    return False

def _matches_pattern(path: str, pattern: str, is_dir: bool) -> bool:
    """
    Check if a path matches a single gitignore pattern.
    
    Args:
        path: Path to check
        pattern: Single gitignore pattern
        is_dir: Whether the path is a directory
    
    Returns:
        True if path matches pattern, False otherwise
    """
    # Handle directory-specific patterns
    if pattern.endswith('/'):
        if not is_dir:
            return False
        pattern = pattern[:-1]
    
    # Handle patterns starting with /
    if pattern.startswith('/'):
        pattern = pattern[1:]
        return fnmatch.fnmatch(path, pattern)
    
    # Handle patterns with middle /
    if '/' in pattern:
        return fnmatch.fnmatch(path, pattern)
    
    # Handle basic patterns
    return fnmatch.fnmatch(os.path.basename(path), pattern)

def get_ignored_paths(directory: str = ".", patterns: Optional[List[str]] = None) -> List[str]:
    """
    Get list of paths that match gitignore patterns.
    
    Args:
        directory: Directory to scan (defaults to current directory)
        patterns: List of patterns (if None, will read from .gitignore)
    
    Returns:
        List of paths that should be ignored
    """
    if patterns is None:
        patterns = get_gitignore_patterns(directory)
    
    ignored = []
    for root, dirs, files in os.walk(directory):
        # Check directories
        dirs[:] = [d for d in dirs if not should_ignore(
            os.path.join(root, d),
            patterns,
            is_dir=True
        )]
        
        # Check files
        for file in files:
            path = os.path.join(root, file)
            if should_ignore(path, patterns):
                ignored.append(path)
    
    return ignored 