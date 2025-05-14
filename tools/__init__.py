# tools/__init__.py

import os
import importlib.util
from typing import Callable, Dict, Any, Optional, List, Tuple, TypeVar, cast, Union, Set
# Ensure consistency with tools/completion.py for ToolUseBlock import
from anthropic.types import ToolUseBlock 
from logger import llt_logger
import argparse
import re
from collections import deque
from dataclasses import dataclass
import sys
import json
from datetime import datetime
from functools import wraps

_tools_registry: Dict[str, Dict[str, Any]] = {}

# Type mapping from tool spec to JSON schema
TYPE_MAP = {
    "int": "integer",
    "float": "number",
    "str": "string", 
    "string": "string",
    "bool": "boolean",
    "boolean": "boolean",
}

# Export symbols for tool authors
__all__ = ['llt', 'ScheduledCommand', 'ToolResult', 'get_plugin_args']

# Type aliases for tool return values
T = TypeVar('T')
Messages = List[Dict[str, Any]]
CommandsToQueue = List['ScheduledCommand']
ToolResult = Union[Messages, Tuple[Messages, CommandsToQueue]]

# Define a decorator type for Mypy
F = TypeVar('F', bound=Callable[..., Any])

def llt(*, needs_index: bool = False) -> Callable[[F], F]:
    """
    Enhanced decorator that registers a tool by parsing its docstring.
    
    Args:
        needs_index: Whether this tool needs the message index parameter
    
    Returns:
        A decorated function that registers itself in the tools registry
    """
    def decorator(fn: F) -> F:
        """
        Enhanced decorator that registers a tool by parsing its docstring.

        Each docstring should contain lines in the format:

            Description: ...
            Type: ...
            Default: ...
            flag: ...
            short: ...

        And optional sub-flags:
            param: <name> <type> <default>

        Example:
            @llt(needs_index=True)
            def example(messages, context, index=-1):
                \"\"\"
                Description: Example tool
                Type: bool
                Default: false
                flag: example
                short: e
                param: url string "https://default.com"
                param: timeout int 30
                \"\"\"
                ...

        We'll store these in _tools_registry for later argument parsing and command mapping.
        """
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
            
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
        
        # Parse sub-flags (parameters)
        param_pattern = re.compile(r"param:\s*(\w+)\s+(\w+)(?:\s+(.*))?")
        subflags = {}
        
        for line in doc.splitlines():
            param_match = param_pattern.search(line.strip())
            if param_match:
                param_name = param_match.group(1)
                param_type = param_match.group(2)
                # Handle quoted default values
                param_default = param_match.group(3)
                if param_default:
                    param_default = param_default.strip()
                    # Remove quotes from string defaults
                    if (param_default.startswith('"') and param_default.endswith('"')) or \
                       (param_default.startswith("'") and param_default.endswith("'")):
                        param_default = param_default[1:-1]
                    # Convert to proper Python type if possible
                    elif param_type in ('int', 'float'):
                        try:
                            param_default = int(param_default) if param_type == 'int' else float(param_default)
                        except ValueError:
                            llt_logger.log_warning(f"Invalid {param_type} default for {param_name}: {param_default}")
                    elif param_type in ('bool', 'boolean'):
                        param_default = param_default.lower() == 'true'
                
                subflags[param_name] = {
                    'type': param_type,
                    'default': param_default
                }

        tool_registry_entry = {
            'function': fn,
            'description': description,
            'type': arg_type,
            'default': default if default != "None" else None,
            'flag': flag,
            'short': short,
            'subflags': subflags,
            'needs_index': needs_index
        }
        
        _tools_registry[fn.__name__] = tool_registry_entry
        return fn
    
    # The `if callable(needs_index):` block was an attempt to handle `@llt` (no parentheses).
    # By making `needs_index` a keyword-only argument, we are encouraging explicit calls
    # like `@llt()` or `@llt(needs_index=True)`, which should be clearer for Mypy.
    # The decorator factory pattern is that `llt` (with its keyword arguments) 
    # returns the `decorator` function, which then takes the actual function `fn` to be decorated.
    return decorator


def add_tool_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Create argparse flags from the collected tool registry.
    Now handles both main flags and subflags.
    """
    used_flags: Set[str] = set()
    used_shorts: Set[str] = set()
    for tool_name, info in _tools_registry.items():
        flag_str = info['flag']
        if info['type'] is None:
            continue
        short_str = info['short']
        description = info['description']
        arg_type = info['type']
        default_val = info['default']

        used_flags.add(flag_str)

        cli_flags = [f"--{flag_str}"]
        if short_str:
            if short_str in used_shorts:
                llt_logger.log_error(f"Duplicate short flag '-{short_str}' in {tool_name}", {"tool": tool_name})
            else:
                cli_flags.append(f"-{short_str}")
            used_shorts.add(short_str)

        # Add main flag for the tool
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


def make_scheduled_from_tool_use(
    block: ToolUseBlock, # Use the imported ToolUseBlock directly
) -> "ScheduledCommand":
    """
    Convert a Claude `tool_use` block into an LLT ScheduledCommand.
    
    Example: 
        "block": "ToolUseBlock(id='toolu_01HyaVAFMSuLys6iYPKL7jMu', input={'input': 'main.py'}, name='file', type='tool_use')"
        
        returns:
            ScheduledCommand(name='file', index=-1, value='main.py', args={})
    
    Special cases:
        For execute tool: If 'content' is present, it's passed directly in both value and args
    """
    # Extract parameters from the tool use block
    inp = block.input or {}
    idx = inp.pop("index", -1) if isinstance(inp, dict) else -1
    value = inp.pop("input", None) if isinstance(inp, dict) else None
    
    # Debug information
    print(f"Block name: {block.name}, index: {idx}, value: {value}, args: {inp}")
    registry_info = _tools_registry.get(block.name)
    print(f"Registry info for {block.name}: {registry_info}")
    
    # Special handling for execute and similar commands that need direct content
    """ if block.name == "execute" and "content" in inp:
        print(f"Special handling for execute command with content: {inp['content']}")
        # Pass the entire input dictionary as both the value and args
        return ScheduledCommand(name=block.name, index=idx, value=inp, args=inp)
     """
    # Standard handling for most tools
    args_for_command: Dict[Any, Any] = {}
    if isinstance(inp, dict):
        args_for_command = cast(Dict[Any, Any], inp)
    elif inp is not None: 
        # If inp is not None and not a dict, it's an unexpected type.
        # Log a warning and default to empty dict for args.
        llt_logger.log_warning(f"Unexpected type for tool input: {type(inp)}. Expected dict or None.", {"input_value": inp})
        # Depending on strictness, one might raise an error here.
        # For now, proceed with empty args.

    if value is not None:
        return ScheduledCommand(name=block.name, index=idx, value=value, args=args_for_command)
    elif args_for_command:  # If there are other args (which must be a dict by now)
        return ScheduledCommand(name=block.name, index=idx, value=args_for_command, args=args_for_command)
    else:  # Fallback for tools with no parameters (value is not None, inp was None or not a dict)
        return ScheduledCommand(name=block.name, index=idx, value=True, args={})


def pack_namespaced_args(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Convert flat argparse namespace to nested dictionary with namespaces.
    
    Example:
        {
          "model": "claude-3-sonnet",
          "execute": {"language":"bash","timeout":30},
          "complete": True
        }
    """
    args_dict = vars(args)
    result = {}
    
    # Track which keys have been processed
    processed_keys = set()
    
    # Find all tool flags
    for tool_name, info in _tools_registry.items():
        flag = info['flag']
        if flag in args_dict:
            # Main flag exists
            value = args_dict[flag]
            
            # For boolean flags that are False or string flags that are None, skip
            if (info['type'] in ('bool', 'boolean') and not value) or value is None:
                processed_keys.add(flag)
                continue
                
            # Process subflags if they exist
            subflags = info.get('subflags', {})
            if subflags:
                # If this tool has subflags, create a nested dict
                tool_dict = {}
                
                # Add subflags to the tool dict if they exist in args
                for subflag, subflag_info in subflags.items():
                    arg_key = f"{flag}_{subflag}"
                    if arg_key in args_dict:
                        subflag_value = args_dict[arg_key]
                        # Only include non-default values
                        default_value = subflag_info.get('default')
                        if subflag_value != default_value:
                            tool_dict[subflag] = subflag_value
                        processed_keys.add(arg_key)
                        
                # Handle main flag value (only for non-boolean types)
                if info['type'] not in ('bool', 'boolean'):
                    # Use the value directly as an input parameter
                    tool_dict['input'] = value
                
                # Only add the tool to the result if it has actual values
                if tool_dict or info['type'] in ('bool', 'boolean'):
                    result[flag] = tool_dict if tool_dict else True
            else:
                # No subflags, just use the value directly
                result[flag] = value
                
            processed_keys.add(flag)
    
    # Add any unprocessed args as top-level entries
    for key, value in args_dict.items():
        if key not in processed_keys:
            result[key] = value
            
    return result

def get_plugin_args(context: Dict[str, Any], flag: str) -> Dict[str, Any]:
    """
    Helper function to get the arguments for a specific plugin.
    
    Args:
        context: The context dictionary
        flag: The flag (name) of the plugin
        
    Returns:
        Dict containing the plugin's arguments
    """
    result = context.get(flag, {})
    if not isinstance(result, dict):
        result = {'enabled': result}
    return result

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
    
    command_log = {
        "timestamp": datetime.now().isoformat(),
        "command": " ".join(cli_command)
    }
    
    with open(os.path.expanduser("~/.llt/cli_command.json"), "a") as f:
        json.dump(command_log, f)
        f.write("\n")
    return command_queue

def registry_to_json_schema() -> List[Dict[str, Any]]:
    """
    Convert the tool registry to a JSON schema suitable for Anthropic/OpenAI.
    
    Returns:
        List of tool specifications compatible with the API
    """
    tools = []
    
    for _, info in _tools_registry.items():
        flag = info.get('flag')
        description = info.get('description')
        needs_index = info.get('needs_index', False)
        
        # Skip tools without a flag or description
        if not flag or not description:
            continue
            
        tool_spec = {
            "name": flag,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
        
        # Add index parameter only if needed
        if needs_index:
            tool_spec["input_schema"]["properties"]["index"] = {
                "type": "integer",
                "description": "Message index to operate on (-1 for last message)",
                "default": -1
            }
        
        # Handle main flag type if it's not a boolean
        arg_type = info.get('type')
        if arg_type and arg_type not in ('bool', 'boolean'):
            json_type = TYPE_MAP.get(arg_type, "string")
            tool_spec["input_schema"]["properties"]["input"] = {
                "type": json_type,
                "description": f"Input value for {flag}"
            }
            
            default_val = info.get('default')
            if default_val is not None:
                if json_type == "integer":
                    tool_spec["input_schema"]["properties"]["input"]["default"] = int(default_val)
                elif json_type == "number":
                    tool_spec["input_schema"]["properties"]["input"]["default"] = float(default_val)
                else:
                    tool_spec["input_schema"]["properties"]["input"]["default"] = str(default_val)
                    
            # Add to required if no default provided
            if default_val is None:
                tool_spec["input_schema"]["required"].append("input")
                
        # Add subflags
        subflags = info.get('subflags', {})
        for subflag_name, subflag_info in subflags.items():
            subflag_type = subflag_info.get('type')
            if not subflag_type:
                continue
                
            json_type = TYPE_MAP.get(subflag_type, "string")
            
            tool_spec["input_schema"]["properties"][subflag_name] = {
                "type": json_type,
                "description": f"Parameter '{subflag_name}' for {flag}"
            }
            
            subflag_default = subflag_info.get('default')
            if subflag_default is not None:
                if json_type == "integer":
                    try:
                        tool_spec["input_schema"]["properties"][subflag_name]["default"] = int(subflag_default)
                    except (ValueError, TypeError):
                        tool_spec["input_schema"]["properties"][subflag_name]["default"] = 0
                elif json_type == "number":
                    try:
                        tool_spec["input_schema"]["properties"][subflag_name]["default"] = float(subflag_default)
                    except (ValueError, TypeError):
                        tool_spec["input_schema"]["properties"][subflag_name]["default"] = 0.0
                elif json_type == "boolean":
                    tool_spec["input_schema"]["properties"][subflag_name]["default"] = str(subflag_default).lower() == "true"
                else:
                    tool_spec["input_schema"]["properties"][subflag_name]["default"] = str(subflag_default)
            else:
                # Add to required list if no default provided
                tool_spec["input_schema"]["required"].append(subflag_name)
        
        tools.append(tool_spec)
    
    # optional: write to disk
    with open(os.path.expanduser("~/llt/tool_registry.json"), "w") as f:
        json.dump(tools, f, indent=2)
    return tools
