# plugins/__init__.py

import os
import importlib.util
from typing import Callable, Dict, Any, Optional
from logger import llt_logger
import argparse
import re
from collections import deque
from dataclasses import dataclass
import sys

_plugins_registry: Dict[str, Dict[str, Any]] = {}


def llt(fn: Callable) -> Callable:
    """
    Decorator that registers a plugin by parsing its docstring.

    Each docstring should contain lines in the format:

        Description: ...
        Type: ...
        Default: ...
        flag: ...
        short: ...

    Example:
        @llt
        def example(...):
            \"\"\"
            Description: Example plugin
            Type: bool
            Default: false
            flag: example
            short: e
            \"\"\"
            ...

    We'll store these in _plugins_registry for later argument parsing and command mapping.
    """
    doc = fn.__doc__ or ""

    desc_match = re.search(r"Description:\s*(.*)", doc)
    type_match = re.search(r"Type:\s*(.*)", doc)
    default_match = re.search(r"Default:\s*(.*)", doc)
    flag_match = re.search(r"flag:\s*(.*)", doc)
    short_match = re.search(r"short:\s*(.*)", doc)

    description = desc_match.group(1).strip() if desc_match else fn.__name__
    arg_type = type_match.group(1).strip() if type_match else None
    default = default_match.group(1).strip() if default_match else None
    flag = flag_match.group(1).strip() if flag_match else fn.__name__
    short = short_match.group(1).strip() if short_match else None

    _plugins_registry[fn.__name__] = {
        'function': fn,
        'description': description,
        'type': arg_type,
        'default': default if default != "None" else None,
        'flag': flag,
        'short': short
    }
    return fn


def add_plugin_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Create argparse flags from the collected plugin registry.
    """
    used_flags = set()
    used_shorts = set()

    for plugin_name, info in _plugins_registry.items():
        flag_str = info['flag']
        if info['type'] is None:
            continue
        short_str = info['short']
        description = info['description']
        arg_type = info['type']
        default_val = info['default']

        if flag_str in used_flags:
            llt_logger.warning(f"Duplicate plugin flag '{flag_str}' in {plugin_name}")
        used_flags.add(flag_str)

        cli_flags = [f"--{flag_str}"]
        if short_str:
            if short_str in used_shorts:
                llt_logger.warning(f"Duplicate short flag '-{short_str}' in {plugin_name}")
            else:
                cli_flags.append(f"--{short_str}")
            used_shorts.add(short_str)

        if arg_type in ("bool", "boolean"):
            parser.add_argument(
                *cli_flags,
                action='store_true',
                default=(str(default_val).lower() == "true"),
                help=description
            )
        elif arg_type in ("int", "float"):
            py_type = int if arg_type == "int" else float
            try:
                default_conv = py_type(default_val)
            except (ValueError, TypeError):
                default_conv = None
            parser.add_argument(
                *cli_flags,
                type=py_type,
                default=default_conv,
                help=description
            )
        else:
            parser.add_argument(
                *cli_flags,
                type=str,
                default=default_val,
                help=description
            )

def load_plugins(plugin_dir: str) -> None:
    """
    Dynamically load Python scripts from 'plugin_dir'.
    Each script can import @llt from here to register functions.
    """
    if not os.path.isdir(plugin_dir):
        return

    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            file_path = os.path.join(plugin_dir, filename)
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            try:
                module = importlib.util.module_from_spec(spec)
                if module and spec.loader:
                    spec.loader.exec_module(module)
            except ImportError as e:
                llt_logger.log_error(f"Failed to import {module_name}", {"error": str(e)})


def help(messages, args, index):
    print(', '.join(_plugins_registry.keys()))
    return messages


def quit(messages, args, index):
    exit(0)

def init_cmd_map() -> Dict[str, Callable]:
    """Initialize a command map with plugin commands and their abbreviations."""
    n_abbv = lambda s, n=1: s[:n].lower()
    cmd_map = {}
    for _, info in _plugins_registry.items():
        cmd_name = info['flag']
        if cmd_name not in cmd_map:
            cmd_map[cmd_name] = info['function']
        if n_abbv(cmd_name) not in cmd_map:
            cmd_map[n_abbv(cmd_name)] = info['function']
        elif len(cmd_name) > 2 and n_abbv(cmd_name, 2) not in cmd_map:
            cmd_map[n_abbv(cmd_name, 2)] = info['function']
        seps = ["-", "_"]
        for sep in seps:
            split_cmd = cmd_name.split(sep)
            if split_cmd:
                cmd_map[split_cmd[0]] = info['function']
                
    cmd_map["h"] = cmd_map["help"] = help
    cmd_map["q"] = cmd_map["quit"] = quit
    
    return cmd_map

@dataclass
class ScheduledCommand:
    """Command to be executed, whether from CLI args or interactive input"""
    name: str  # Command name/flag
    index: int  # Position in message list or -1
    args: Optional[dict] = None  # Any additional args needed for command

def schedule_startup_commands(args) -> deque[ScheduledCommand]:
    """Schedule CLI plugin args into a queue of commands to execute in order they were serialized"""
    command_queue: deque[ScheduledCommand] = deque()
    
    # Create mapping of flag variations to plugin names
    flag_to_plugin = {}
    for plugin_name, info in _plugins_registry.items():
        flag = info['flag']
        short = info['short']
        flag_to_plugin[f"--{flag}"] = flag
        if short:
            flag_to_plugin[f"--{short}"] = flag
    
    # Iterate through sys.argv to maintain original order
    for arg in sys.argv[1:]:  # Skip script name
        # Strip leading dashes and check if it's a boolean flag
        stripped_arg = arg.lstrip('-')
        if arg in flag_to_plugin:  # Full flag match
            flag = flag_to_plugin[arg]
            if hasattr(args, flag) and getattr(args, flag):
                command_queue.append(ScheduledCommand(flag, -1))
        elif stripped_arg in [info['flag'] for _, info in _plugins_registry.items()]:
            # Direct flag name match (for cases where arg might be after an =)
            if hasattr(args, stripped_arg) and getattr(args, stripped_arg):
                command_queue.append(ScheduledCommand(stripped_arg, -1))
    
    return command_queue