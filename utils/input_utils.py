import os
import readline
from typing import List, Dict, Tuple, Optional, Callable

from utils.colors import Colors

def path_completer(text: str, state: int) -> Optional[str]:
    """Tab completion for file paths."""
    text = os.path.expanduser(text)
    if os.path.isdir(text):
        entries = os.listdir(text)
        entries = [
            os.path.join(text, e) + ('/' if os.path.isdir(os.path.join(text, e)) else '')
            for e in entries
        ]
    else:
        dirname = os.path.dirname(text) or "."
        basename = os.path.basename(text)
        try:
            entries = [
                os.path.join(dirname, e) + ('/' if os.path.isdir(os.path.join(dirname, e)) else '')
                for e in os.listdir(dirname)
                if e.startswith(basename)
            ]
        except FileNotFoundError:
            entries = []
    matches = sorted(set(entries))
    return matches[state] if state < len(matches) else None

def setup_readline_completer(completer: Callable) -> None:
    """Configure readline with given completer."""
    readline.set_completer_delims(' \t\n;')
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind('bind ^I rl_complete')
    else:
        readline.parse_and_bind('tab: complete')
    readline.set_completer(completer)

def path_input(default_path: Optional[str] = None, root_dir: Optional[str] = None) -> str:
    """Prompt for file path with tab completion."""
    try:
        def complete_path(text, state):
            if root_dir and not os.path.isabs(os.path.expanduser(text)):
                full_text = os.path.join(root_dir, text)
            else:
                full_text = text
            completion = path_completer(full_text, state)
            if completion and root_dir and completion.startswith(root_dir):
                completion = os.path.relpath(completion, root_dir)
            return completion

        setup_readline_completer(complete_path)
        
        prompt = "Enter file path"
        if default_path:
            prompt += f" (default: {default_path})"
        path = input(f"{prompt}: ") or default_path

        if root_dir and path:
            return os.path.join(root_dir, os.path.expanduser(path))
        return os.path.expanduser(path or '')
        
    finally:
        readline.set_completer(None)

def list_completer(values: List[str]) -> Callable:
    """Create completer function for list of values."""
    def completer(text: str, state: int) -> Optional[str]:
        matches = [v for v in values if v.startswith(text)]
        try:
            return matches[state]
        except IndexError:
            return None
    return completer

def list_input(values: List[str], prompt: str = "Enter a value from list") -> str:
    """Get input with list completion."""
    setup_readline_completer(list_completer(values))
    try:
        return input(f"{prompt} (tab to autocomplete): ")
    finally:
        readline.set_completer(None)

def get_valid_index(messages: List[Dict], prompt: str, default: int = -1) -> int:
    """Get valid message index from user input."""
    try:
        idx = input(f"Enter index of message to {prompt} (default {default}): ").strip() or default
        if not idx:
            return default
        idx = int(idx) % len(messages)  # Support negative indexing
    except ValueError:
        print("Invalid input. Using default.")
        idx = default
        
    if not -len(messages) <= idx < len(messages):
        raise IndexError("Index out of range")
        
    return idx

def llt_input(plugin_keys: List[str]) -> Tuple[str, int]:
    """Get command input with plugin completion."""
    setup_readline_completer(list_completer(plugin_keys))
    try:
        raw_cmd = input("llt> ")
        
        # Parse command and index
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
    finally:
        readline.set_completer(None) 

def confirm_action(prompt: str) -> bool:
    """Confirm an action with user input."""
    return input(f"{prompt} (y/n): ").lower() == 'y'