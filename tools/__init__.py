# tools/__init__.py

import os
import importlib.util
from typing import Callable, Dict, Any, Optional, List, Tuple, TypeVar, cast, Union
from logger import llt_logger
import argparse
import re
from collections import deque
from dataclasses import dataclass
import sys
import json
from datetime import datetime

_tools_registry: Dict[str, Dict[str, Any]] = {}

# Export symbols for tool authors
__all__ = ['llt', 'ScheduledCommand', 'ToolResult']

# Type aliases for tool return values
T = TypeVar('T')
Messages = List[Dict[str, Any]]
CommandsToQueue = List['ScheduledCommand']
ToolResult = Union[Messages, Tuple[Messages, CommandsToQueue]]

def llt(fn: Callable) -> Callable:
    """
    Decorator that registers a tool by parsing its docstring.

    Each docstring should contain lines in the format:

        Description: ...
        Type: ...
        Default: ...
        flag: ...
        short: ...

    Example:
        @llt
        def example(messages, context, index=-1):
            \"\"\"
            Description: Example tool
            Type: bool
            Default: false
            flag: example
            short: e
            \"\"\"
            ...

    We'll store these in _tools_registry for later argument parsing and command mapping.
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

    _tools_registry[fn.__name__] = {
        'function': fn,
        'description': description,
        'type': arg_type,
        'default': default if default != "None" else None,
        'flag': flag,
        'short': short
    }
    return fn


def add_tool_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Create argparse flags from the collected tool registry.
    """
    used_flags = set()
    used_shorts = set()

    for tool_name, info in _tools_registry.items():
        flag_str = info['flag']
        if info['type'] is None:
            continue
        short_str = info['short']
        description = info['description']
        arg_type = info['type']
        default_val = info['default']

        if flag_str in used_flags:
            llt_logger.log_info(f"Duplicate tool flag '{flag_str}' in {tool_name}", {"tool": tool_name})
        used_flags.add(flag_str)

        cli_flags = [f"--{flag_str}"]
        if short_str:
            if short_str in used_shorts:
                llt_logger.log_info(f"Duplicate short flag '-{short_str}' in {tool_name}", {"tool": tool_name})
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

def load_tools(tool_dir: str) -> None:
    """
    Dynamically load Python scripts from 'tool_dir'.
    Each script can import @llt from here to register functions.
    """
    if not os.path.isdir(tool_dir):
        return

    for filename in os.listdir(tool_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            file_path = os.path.join(tool_dir, filename)
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                try:
                    module = importlib.util.module_from_spec(spec)
                    if module:
                        spec.loader.exec_module(module)
                except ImportError as e:
                    llt_logger.log_error(f"Failed to import {module_name}", {"error": str(e)})
            else:
                llt_logger.log_error(f"Could not load spec for tool: {module_name}", {"path": file_path})

    # Generate the tool spec after loading all tools
    generate_tool_spec(os.path.join(os.environ.get("LLT_PATH", "~/.llt"), "tool_spec.json"))


def help(messages, context, index):
    print(', '.join(_tools_registry.keys()))
    return messages


def quit(messages, context, index):
    exit(0)

def init_cmd_map() -> Dict[str, Callable]:
    """Initialize a command map with tool commands and their abbreviations."""
    n_abbv = lambda s, n=1: s[:n].lower()
    cmd_map = {}
    for _, info in _tools_registry.items():
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
    value: Optional[Any] = None  # Store the specific value for this command instance

def schedule_startup_commands(args) -> deque[ScheduledCommand]:
    """Schedule CLI tool args into a queue of commands to execute in order they were serialized"""
    command_queue: deque[ScheduledCommand] = deque()
    cli_command = ["llt"]
    
    # Create mapping of flag variations to tool names
    flag_to_tool = {}
    for tool_name, info in _tools_registry.items():
        flag = info['flag']
        short = info['short']
        flag_to_tool[f"--{flag}"] = flag
        if short:
            flag_to_tool[f"--{short}"] = flag
    
    # Process arguments in pairs to handle value arguments
    i = 0
    while i < len(sys.argv[1:]):
        arg = sys.argv[i+1]  # +1 to skip script name
        cli_command.append(arg)
        
        # Strip leading dashes and check if it's a flag
        stripped_arg = arg.lstrip('--')
        
        # Handle flag with or without value
        if arg in flag_to_tool:  # Full flag match
            flag = flag_to_tool[arg]
            if hasattr(args, flag):
                arg_type = None
                # Find the argument type from the registry
                for _, info in _tools_registry.items():
                    if info['flag'] == flag:
                        arg_type = info['type']
                        break
                
                # For boolean flags
                if arg_type in ("bool", "boolean"):
                    value = getattr(args, flag)
                    if value:
                        command_queue.append(ScheduledCommand(flag, -1, value=True))
                # For value flags (string, int, float)
                else:
                    # Check if there's a value in the next argument
                    next_is_value = False
                    if i+1 < len(sys.argv[1:]):
                        next_arg = sys.argv[i+2]
                        if not next_arg.startswith('--'):
                            next_is_value = True
                            i += 1  # Skip the value in the next iteration
                            cli_command.append(next_arg)  # Add value to cli command
                            command_queue.append(ScheduledCommand(flag, -1, value=next_arg))
                    if not next_is_value:
                        # Check for --flag=value format
                        if '=' in arg:
                            value = arg.split('=', 1)[1]
                            cli_command[-1] = f"{arg}={value}"  # Update last entry with value
                            command_queue.append(ScheduledCommand(flag, -1, value=value))
                        else:
                            # Use the default value from argparse
                            value = getattr(args, flag)
                            if value is not None:
                                cli_command.append(str(value))  # Add default value
                            command_queue.append(ScheduledCommand(flag, -1, value=value))
        elif stripped_arg in [info['flag'] for _, info in _tools_registry.items()]:
            # Direct flag name match (for cases where arg might be after an =)
            if hasattr(args, stripped_arg):
                # Handle --flag=value format
                if '=' in arg:
                    value = arg.split('=', 1)[1]
                    cli_command[-1] = f"{arg}={value}"  # Update last entry with value
                    command_queue.append(ScheduledCommand(stripped_arg, -1, value=value))
                else:
                    value = getattr(args, stripped_arg)
                    if value is not None:
                        cli_command.append(str(value))  # Add value
                    command_queue.append(ScheduledCommand(stripped_arg, -1, value=value))
        
        i += 1
    
    if not args.non_interactive:
        llt_logger.log_info("llt session started", {"cli_command": " ".join(cli_command)})
    # Log command history with metadata to ~/.llt/cli_command.json
    
    command_log = {
        "timestamp": datetime.now().isoformat(),
        "command": " ".join(cli_command)
    }
    
    with open(os.path.expanduser("~/.llt/cli_command.json"), "a") as f:
        json.dump(command_log, f)
        f.write("\n")
    return command_queue

def generate_tool_spec(output_path: str):
    """Generates a tool specification JSON file based on registered tools."""
    tool_spec: Dict[str, Any] = {
        "name": "llt",
        "description": "Terminal tool for managing language model conversations with tool commands",
        "index": {
            "description": "Message index to operate on (-1 for last message)",
            "type": "integer",
            "default": -1
        },
        "functions": {}
    }

    for _, info in _tools_registry.items():
        flag = info.get('flag')
        description = info.get('description')
        arg_type = info.get('type')  # Get the type
        default_val = info.get('default') # Get the default

        # Skip tools without a flag (like the internal help/quit) or basic description
        if not flag or not description:
            continue
            
        # Add function description and other relevant fields
        function_spec = {"description": description}
        if arg_type:
            function_spec["type"] = arg_type
        if default_val is not None: # Explicitly check for None
            function_spec["default"] = default_val
            
        tool_spec["functions"][flag] = function_spec    

    try:
        with open(output_path, 'w') as f:
            json.dump(tool_spec, f, indent=2)
        llt_logger.log_info(f"Tool specification generated successfully at {output_path}")
    except IOError as e:
        llt_logger.log_error(f"Failed to write tool specification to {output_path}", {"error": str(e)})