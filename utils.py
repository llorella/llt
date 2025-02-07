# @utils.py
# Combined utilities from utils/

import os
import json
import shutil
from datetime import datetime
import sys
import re
import difflib
import readline
import base64
import tiktoken
import pyperclip
from PIL import Image
from math import ceil
import tempfile
from io import BytesIO
import pprint
from typing import List, Dict, Tuple, Optional, ContextManager
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager
# Language mappings
language_extension_map = {
    "bash": ".sh",
    "python": ".py",
    "shell": ".sh",
    "markdown": ".md",
    "html": ".html",
    "css": ".css",
    "javascript": ".js",
    "typescript": ".ts",
    "json": ".json",
    "yaml": ".yaml",
    "c": ".c",
    "cpp": ".cpp",
    "rust": ".rs",
    "go": ".go",
    "csv": ".csv",
    "cuda": ".cu",
    "jsx": ".jsx",
    "tsx": ".tsx"
}

language_comment_map = {
    'python': '#',
    'shell': '#',
    'text': '#',
    'markdown': '#',
    'html': '<!--',
    'css': '/*',
    'javascript': '//',
    'typescript': '//',
    'json': '//',
    'yaml': '#',
    'c': '//',
    'cpp': '//',
    'rust': '//',
    'csv': '#',
    'jsx': '//',
    'tsx': '//'
}

class Colors:
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    MAGENTA = "\033[35m"
    YELLOW = "\033[93m"
    WHITE = "\033[97m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"
    CYAN = "\033[36m"
    LIGHT_BLUE = "\033[94m"
    LIGHT_GREEN = "\033[92m"
    PURPLE = "\033[95m"

    @staticmethod
    def print_colored(text: str, color: str = "") -> None:
        print(f"{color}{text}{Colors.RESET}")

    @staticmethod
    def print_bold(text: str, color: str = "") -> None:
        print(f"{Colors.BOLD}{color}{text}{Colors.RESET}")

    @staticmethod
    def pretty_print_dict(message: Dict) -> None:
        formatted_message = pprint.pformat(message, indent=4)
        Colors.print_colored(formatted_message, Colors.WHITE)

    @staticmethod
    def print_header():
        Colors.print_colored("***** Welcome to llt, the little language terminal *****", Colors.YELLOW)

# File diff utilities
def generate_diff(old_content: str, new_content: str, filename: str = "") -> str:
    """Generate a unified diff string from old_content to new_content."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=filename + " (old)" if filename else "",
        tofile=filename + " (new)" if filename else "",
        lineterm=""
    )
    return "".join(diff)

def prompt_and_write_file(final_path: str, new_content: str, diff_text: str) -> bool:
    """Display a diff, prompt the user if they want to write to 'final_path'."""
    file_exists = os.path.isfile(final_path)
    if not diff_text:
        print(f"No changes for {final_path}, skipping.")
        return False

    print(f"\n--- Diff for {final_path} ---")
    print(diff_text, end="")
    print("\n--- End of diff ---")

    if file_exists:
        user_input = input(f"Overwrite file '{final_path}'? (y/N) ").strip().lower()
    else:
        user_input = input(f"File '{final_path}' does not exist. Create it? (y/N) ").strip().lower()

    if user_input == 'y':
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        try:
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            action = "Overwritten" if file_exists else "Created"
            print(f"{action} '{final_path}'.\n")
            return True
        except Exception as e:
            print(f"Error writing '{final_path}': {e}")
            return False
    elif user_input == 'c':
        pyperclip.copy(new_content)
        return False
    else:
        print(f"Skipped writing '{final_path}'.\n")
        return False

# Markdown parsing utilities
def detect_language_from_content(content: str) -> Optional[str]:
    """Try to detect language from code content."""
    indicators = {
        'python': ['def ', 'import ', 'class ', 'if __name__'],
        'javascript': ['function ', 'const ', 'let ', 'var '],
        'typescript': ['interface ', 'type ', '<T>', ': string'],
        'html': ['<!DOCTYPE', '<html', '<div', '<body'],
        'css': ['{', '@media', '#', '.class'],
        'shell': ['#!/bin/', 'echo ', 'export ', 'sudo '],
        'rust': ['fn ', 'impl ', 'pub ', 'use '],
        'go': ['func ', 'package ', 'import (', 'type '],
    }
    
    for lang, patterns in indicators.items():
        if any(pattern in content for pattern in patterns):
            return lang
    return None

def extract_code_blocks(markdown: str) -> List[Dict]:
    """Extract code blocks from markdown text."""
    code_pattern = re.compile(r"```(\w+)\n(.*?)\n```", re.DOTALL)
    matches = code_pattern.findall(markdown)
    blocks = []
    for language, code in matches:
        blocks.append({
            "language": language,
            "content": code.strip(),
            "filename": None
        })
    return blocks

def fuzzy_find_filename(line: str) -> str:
    """Find something that looks like a path or filename."""
    filename_pattern = re.compile(r'([^\s"\':]+(\.[^\s"\':]+)+)')
    matches = filename_pattern.findall(line)
    for full_match, _ in matches:
        return full_match
    return ""

def extract_filename_from_codeblock(code: str, language: str) -> Optional[str]:
    """Try to find filename in code block comments."""
    comment_prefix = language_comment_map.get(language, "#")
    lines = code.split('\n')
    max_lines_to_check = min(5, len(lines))

    for i in range(max_lines_to_check):
        line = lines[i].strip()
        if not line:
            continue

        if language == "css":
            if line.startswith("/*") and line.endswith("*/"):
                content = line[2:-2].strip()
                if filename := fuzzy_find_filename(content):
                    return filename
        else:
            if line.startswith(comment_prefix):
                content = line[len(comment_prefix):].strip()
                if filename := fuzzy_find_filename(content):
                    return filename
    return None

def parse_markdown_for_codeblocks(markdown: str) -> List[Dict]:
    """Parse markdown and extract code blocks with metadata."""
    blocks = extract_code_blocks(markdown)
    for i, block in enumerate(blocks):
        block["index"] = i
        if not block["filename"]:
            block["filename"] = extract_filename_from_codeblock(
                block["content"],
                block["language"]
            )
    return blocks

# Input utilities
def path_completer(text, state):
    text = os.path.expanduser(text)
    if os.path.isdir(text):
        entries = os.listdir(text)
        entries = [
            os.path.join(text, e)
            + ("/" if os.path.isdir(os.path.join(text, e)) else "")
            for e in entries
        ]
    else:
        dirname = os.path.dirname(text) or "."
        basename = os.path.basename(text)
        try:
            entries = [
                os.path.join(dirname, e)
                + ("/" if os.path.isdir(os.path.join(dirname, e)) else "")
                for e in os.listdir(dirname)
                if e.startswith(basename)
            ]
        except FileNotFoundError:
            entries = []
    matches = sorted(set(entries))
    try:
        return matches[state]
    except IndexError:
        return None

def path_input(default_file: str = None, root_dir: str = None) -> str:
    readline.set_completer_delims(" \t\n;")
    if "libedit" in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")

    def completer(text, state):
        if root_dir and not os.path.isabs(os.path.expanduser(text)):
            full_text = os.path.join(root_dir, text)
        else:
            full_text = text
        completion = path_completer(full_text, state)
        if completion and root_dir and completion.startswith(root_dir):
            completion = os.path.relpath(completion, root_dir)
        return completion

    readline.set_completer(completer)
    try:
        prompt_text = "Enter file path"
        if default_file:
            prompt_text += f" (default: {default_file})"
        file_path = input(f"{prompt_text}{Colors.RESET}: ")
    finally:
        readline.set_completer(None)
    if root_dir:
        return (
            os.path.join(root_dir, os.path.expanduser(file_path))
            if file_path
            else default_file
        )
    else:
        return os.path.expanduser(file_path) if file_path else default_file

def list_completer(values):
    def completer(text, state):
        matches = [v for v in values if v.startswith(text)]
        try:
            return matches[state]
        except IndexError:
            return None
    return completer

def list_input(values: List[str], input_string: str = "Enter a value from list") -> str:
    readline.set_completer_delims(" \t\n;")
    if "libedit" in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
    readline.set_completer(list_completer(values))
    try:
        return input(f"{input_string} (tab to autocomplete): {Colors.RESET}")
    finally:
        readline.set_completer(None)

def content_input(display_string: str = "Enter content below.") -> str:
    print(display_string)
    Colors.print_colored("*********************************************************", Colors.YELLOW)
    content = input("> ") or ""
    Colors.print_colored("\n*********************************************************\n", Colors.YELLOW)
    return content

def llt_input(plugin_keys: List[str], suggested_cmd: str = "") -> Tuple[str, int]:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(list_completer(plugin_keys))

    raw_cmd = input(f"llt (suggested is {suggested_cmd})> ")
    
    # Strip whitespace
    raw_cmd = raw_cmd.strip()
    
    if not raw_cmd:
        return "", -1
        
    # Pattern 1: "123cmd" - Index followed by command
    if raw_cmd[:-1].isdigit() and raw_cmd[-1:].isalpha():
        return raw_cmd[-1:], int(raw_cmd[:-1])
        
    # Pattern 2: "cmd123" - Command followed by index
    if raw_cmd[:-1].isalpha() and raw_cmd[-1:].isdigit():
        return raw_cmd[:-1], int(raw_cmd[-1:])
        
    # Pattern 3: "1-cmd" - Negative index followed by command
    if (len(raw_cmd) > 2 and 
        raw_cmd[0].isdigit() and 
        raw_cmd[1] == '-' and 
        raw_cmd[2:].isalpha()):
        return raw_cmd[2:], -int(raw_cmd[0])
        
    # Pattern 4: "cmd-1" - Command followed by negative index
    parts = raw_cmd.split('-')
    if (len(parts) == 2 and 
        parts[0].isalpha() and 
        parts[1].isdigit()):
        return parts[0], -int(parts[1])
    
    # Default: Just a command with no index
    return raw_cmd, -1

def get_valid_index(messages: List[Dict[str, any]], prompt: str, default=-1) -> int:
    """Prompt the user to enter a valid index for a message."""
    try:
        idx = (
            input(
                f"Enter index of message to {prompt} (default is {'all' if not default else default}): "
            )
            or default
        )
        if not idx:
            return default
        idx = int(idx) % len(messages)  # support negative indexing
    except ValueError:
        print("Invalid input. Using default.")
        idx = default
    if not -len(messages) <= idx < len(messages):
        raise IndexError("Index out of range. No operation will be performed.")
    return idx

# File operations utilities
def get_project_dir(args: Dict, default_name: str = "untitled") -> str:
    """Determine project directory based on command arguments."""
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
    """Process multiple file changes with diff display and user confirmation."""
    modified_files = []
    skipped_files = []

    for file_info in files:
        filepath = Path(project_dir) / file_info["filename"]
        new_content = file_info["content"]
        
        old_content = read_file_content(str(filepath)) or ""
        diff_lines = generate_diff(old_content, new_content)
        
        if non_interactive:
            if write_file_content(str(filepath), new_content):
                modified_files.append(file_info["filename"])
            else:
                skipped_files.append(file_info["filename"])
            continue
            
        print(f"\nProcessing: {file_info['filename']}")
        print(diff_lines)
        
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

# Image utilities
def encode_image_to_base64(image_path: str) -> str:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return encoded

def is_base64(text: str) -> bool:
    try:
        base64.b64decode(text)
        return True
    except Exception:
        return False

def tokenize(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> int:
    """Count tokens in message content."""
    content = ""
    for msg in messages:
        msg_content = msg["content"]
        if isinstance(msg_content, str):
            content += msg_content
        elif isinstance(msg_content, list):
            for c in msg_content:
                if c.get("type") == "text":
                    content += c["text"]
    encoding = tiktoken.encoding_for_model(args.get("model","gpt-4"))
    num_tokens = 4 + len(encoding.encode(content))
    Colors.print_colored(f"Tokens used: {num_tokens}", Colors.BLUE)
    return num_tokens


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

def confirm_action(prompt: str) -> bool:
    """Prompt the user to confirm an action."""
    return input(f"{prompt} (y/N) [N]: ").lower() == 'y'


class DiffType(Enum):
    ADDED = '+'
    REMOVED = '-'
    CHANGED = '~'
    UNCHANGED = ' '
@dataclass
class DiffLine:
    type: DiffType
    content: str
    line_number_old: Optional[int] = None
    line_number_new: Optional[int] = None
    def colorize(self) -> str:
        """Return colorized version of the line content."""
        color_map = {
            DiffType.ADDED: Colors.GREEN,
            DiffType.REMOVED: Colors.RED,
            DiffType.CHANGED: Colors.YELLOW,
            DiffType.UNCHANGED: ''
        }
        return f"{color_map[self.type]}{self.content}{Colors.RESET}"
    
def generate_diff(old_content: str, new_content: str, context_lines: int = 3) -> List[DiffLine]:
    """Generate detailed diff with line numbers and change types."""
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    
    differ = difflib.SequenceMatcher(None, old_lines, new_lines)
    diff_lines = []
    
    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == 'equal':
            start = max(i1, i1 + (i2 - i1 - context_lines))
            end = min(i2, i1 + context_lines)
            for i, line in enumerate(old_lines[start:end], start):
                diff_lines.append(DiffLine(
                    type=DiffType.UNCHANGED,
                    content=line,
                    line_number_old=i + 1,
                    line_number_new=j1 + (i - i1) + 1
                ))
        elif tag == 'replace':
            for i, line in enumerate(old_lines[i1:i2], i1):
                diff_lines.append(DiffLine(
                    type=DiffType.REMOVED,
                    content=line,
                    line_number_old=i + 1
                ))
            for j, line in enumerate(new_lines[j1:j2], j1):
                diff_lines.append(DiffLine(
                    type=DiffType.ADDED,
                    content=line,
                    line_number_new=j + 1
                ))
        elif tag == 'delete':
            for i, line in enumerate(old_lines[i1:i2], i1):
                diff_lines.append(DiffLine(
                    type=DiffType.REMOVED,
                    content=line,
                    line_number_old=i + 1
                ))
        elif tag == 'insert':
            for j, line in enumerate(new_lines[j1:j2], j1):
                diff_lines.append(DiffLine(
                    type=DiffType.ADDED,
                    content=line,
                    line_number_new=j + 1
                ))
    
    return diff_lines
def format_diff(diff_lines: List[DiffLine], show_line_numbers: bool = True) -> str:
    """Format diff lines for display."""
    output = []
    max_line_num_width = 5
    
    for line in diff_lines:
        if show_line_numbers:
            old_num = str(line.line_number_old or '').rjust(max_line_num_width)
            new_num = str(line.line_number_new or '').rjust(max_line_num_width)
            line_info = f"{old_num}│{new_num}│"
        else:
            line_info = f"{line.type.value} "
            
        output.append(f"{line_info} {line.colorize()}")
        
    return "\n".join(output) 