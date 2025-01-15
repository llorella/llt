import os
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from utils.colors import Colors
from utils.diff import generate_diff, format_diff
from utils.input_utils import path_input
import pyperclip


def get_project_dir(args: Dict, default_name: str = "untitled") -> str:
    """
    Determine project directory based on command arguments.
    
    Args:
        args: Command arguments including exec_dir and load info
        default_name: Default directory name if no load path
    """
    
    ll_dir_abs = os.path.abspath(args.ll_dir)
    load_abs = os.path.abspath(args.load)
    rel = os.path.relpath(load_abs, ll_dir_abs)
    base, ext = os.path.splitext(rel)
    project_dir = path_input(os.path.join(args.exec_dir, rel or os.getcwd()), args.exec_dir)
    return project_dir

def read_file_content(filepath: str) -> Optional[str]:
    """Safely read file content."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:        
            return f.read()
    except Exception as e:
        Colors.print_colored(f"Error reading file {filepath}: {e}", Colors.RED)
        return None

def write_file_content(filepath: str, content: str) -> bool:
    """Safely write content to file."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        Colors.print_colored(f"Error writing file {filepath}: {e}", Colors.RED)
        return False

def process_file_changes(
    files: List[Dict[str, str]], 
    project_dir: str,
    non_interactive: bool = False
) -> Tuple[List[str], List[str]]:
    """
    Process multiple file changes with diff display and user confirmation.
    
    Args:
        files: List of {"filename": str, "content": str} dicts
        project_dir: Base directory for file operations
        non_interactive: Skip user confirmations if True
    
    Returns:
        Tuple of (modified_files, skipped_files)
    """
    modified_files = []
    skipped_files = []

    for file_info in files:
        filepath = Path(project_dir) / file_info["filename"]
        new_content = file_info["content"]
        
        # Get existing content if file exists
        old_content = read_file_content(str(filepath)) or ""
        
        # Generate diff
        diff_lines = generate_diff(old_content, new_content)
        
        if non_interactive:
            if write_file_content(str(filepath), new_content):
                modified_files.append(file_info["filename"])
            else:
                skipped_files.append(file_info["filename"])
            continue
            
        # Show diff and get user choice
        print(f"\nProcessing: {file_info['filename']}")
        print(format_diff(diff_lines))
        
        if filepath.exists():
            choice = input("Overwrite file? (y/n/c=copy to clipboard) [n]: ").lower()
        else:
            choice = input("Create file? (y/n/c=copy to clipboard) [n]: ").lower()
            
        if choice == 'y':
            if write_file_content(str(filepath), new_content):
                modified_files.append(file_info["filename"])
            else:
                skipped_files.append(file_info["filename"])
        elif choice == 'c':
            pyperclip.copy(new_content)
            print("Content copied to clipboard")
            skipped_files.append(file_info["filename"])
        else:
            print(f"Skipped {file_info['filename']}")
            skipped_files.append(file_info["filename"])
            
    return modified_files, skipped_files

def make_file_summary(modified: List[str], skipped: List[str]) -> str:
    """Generate operation summary message."""
    summary = ["File operations complete."]
    
    if modified:
        summary.append("Modified/Created:")
        summary.extend(f"  - {f}" for f in modified)
    if skipped:
        summary.append("Skipped:")
        summary.extend(f"  - {f}" for f in skipped)
        
    return "\n".join(summary) 