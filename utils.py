# @utils.py
# Combined utilities from utils/

import os
import shutil
from datetime import datetime
import difflib
import readline
import base64
from typing import List, Dict, Tuple, Optional, Any, Callable, TypeVar, Union, Sequence, Generator, Iterator
from dataclasses import dataclass
import shlex
from contextlib import contextmanager
import tempfile
import tiktoken
import pyperclip
from pathlib import Path
import re

# Type aliases
T = TypeVar('T')
InputValue = Union[str, int, float, bool, List[str], Dict[str, Any]]

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
        if readline.__doc__ and "libedit" in readline.__doc__:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
    def _create_completer(self, 
                         options: Optional[List[str]] = None, 
                         path_mode: bool = False,
                         root_dir: Optional[str] = None) -> Callable[[str, int], Optional[str]]:
        """Create a completer function based on mode."""
        def path_completer(text: str, state: int) -> Optional[str]:
            text = os.path.expanduser(text)
            if root_dir and not os.path.isabs(text):
                text = os.path.join(root_dir, text)
            
            dir_path = os.path.dirname(text) or "."
            try:
                if os.path.isdir(text):
                    files = os.listdir(text)
                else:
                    base = os.path.basename(text)
                    files = [f for f in os.listdir(dir_path) if f.startswith(base)]
                files = [os.path.join(dir_path, f) + ('/' if os.path.isdir(os.path.join(dir_path, f)) else '')
                        for f in files]
                
                # Make paths relative to root_dir if specified
                if root_dir:
                    files = [os.path.relpath(f, root_dir) for f in files]
                    
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
                 root_dir: Optional[str] = None,
                 validator: Optional[Callable[[str], bool]] = None,
                 transform: Optional[Callable[[str], Any]] = None) -> Any:
        """
        Enhanced input handling with autocomplete, validation, and transformation.
        
        Args:
            prompt: Input prompt text
            options: List of autocomplete options
            default: Default value if input is empty
            path_mode: Enable path completion mode
            root_dir: Base directory for path completion
            validator: Optional validation function
            transform: Optional transformation function
        """
        readline.set_completer(self._create_completer(options, path_mode, root_dir))
        
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

    def get_path_input(self, 
                      prompt: str,
                      default: Optional[str] = None,
                      root_dir: Optional[str] = None) -> str:
        """Get path input with filesystem autocomplete."""
        result = self.get_input(
            prompt,
            default=default,
            path_mode=True,
            root_dir=root_dir
        ).strip()  # Strip any trailing whitespace
    
            
        # Handle path resolution
        if root_dir and not os.path.isabs(os.path.expanduser(result)):
            return os.path.join(root_dir, result)
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
            return value.strip() # Trim custom input
        
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


def get_valid_index(messages: Sequence[Dict], prompt: str, default: int = -1) -> int:
    """Get a valid index from the user for a list of messages."""
    if not messages:
        return default

    def validate(value: str) -> bool:
        try:
            idx = int(value) if value else default
            return -len(messages) <= idx < len(messages)
        except ValueError:
            return False

    def transform(value: str) -> int:
        idx = int(value) if value else default
        return idx if idx >= 0 else len(messages) + idx
    return input_handler.get_input(
        f"Enter index of message to {prompt}",
        default=default,
        validator=validate,
        transform=transform
    )

def parse_interactive_input(input_str: str) -> Tuple[str, Optional[str], Optional[int]]:
    """Parse interactive input into command, value, and (0-based) index.

    Handles simple quoted arguments using shlex.
    Prioritizes checking the last part for an integer index.
    Examples:
    'load my_file.ll'       -> ('load', 'my_file.ll', None)
    'prompt "hello world"'    -> ('prompt', 'hello world', None)
    'remove 3'              -> ('remove', None, 2)  # Positive index becomes 0-based
    'attach temp.ll -1'     -> ('attach', 'temp.ll', -1) # Negative index preserved
    'load temp -1'          -> ('load', 'temp', -1)
    'my_command val1 val2 5'  -> ('my_command', 'val1 val2', 4)
    'help'                  -> ('help', None, None)
    ''                      -> ('', None, None)
    """
    if not input_str:
        return "", None, None

    try:
        parts = shlex.split(input_str)
    except ValueError:
        # Basic fallback for unmatched quotes
        parts = input_str.split()

    if not parts:
         return "", None, None

    cmd = parts[0]
    value = None
    index = None # Internal index (0-based for positive, kept as-is for negative)

    # Check if the last part is an integer index
    if len(parts) >= 2:
        try:
            potential_index = int(parts[-1])
            # If successful, treat the last part as the index
            index = potential_index - 1 if potential_index > 0 else potential_index
            # The value is everything between the command and the index
            if len(parts) > 2:
                value = " ".join(parts[1:-1])
            # else: value remains None (e.g., 'remove 3')
            return cmd, value, index
        except ValueError:
            # Last part is not an integer, treat all parts after cmd as value
            value = " ".join(parts[1:])
    # else: Only command was provided, value and index remain None

    return cmd, value, index # Index will be None here

def llt_interactive_input(command_list: List[str]) -> Tuple[str, Optional[str], Optional[int]]:
    """Prompt user for command, handle tab completion, parse using parse_interactive_input.

    Returns command name, optional value string, and optional 0-based index.
    """
    completer = None
    try:
        import readline
        
        def _completer(text, state):
            options = [cmd for cmd in command_list if cmd.startswith(text)]
            return options[state] if state < len(options) else None
        
        completer = _completer # Assign the inner function
        readline.set_completer(completer)
        # Use common delimiters including space
        readline.set_completer_delims(' \t\n`~!@#$%^&*()-=+[{]}\\|;\'",<>/?')
        readline.parse_and_bind('tab: complete')
    except ImportError:
        pass # Readline not available

    try:
        input_str = input("\nllt> ").strip()
    finally:
        # Reset completer if readline was used
        try:
            import readline
            if completer is not None:
                readline.set_completer(None)
        except ImportError:
            pass

    cmd, value, index = parse_interactive_input(input_str)

    return cmd, value, index

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
    # Simplified language detection based on common keywords
    indicators = {
        'python': ['def ', 'import ', 'class ', 'if __name__'],
        'javascript': ['function ', 'const ', 'let ', 'var '],
        'typescript': ['interface ', 'type ', '<T>', ': string'],
        'html': ['<!DOCTYPE', '<html', '<div', '<body'],
        'css': ['{', '@media', '#', '.class'], # CSS detection simplified
        'shell': ['#!/bin/', 'echo ', 'export ', 'sudo '],
        'rust': ['fn ', 'impl ', 'pub ', 'use '],
        'go': ['func ', 'package ', 'import (', 'type '],
        'java': ['public class', 'import java.', 'System.out.println'],
        'c': ['#include', 'int main', 'printf'],
        'cpp': ['#include', 'std::cout', 'int main'],
        'sql': ['SELECT ', 'INSERT ', 'UPDATE ', 'CREATE TABLE'],
        'yaml': [': ', '- '], # Basic YAML indicators
    }
    # Lowercase content once for efficiency
    content_lower = content.lower()
    lines = content_lower.splitlines()

    # Check first few lines and keywords
    line_limit = min(10, len(lines))
    content_sample = "\n".join(lines[:line_limit])

    for lang, patterns in indicators.items():
        if any(pattern.lower() in content_sample for pattern in patterns):
             # Add extra check for shell scripts starting with shebang
             if lang == 'shell' and lines and lines[0].startswith('#!'):
                  return lang
             elif lang != 'shell': # Avoid matching generic patterns too easily
                  return lang

    # If no specific language detected, return None or 'text'
    return None

def parse_markdown_for_codeblocks(markdown: str) -> List[Dict]:
    """Parse markdown and extract code blocks with metadata, including filename."""
    blocks = []
    # Regex to find code blocks, capturing language/filename and content
    # Handles optional language/filename on the first line
    code_pattern = re.compile(r"```(\S*)?\s*\n(.*?)\n```", re.DOTALL)

    # Regex to find potential filenames within comments (simple version)
    filename_comment_pattern = re.compile(r'(?:#|//|--|/\*)\s*file:\s*(\S+)', re.IGNORECASE)
    # Simple fuzzy filename pattern (e.g., path/to/file.py)
    fuzzy_filename_pattern = re.compile(r'\b(?:[a-zA-Z0-9._-]+/)*[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}\b')

    for i, match in enumerate(code_pattern.finditer(markdown)):
        first_line_token = match.group(1) or ""  # Language or potential filename
        content = match.group(2).strip()
        language = "text"  # Default
        filename = None

        # Try to determine filename directly from the first line token
        if '.' in first_line_token:  # Likely a filename
            filename = first_line_token
            _, ext = os.path.splitext(filename)
            ext = ext.lstrip('.')
            # Map extension to language
            for lang_key, lang_ext in language_extension_map.items():
                if lang_ext.lstrip('.') == ext:
                    language = lang_key
                    break
            if language == "text":  # If mapping failed, use extension itself
                language = ext if ext else "text"
        elif first_line_token:  # Likely a language identifier
            language = first_line_token.lower()

        # If filename wasn't on the first line, try searching comments
        if not filename:
            comment_match = filename_comment_pattern.search(content.split('\n', 5)[0])  # Check first few lines
            if comment_match:
                filename = comment_match.group(1)
            else:
                # Try fuzzy matching if no explicit comment found
                fuzzy_match = fuzzy_filename_pattern.search(content.split('\n', 5)[0])
                if fuzzy_match:
                    # Be cautious with fuzzy matches, might be URLs or other strings
                    potential_fn = fuzzy_match.group(0)
                    # Basic sanity check (avoid overly long strings, etc.)
                    if len(potential_fn) < 100 and potential_fn.count('.') < 5:
                        filename = potential_fn

        # Fallback: Use detected language if identifier wasn't valid language
        if language not in language_extension_map and language not in language_comment_map:
            detected_lang = detect_language_from_content(content)
            if detected_lang:
                language = detected_lang

        blocks.append({
            "index": i,
            "language": language,
            "content": content,
            "filename": filename  # May be None
        })

    return blocks
# File operations utilities
def get_project_dir(args: Dict[str, Any]) -> str:
    """Determine project directory based on command arguments."""
    # Ensure LLT_PATH is handled if None
    llt_path = os.getenv('LLT_PATH', '.')
        
    exec_dir = args.get('exec_dir', os.path.join(llt_path, 'exec'))

    # Use current working directory if 'load' is not specified
    load_path = args.get("load")
    
    if load_path and not load_path.endswith('.ll'):
        # When load is specified, project dir should be under exec_dir with same name
        project_dir = os.path.join(exec_dir, load_path)
    else:
        # If no 'load' specified, default to execution directory
        project_dir = os.getcwd()

    # Use input_handler to get the project directory path if interactive
    if not args.get('non_interactive'):
        # Get raw input first to check for "."
        user_input = input_handler.get_input(
            "Enter project directory",
            default=project_dir, # Still provide the calculated default
            path_mode=True, # Keep path completion
            root_dir=exec_dir # Keep completion relative to exec_dir
        )

        if user_input == ".":
            project_dir = os.getcwd()
        elif user_input: # Check if user provided non-empty input other than "."
             # Use the input value, potentially resolving relative to exec_dir
             resolved_path = os.path.expanduser(user_input)
             if exec_dir and not os.path.isabs(resolved_path):
                  project_dir = os.path.join(exec_dir, resolved_path)
             else:
                  project_dir = resolved_path

    # Ensure the final path is absolute and normalized
    return os.path.abspath(project_dir)

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


def confirm_action(prompt: str) -> bool:
    """Prompt the user to confirm an action."""
    # Use input_handler for consistency, though basic input is fine here
    response = input_handler.get_input(f"{prompt} (y/N)", default='n')
    return response.lower() == 'y'


class BackupManager:
    def __init__(self):
        self.backups = []

    def create_backup(self, filepath: str) -> None:
        backup_path = f"{filepath}.backup"
        try:
            shutil.copy2(filepath, backup_path)
            self.backups.append(backup_path)
        except Exception as e:
            Colors.print_colored(f"Error creating backup: {e}", Colors.RED)

backup_manager = BackupManager()


def iter_blocks(
    message: Dict,
    predicate: Optional[Callable[[Dict], bool]] = None,
    transform: Optional[Callable[[Dict], Dict]] = None
) -> Iterator[Dict]:
    """
    Iterate through code blocks in a given message's content.
    Uses parse_markdown_for_codeblocks utility. Handles potential non-string content.
    """
    content = message.get("content", "")
    if not isinstance(content, str):
         if isinstance(content, list):
              text_parts = [str(part) for part in content if isinstance(part, (str, int, float))]
              content = "\\n".join(text_parts)
         else:
              Colors.print_colored("Warning: Cannot iterate blocks on non-text/list content.", Colors.YELLOW)
              return iter([])

    if not callable(parse_markdown_for_codeblocks):
        Colors.print_colored("Error: parse_markdown_for_codeblocks is not available.", Colors.RED)
        return iter([])

    blocks = parse_markdown_for_codeblocks(content)
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if not predicate or predicate(block):
            yield transform(block) if transform else block
