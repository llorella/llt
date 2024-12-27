# utils.py
import os
import sys
import readline
import base64
import tiktoken
from PIL import Image
from math import ceil
import tempfile
from io import BytesIO
import pprint
from typing import List, Dict, Tuple
colors = {  
    'system': '\033[34m',    # blue
    'user': '\033[32m',      # green
    'assistant': '\033[35m', # magenta
    'reset': '\033[0m'
}


# ANSI escape codes for colors and styles
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
        """Print text with the specified ANSI color."""
        print(f"{color}{text}{Colors.RESET}")

    @staticmethod
    def print_bold(text: str, color: str = "") -> None:
        """Print bold text with the specified ANSI color."""
        print(f"{Colors.BOLD}{color}{text}{Colors.RESET}")

    @staticmethod
    def pretty_print_dict(message: Dict) -> None:
        """Pretty-print a dictionary with indentation."""
        formatted_message = pprint.pformat(message, indent=4)
        Colors.print_colored(formatted_message, Colors.WHITE)

    @staticmethod
    def print_header():
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("***** Welcome to llt, the little language terminal. *****", Colors.WHITE)
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("*********************************************************\n", Colors.YELLOW)

def path_completer(text, state):
    """Autocomplete file and directory paths."""
    # Expand user home directory shortcut
    text = os.path.expanduser(text)
    # If text is a directory, list its contents
    if os.path.isdir(text):
        entries = os.listdir(text)
        entries = [
            os.path.join(text, entry)
            + ("/" if os.path.isdir(os.path.join(text, entry)) else "")
            for entry in entries
        ]
    else:
        # Get the directory and basename
        dirname = os.path.dirname(text) or "."
        basename = os.path.basename(text)
        try:
            entries = [
                os.path.join(dirname, entry)
                + ("/" if os.path.isdir(os.path.join(dirname, entry)) else "")
                for entry in os.listdir(dirname)
                if entry.startswith(basename)
            ]
        except FileNotFoundError:
            entries = []
    # Remove duplicates and sort
    matches = sorted(set(entries))
    try:
        return matches[state]
    except IndexError:
        return None

def path_input(default_file: str = None, root_dir: str = None) -> str:
    """Prompt the user to input a file or directory path with autocomplete."""
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
        # Adjust the returned value to remove root_dir
        completion = path_completer(full_text, state)
        if completion:
            # Remove root_dir from the beginning if present
            if root_dir and completion.startswith(root_dir):
                completion = os.path.relpath(completion, root_dir)
            return completion
        else:
            return None

    readline.set_completer(completer)
    try:
        prompt_text = f"Enter {'file' if root_dir else 'directory'} path"
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
    """Create a completer function for a list of values."""

    def completer(text, state):
        matches = [value for value in values if value.startswith(text)]
        try:
            return matches[state]
        except IndexError:
            return None

    return completer


def list_input(values: List[str], input_string: str = "Enter a value from list") -> str:
    """Prompt the user to select a value from a list with autocomplete."""
    readline.set_completer_delims(" \t\n;")
    if "libedit" in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
    readline.set_completer(list_completer(values))
    try:
        return input(
            f"{input_string} (tab to autocomplete): {Colors.RESET}"
        )
    finally:    
        readline.set_completer(None)

def content_input(display_string: str = "Enter content below.") -> str:
    print(display_string)
    Colors.print_colored("*********************************************************", Colors.YELLOW)
    content = input("> ") or ""
    Colors.print_colored("\n*********************************************************\n", Colors.YELLOW)
    return content

def llt_input(plugin_keys: List[str]) -> Tuple[str, int]:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(list_completer(plugin_keys))

    raw_cmd = input("llt> ")
    if raw_cmd and raw_cmd[:-1].isdigit() and raw_cmd[-1].isalpha():
        # If command follows the pattern: number + letter (e.g., "2v")
        index = int(raw_cmd[:-1])
        cmd = raw_cmd[-1]
    elif raw_cmd and raw_cmd[:1].isdigit() and raw_cmd[1] == '-' and raw_cmd[2:].isalpha():
        # If command follows the pattern: -number + letter (e.g., "-2v") for last n items
        index = -int(raw_cmd[1:-1])
        cmd = raw_cmd[-1]
    elif raw_cmd and raw_cmd[-1::].isdigit() and raw_cmd[:1].isalpha():
        # If command follows the pattern: letter + number (e.g., "v2")
        index = int(raw_cmd[-1:])
        cmd = raw_cmd[:-1]
    else:
        cmd = raw_cmd  # Regular command without index
        index = -1
        
    return cmd, index



def count_image_tokens(file_path: str) -> int:
    """Count tokens in an image based on its dimensions."""

    def resize(width, height):
        if width > 1024 or height > 1024:
            if width > height:
                height = int(height * 1024 / width)
                width = 1024
            else:
                width = int(width * 1024 / height)
                height = 1024
        return width, height

    def count_image_tokens_resized(width: int, height: int):
        width, height = resize(width, height)
        h = ceil(height / 512)
        w = ceil(width / 512)
        total = 85 + 170 * h * w
        return total

    with Image.open(file_path) as image:
        width, height = image.size
        return count_image_tokens_resized(width, height)


def encode_image_to_base64(image_path: str, max_dimension: int = 1568) -> str:
    """
    Encodes an image to a base64 string after resizing if necessary.
    
    Args:
        image_path (str): The file path to the image.
        max_dimension (int): The maximum allowed dimension (width or height).
        
    Returns:
        str: Base64 encoded string of the image.
        
    Raises:
        FileNotFoundError: If the image file does not exist.
        ValueError: If the image format is unsupported.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    supported_formats = ('.jpeg', '.jpg', '.png', '.gif', '.webp')
    if not image_path.lower().endswith(supported_formats):
        raise ValueError(f"Unsupported image format for file: {image_path}")
    
    # Resize image if necessary
    
    resized_image_path = image_path
    
    with open(resized_image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    
    # Optionally, remove the resized image if it's a temporary file
    if resized_image_path != image_path:
        os.remove(resized_image_path)
    
    return encoded_string


def encoded_img_to_pil_img(data_str: str):
    """Convert a base64 string back to a PIL Image."""
    base64_str = data_str.replace("data:image/png;base64,", "")
    image_data = base64.b64decode(base64_str)
    return Image.open(BytesIO(image_data))


def save_to_tmp_img_file(data_str: str) -> str:
    """Save a base64-encoded image string to a temporary file."""
    image = encoded_img_to_pil_img(data_str)
    tmp_dir = tempfile.mkdtemp()
    tmp_img_path = os.path.join(tmp_dir, "tmp_img.png")
    image.save(tmp_img_path)
    return tmp_img_path


# Message utilities
def tokenize(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> int:
    num_tokens, content = 0, ""
    for msg in messages:
        msg_content = msg["content"]
        if isinstance(msg_content, list):
            for item in msg_content:
                if item["type"] == "text":
                    content += item["text"]
                # elif item['type'] == 'image_url':
                #     num_tokens += count_image_tokens(item['image_url']['url'])
        else:
            content += msg_content
    encoding = tiktoken.encoding_for_model("gpt-4")
    num_tokens += 4 + len(encoding.encode(content))
    print(f"{Colors.BOLD}{Colors.BLUE}Tokens:{Colors.RESET} {num_tokens}")
    return num_tokens


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


# Miscellaneous utilities
language_extension_map = {
    ".py": "python",
    ".sh": "shell",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".c": "c",
    ".cpp": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".csv": "csv",
    ".cu": "cuda",
}


def inverse_kv_map(d: Dict) -> Dict:
    """Invert a key-value mapping."""
    return {v: k for k, v in d.items()}


def is_base64(text: str) -> bool:
    """Check if a string is base64-encoded."""
    try:
        base64.b64decode(text)
        return True
    except Exception as e:
        Colors.print_colored(f"Error decoding base64: {e}", Colors.RED)
        return False

def quit_program(messages: List, args: Dict, index: int = -1) -> None:
    sys.exit(0)
