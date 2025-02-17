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
import pyperclip  # type: ignore
from PIL import Image
from math import ceil
import tempfile
from io import BytesIO
import pprint
from typing import List, Dict, Tuple, Optional, ContextManager, Any, Callable, TypeVar, Union, Generator
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager
import time

# Type aliases
T = TypeVar('T')
InputValue = Union[str, int, float, bool, List[str], Dict[str, Any]]
InputHandler = Callable[[str, Any], InputValue]

# Global handlers
input_handler = None
file_handler = None
diff_handler = None

# Compatibility layer for existing imports
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'

    @staticmethod
    def print_colored(text: str, color: str) -> None:
        print(f"{color}{text}{Colors.RESET}")

    @staticmethod
    def print_header() -> None:
        print(f"{Colors.HEADER}Welcome to LLT{Colors.RESET}")

# Language mappings
language_extension_map = {
    "bash": ".sh", "python": ".py", "shell": ".sh", "markdown": ".md",
    "html": ".html", "css": ".css", "javascript": ".js", "typescript": ".ts",
    "json": ".json", "yaml": ".yaml", "c": ".c", "cpp": ".cpp",
    "rust": ".rs", "go": ".go", "csv": ".csv", "cuda": ".cu",
    "jsx": ".jsx", "tsx": ".tsx", "ruby": ".rb", "java": ".java",
    "sql": ".sql", "dockerfile": "Dockerfile", "makefile": "Makefile"
}

language_comment_map = {
    'python': '#', 'shell': '#', 'text': '#', 'markdown': '#',
    'html': '<!--', 'css': '/*', 'javascript': '//', 'typescript': '//',
    'json': '//', 'yaml': '#', 'c': '//', 'cpp': '//',
    'rust': '//', 'csv': '#', 'jsx': '//', 'tsx': '//',
    'ruby': '#', 'java': '//', 'sql': '--', 'dockerfile': '#', 'makefile': '#'
}

class InputHandler:
    """Enhanced input handling with autocomplete and validation."""
    
    def __init__(self):
        self.history = []
        self._setup_readline()
        
    def _setup_readline(self):
        """Configure readline with common settings."""
        readline.set_completer_delims(" \t\n;")
        if "libedit" in readline.__doc__:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
            
    def _create_completer(self, 
                         options: Optional[List[str]] = None, 
                         path_mode: bool = False,
                         base_dir: Optional[str] = None) -> Callable[[str, int], Optional[str]]:
        """Create a completer function based on mode."""
        def path_completer(text: str, state: int) -> Optional[str]:
            text = os.path.expanduser(text)
            if base_dir and not os.path.isabs(text):
                text = os.path.join(base_dir, text)
            
            dir_path = os.path.dirname(text) or "."
            try:
                if os.path.isdir(text):
                    files = os.listdir(text)
                else:
                    base = os.path.basename(text)
                    files = [f for f in os.listdir(dir_path) if f.startswith(base)]
                files = [os.path.join(dir_path, f) + ('/' if os.path.isdir(os.path.join(dir_path, f)) else '')
                        for f in files]
                
                # Make paths relative to base_dir if specified
                if base_dir:
                    files = [os.path.relpath(f, base_dir) for f in files]
                    
                return sorted(files)[state] if state < len(files) else None
            except (OSError, IndexError):
                return None

        def list_completer(text: str, state: int) -> Optional[str]:
            if not options:
                return None
            matches = [opt for opt in options if opt.startswith(text.lower())]
            return matches[state] if state < len(matches) else None

        return path_completer if path_mode else list_completer

    def get_input(self, 
                 prompt: str,
                 options: Optional[List[str]] = None,
                 default: Any = None,
                 path_mode: bool = False,
                 base_dir: Optional[str] = None,
                 validator: Optional[Callable[[str], bool]] = None,
                 transform: Optional[Callable[[str], Any]] = None) -> Any:
        """
        Enhanced input handling with autocomplete, validation, and transformation.
        
        Args:
            prompt: Input prompt text
            options: List of autocomplete options
            default: Default value if input is empty
            path_mode: Enable path completion mode
            base_dir: Base directory for path completion
            validator: Optional validation function
            transform: Optional transformation function
        """
        readline.set_completer(self._create_completer(options, path_mode, base_dir))
        
        try:
            while True:
                # Format prompt with default if provided
                full_prompt = f"{prompt}"
                if default is not None:
                    full_prompt += f" (default: {default})"
                full_prompt += ": "

                # Get input
                value = input(full_prompt)
                
                # Handle empty input
                if not value:
                    return default

                # Validate if required
                if validator and not validator(value):
                    Colors.print_colored("Invalid input, please try again.", Colors.RED)
                    continue

                # Transform if required
                if transform:
                    try:
                        value = transform(value)
                    except Exception as e:
                        Colors.print_colored(f"Error transforming input: {e}", Colors.RED)
                        continue

                self.history.append(value)
                return value

        finally:
            readline.set_completer(None)

    def get_command_input(self, commands: List[str], prompt: str = "llt") -> Tuple[str, int]:
        """Get command input with command autocompletion."""
        try:
            result = self.get_input(
                prompt,
                options=commands,
                path_mode=False
            )
            return parse_cmd_string(result)
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            sys.exit(0)

    def get_path_input(self, 
                      prompt: str,
                      default: Optional[str] = None,
                      base_dir: Optional[str] = None) -> str:
        """Get path input with filesystem autocomplete."""
        result = self.get_input(
            prompt,
            default=default,
            path_mode=True,
            base_dir=base_dir
        )
        
        # Handle path resolution
        if base_dir and not os.path.isabs(os.path.expanduser(result)):
            return os.path.join(base_dir, result)
        return os.path.expanduser(result)

    def get_list_input(self, 
                      options: List[str], 
                      prompt: str = "", 
                      allow_custom: bool = True) -> str:
        """
        Get input from a list of options with both number and text selection.
        
        Args:
            options: List of available options
            prompt: Optional prompt text
            allow_custom: Allow custom input not in options list
        """
        if not options:
            return ""
        
        if prompt:
            print(prompt)
        
        # Display numbered options
        for i, option in enumerate(options, 1):
            print(f"{i}. {option}")
        
        def validate(value: str) -> bool:
            if not value:
                return True
            try:
                idx = int(value)
                return 1 <= idx <= len(options)
            except ValueError:
                return allow_custom or any(opt.lower().startswith(value.lower()) for opt in options)
        
        def transform(value: str) -> str:
            if not value:
                return ""
            try:
                idx = int(value)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            except ValueError:
                matches = [opt for opt in options if opt.lower().startswith(value.lower())]
                if len(matches) == 1:
                    return matches[0]
            return value
        
        return self.get_input(
            "Enter number or text",
            options=options,
            validator=validate,
            transform=transform
        )

class FileHandler:
    """File operations with safety checks and backups."""

    @staticmethod
    def read(filepath: str) -> Optional[str]:
        """Safely read file content."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            Colors.print_colored(f"Error reading file {filepath}: {e}", Colors.RED)
            return None

    @staticmethod
    def write(filepath: str, content: str) -> bool:
        """Safely write content to file."""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            Colors.print_colored(f"Error writing file {filepath}: {e}", Colors.RED)
            return False

    @staticmethod
    def backup(filepath: str, backup_dir: str = ".backups") -> Optional[str]:
        """Create a backup of a file."""
        if not os.path.exists(filepath):
            return None
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{os.path.basename(filepath)}.{timestamp}")
            os.makedirs(backup_dir, exist_ok=True)
            shutil.copy2(filepath, backup_path)
            return backup_path
        except Exception as e:
            Colors.print_colored(f"Error creating backup: {e}", Colors.RED)
            return None

    @staticmethod
    def encode_image_to_base64(image_path: str) -> str:
        """Encode image to base64."""
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            Colors.print_colored(f"Error encoding image: {e}", Colors.RED)
            return ""

class DiffHandler:
    """Handle file diffs and changes."""
    
    @dataclass
    class DiffLine:
        type: str  # '+', '-', '~', ' '
        content: str
        old_number: Optional[int] = None
        new_number: Optional[int] = None

        def colorize(self) -> str:
            color_map = {'+': Colors.GREEN, '-': Colors.RED, '~': Colors.YELLOW, ' ': ''}
            return f"{color_map[self.type]}{self.content}{Colors.RESET}"

    @staticmethod
    def generate(old: str, new: str, context_lines: int = 3) -> List['DiffHandler.DiffLine']:
        """Generate detailed diff with line numbers."""
        differ = difflib.SequenceMatcher(None, old.splitlines(), new.splitlines())
        diff_lines = []

        for tag, i1, i2, j1, j2 in differ.get_opcodes():
            if tag == 'equal':
                start = max(i1, i1 + (i2 - i1 - context_lines))
                end = min(i2, i1 + context_lines)
                for i in range(start, end):
                    diff_lines.append(DiffHandler.DiffLine(
                        type=' ',
                        content=old.splitlines()[i],
                        old_number=i + 1,
                        new_number=j1 + (i - i1) + 1
                    ))
            elif tag in ('replace', 'delete', 'insert'):
                if tag in ('replace', 'delete'):
                    for i in range(i1, i2):
                        diff_lines.append(DiffHandler.DiffLine(
                            type='-',
                            content=old.splitlines()[i],
                            old_number=i + 1
                        ))
                if tag in ('replace', 'insert'):
                    for j in range(j1, j2):
                        diff_lines.append(DiffHandler.DiffLine(
                            type='+',
                            content=new.splitlines()[j],
                            new_number=j + 1
                        ))
        return diff_lines

    @staticmethod
    def format(diff_lines: List['DiffHandler.DiffLine'], show_numbers: bool = True) -> str:
        """Format diff lines for display."""
        output = []
        num_width = 5

        for line in diff_lines:
            if show_numbers:
                old = str(line.old_number or '').rjust(num_width)
                new = str(line.new_number or '').rjust(num_width)
                prefix = f"{old}│{new}│"
            else:
                prefix = f"{line.type} "
            output.append(f"{prefix} {line.colorize()}")

        return "\n".join(output)

# Initialize global handlers
input_handler = InputHandler()
file_handler = FileHandler()
diff_handler = DiffHandler()

# Utility functions that use the handlers
def get_input(prompt: str, options: Optional[List[str]] = None, 
              default: Any = None, **kwargs) -> Any:
    """Get input with autocomplete support."""
    return input_handler.get_input(prompt, options, default, **kwargs)

def get_path_input(prompt: str, default: Optional[str] = None, 
                  root_dir: Optional[str] = None) -> str:
    """Get path input with filesystem autocomplete."""
    path = input_handler.get_input(prompt, default=default, path_mode=True)
    if root_dir and not os.path.isabs(os.path.expanduser(path)):
        return os.path.join(root_dir, path)
    return os.path.expanduser(path)

def get_valid_index(messages: List[Dict], prompt: str, default: int = -1) -> int:
    """Get valid message index with bounds checking."""
    def validate(value: str) -> bool:
        try:
            idx = int(value) if value else default
            return -len(messages) <= idx < len(messages)
        except ValueError:
            return False

    def transform(value: str) -> int:
        return int(value) if value else default

    return input_handler.get_input(
        f"Enter index of message to {prompt}",
        default=default,
        validator=validate,
        transform=transform
    )

def parse_cmd_string(raw_cmd: str) -> Tuple[str, int]:
    """Parse command string into command and index."""
    raw_cmd = raw_cmd.strip()
    if not raw_cmd:
        return "", -1

    patterns = [
        (r"^(\d+)([a-z]+)$", lambda m: (m.group(2), int(m.group(1)))),           # "123cmd"
        (r"^([a-z]+)(\d+)$", lambda m: (m.group(1), int(m.group(2)))),           # "cmd123"
        (r"^(\d+)-([a-z]+)$", lambda m: (m.group(2), -int(m.group(1)))),         # "1-cmd"
        (r"^([a-z]+)-(\d+)$", lambda m: (m.group(1), -int(m.group(2))))          # "cmd-1"
    ]

    for pattern, handler in patterns:
        if match := re.match(pattern, raw_cmd):
            return handler(match)

    return raw_cmd, -1

# Context managers
@contextmanager
def temp_file(suffix: Optional[str] = None, content: Optional[str] = None) -> Generator[str, None, None]:
    """Create and manage temporary file."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        if content is not None:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
        else:
            os.close(fd)
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)

# Image handling
def encode_image(image_path: str) -> str:
    """Encode image to base64."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        Colors.print_colored(f"Error encoding image: {e}", Colors.RED)
        return ""

# Token counting
def count_tokens(messages: List[Dict], model: str = "gpt-4") -> int:
    """Count tokens in messages."""
    content = "".join(
        msg["content"] if isinstance(msg["content"], str)
        else "".join(c["text"] for c in msg["content"] if c.get("type") == "text")
        for msg in messages
    )
    encoding = tiktoken.encoding_for_model(model)
    return 4 + len(encoding.encode(content))  # 4 for message formatting

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

# File operations utilities
def get_project_dir(args: Dict, default_name: str = "untitled") -> str:
    """Determine project directory based on command arguments."""
    ll_dir_abs = os.path.abspath(args.ll_dir)
    load_abs = os.path.abspath(args.load)
    rel = os.path.relpath(load_abs, ll_dir_abs)
    base, ext = os.path.splitext(rel)
    project_dir = get_path_input(os.path.join(args.exec_dir, rel or os.getcwd()), args.exec_dir)
    return project_dir

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
        
        old_content = file_handler.read(str(filepath)) or ""
        diff_lines = generate_diff(old_content, new_content)
        
        if non_interactive:
            if file_handler.write(str(filepath), new_content):
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
            if file_handler.write(str(filepath), new_content):
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
    def temp_file(self, suffix: Optional[str] = None, content: Optional[str] = None) -> Generator[str, None, None]:
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

# Compatibility layer for existing functions
def path_input(prompt: str, default: Optional[str] = None, base_dir: Optional[str] = None) -> str:
    return input_handler.get_path_input(prompt, default, base_dir)

def list_input(options: List[str], prompt: str = "", allow_custom: bool = True) -> str:
    """Get input from a list of options with number and text selection."""
    return input_handler.get_list_input(options, prompt, allow_custom)

def content_input(prompt: str = "Enter content") -> str:
    """Get input from the user."""
    return input_handler.get_input(prompt)

def get_valid_index(messages: List[Dict], prompt: str, default: int = -1) -> int:
    """Legacy compatibility function for getting valid message index."""
    if not messages:
        return default
    
    while True:
        try:
            idx_input = input(f"Enter index of message to {prompt} [{default}]: ").strip()
            if not idx_input:
                return default
            idx = int(idx_input)
            if -len(messages) <= idx < len(messages):
                return idx
            print(f"Index must be between {-len(messages)} and {len(messages)-1}")
        except ValueError:
            print("Please enter a valid number")

def llt_input(commands: List[str]) -> Tuple[str, int]:
    """Get user input with command autocompletion."""
    try:
        # Set up command completion
        def completer(text: str, state: int) -> Optional[str]:
            options = [cmd for cmd in commands if cmd.startswith(text.lower())]
            return options[state] if state < len(options) else None
            
        readline.set_completer(completer)
        readline.set_completer_delims(" \t\n;")
        if "libedit" in readline.__doc__:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
            
        # Get input with completion
        raw_input = input("llt> ").strip()
        return parse_cmd_string(raw_input)
        
    except (EOFError, KeyboardInterrupt):
        print("\nExiting...")
        sys.exit(0)
    finally:
        # Reset completer
        readline.set_completer(None)

def parse_cmd_string(raw_cmd: str) -> Tuple[str, int]:
    """Parse command string into command and index."""
    raw_cmd = raw_cmd.strip()
    if not raw_cmd:
        return "", -1

    patterns = [
        (r"^(\d+)([a-z]+)$", lambda m: (m.group(2), int(m.group(1)))),           # "123cmd"
        (r"^([a-z]+)(\d+)$", lambda m: (m.group(1), int(m.group(2)))),           # "cmd123"
        (r"^(\d+)-([a-z]+)$", lambda m: (m.group(2), -int(m.group(1)))),         # "1-cmd"
        (r"^([a-z]+)-(\d+)$", lambda m: (m.group(1), -int(m.group(2))))          # "cmd-1"
    ]

    for pattern, handler in patterns:
        if match := re.match(pattern, raw_cmd):
            return handler(match)

    return raw_cmd, -1

# New DiffHandler implementation
@dataclass
class DiffLine:
    type: str  # '+', '-', '~', ' '
    content: str
    old_number: Optional[int] = None
    new_number: Optional[int] = None

    def colorize(self) -> str:
        color_map = {
            '+': Colors.GREEN,
            '-': Colors.RED,
            '~': Colors.YELLOW,
            ' ': ''
        }
        return f"{color_map[self.type]}{self.content}{Colors.RESET}"

def generate_diff(old_content: str, new_content: str, context_lines: int = 3) -> str:
    """Generate a unified diff string from old_content to new_content."""
    differ = difflib.SequenceMatcher(None, old_content.splitlines(), new_content.splitlines())
    diff_lines = []
    
    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == 'equal':
            start = max(i1, i1 + (i2 - i1 - context_lines))
            end = min(i2, i1 + context_lines)
            for i in range(start, end):
                line = DiffLine(
                    type=' ',
                    content=old_content.splitlines()[i],
                    old_number=i + 1,
                    new_number=j1 + (i - i1) + 1
                )
                diff_lines.append(line)
        elif tag in ('replace', 'delete', 'insert'):
            if tag in ('replace', 'delete'):
                for i in range(i1, i2):
                    line = DiffLine(
                        type='-',
                        content=old_content.splitlines()[i],
                        old_number=i + 1
                    )
                    diff_lines.append(line)
            if tag in ('replace', 'insert'):
                for j in range(j1, j2):
                    line = DiffLine(
                        type='+',
                        content=new_content.splitlines()[j],
                        new_number=j + 1
                    )
                    diff_lines.append(line)
    
    return format_diff(diff_lines)

def format_diff(diff_lines: Union[List[DiffLine], str], show_numbers: bool = True) -> str:
    """Format diff lines for display."""
    if isinstance(diff_lines, str):
        return diff_lines
        
    output = []
    num_width = 5

    for line in diff_lines:
        if show_numbers:
            old = str(line.old_number or '').rjust(num_width)
            new = str(line.new_number or '').rjust(num_width)
            prefix = f"{old}│{new}│"
        else:
            prefix = f"{line.type} "
        output.append(f"{prefix} {line.colorize()}")

    return "\n".join(output)

def encode_image_to_base64(image_path: str) -> str:
    """Legacy compatibility function for image encoding."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        Colors.print_colored(f"Error encoding image: {e}", Colors.RED)
        return ""

def count_tokens(messages: List[Dict], model: str = "gpt-4") -> int:
    """Legacy compatibility function for token counting."""
    content = "".join(
        msg["content"] if isinstance(msg["content"], str)
        else "".join(c["text"] for c in msg["content"] if c.get("type") == "text")
        for msg in messages
    )
    encoding = tiktoken.encoding_for_model(model)
    return 4 + len(encoding.encode(content))

def parse_markdown_for_codeblocks(markdown: str) -> List[Dict]:
    """Legacy compatibility function for markdown parsing."""
    code_pattern = re.compile(r"```(\w+)\n(.*?)\n```", re.DOTALL)
    matches = code_pattern.findall(markdown)
    blocks = []
    
    for i, (language, code) in enumerate(matches):
        filename = None
        if language in language_comment_map:
            comment_prefix = language_comment_map[language]
            first_line = code.split('\n')[0].strip()
            if first_line.startswith(comment_prefix):
                potential_filename = first_line[len(comment_prefix):].strip()
                if potential_filename and '.' in potential_filename:
                    filename = potential_filename
        
        blocks.append({
            "language": language,
            "content": code.strip(),
            "filename": filename,
            "index": i
        })
    
    return blocks

def get_project_dir(args: Dict, default_name: str = "untitled") -> str:
    """Legacy compatibility function for getting project directory."""
    ll_dir_abs = os.path.abspath(args.get('ll_dir', ''))
    load_abs = os.path.abspath(args.get('load', ''))
    rel = os.path.relpath(load_abs, ll_dir_abs)
    project_dir = path_input(os.path.join(args.get('exec_dir', ''), rel or os.getcwd()), args.get('exec_dir'))
    return project_dir

# Initialize global handlers
temp_manager = TempFileManager()
backup_manager = BackupManager()

# Context managers
@contextmanager
def temp_file(suffix: Optional[str] = None, content: Optional[str] = None) -> Generator[str, None, None]:
    """Create and manage temporary file."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        if content is not None:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
        else:
            os.close(fd)
        yield path
    finally:
        if os.path.exists(path):
            os.remove(path)

def confirm_action(prompt: str) -> bool:
    """Prompt the user to confirm an action."""
    return input(f"{prompt} (y/N) [N]: ").strip().lower() == 'y'