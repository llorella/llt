"""
input_handler.py - Input handling utilities for LLT

This module provides functions for interactive command input and parsing.
"""

import readline
import shlex
import os
from typing import Any, Dict, List, Optional, Tuple

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
        def _completer(text, state):
            options = [cmd for cmd in command_list if cmd.startswith(text)]
            return options[state] if state < len(options) else None
        
        completer = _completer # Assign the inner function
        readline.set_completer(completer)
        # Use common delimiters including space
        readline.set_completer_delims(' \t\n`~!@#$%^&*()-=+[{]}\\|;\'",<>/?')
        
        # Configure readline based on platform
        if readline.__doc__ and 'libedit' in readline.__doc__:
            # macOS
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            # Linux/Unix
            readline.parse_and_bind("tab: complete")
    except (ImportError, AttributeError):
        pass # Readline not available or doesn't support completion

    try:
        input_str = input("\nllt> ").strip()
    finally:
        # Reset completer if readline was used
        try:
            if completer is not None:
                readline.set_completer(None)
        except (ImportError, AttributeError):
            pass

    cmd, value, index = parse_interactive_input(input_str)

    return cmd, value, index

def get_path_input(prompt: str, default: Optional[str] = None, root_dir: Optional[str] = None) -> Optional[str]:
    """
    Prompt the user for a file path.
    
    Args:
        prompt: The prompt to display to the user
        default: Default value if the user presses Enter without input
        root_dir: Root directory to use for relative paths
        
    Returns:
        The selected path or None if the user cancels
    """
    try:
        prompt_text = f"{prompt} (default: {default}): " if default else f"{prompt}: "
        path = input(prompt_text).strip()
        
        if not path and default is not None:
            path = default
            
        # Handle relative paths
        if path and root_dir and not os.path.isabs(path):
            path = os.path.join(root_dir, path)
            
        return os.path.expanduser(path) if path else None
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled")
        return None


def get_input(prompt: str, options: Optional[List[str]] = None) -> Optional[str]:
    """Read one interactive value, optionally constrained to known options."""

    suffix = f" ({', '.join(options)}): " if options else ": "
    while True:
        try:
            value = input(f"{prompt}{suffix}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled")
            return None
        if not options or value in options:
            return value
        print(f"Expected one of: {', '.join(options)}")

def get_valid_index(messages: List[Dict], prompt: str, default: int = -1) -> int:
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
        
    # Simple command-line input since we don't have the full input_handler class
    while True:
        try:
            prompt_text = f"Enter index of message to {prompt} (default {default}): "
            value = input(prompt_text).strip()
            
            if not value and default is not None:
                return default
                
            if not validate(value):
                print(f"Invalid index. Please enter a number between {-len(messages)} and {len(messages)-1}")
                continue
                
            return transform(value)
        except (KeyboardInterrupt, EOFError):
            return default
