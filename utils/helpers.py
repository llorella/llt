# utils/helpers.py

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
        # simpler header
        Colors.print_colored("***** Welcome to llt, the little language terminal *****", Colors.YELLOW)

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

def llt_input(plugin_keys: List[str]) -> Tuple[str, int]:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(list_completer(plugin_keys))

    raw_cmd = input("llt> ")
    if raw_cmd and raw_cmd[:-1].isdigit() and raw_cmd[-1].isalpha():
        index = int(raw_cmd[:-1])
        cmd = raw_cmd[-1]
    elif raw_cmd and raw_cmd[:1].isdigit() and raw_cmd[1] == '-' and raw_cmd[2:].isalpha():
        index = -int(raw_cmd[1:-1])
        cmd = raw_cmd[-1]
    elif raw_cmd and raw_cmd[-1:].isdigit() and raw_cmd[:1].isalpha():
        index = int(raw_cmd[-1:])
        cmd = raw_cmd[:-1]
    else:
        cmd = raw_cmd
        index = -1
    return cmd, index

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
    # example function
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
