# plugins/__init__.py

import os
import importlib.util
from typing import Callable, Dict
from logger import llt_logger

_plugins_registry: Dict[str, Callable] = {}

def plugin(fn: Callable) -> Callable:
    """
    Decorator to register a function as a plugin by name.
    """
    _plugins_registry[fn.__name__] = fn
    return fn

def plugins() -> Dict[str, Callable]:
    """
    Return the dictionary of all registered plugin functions.
    """
    return _plugins_registry

def load_plugins(plugin_dir: str) -> None:
    """
    Dynamically load Python scripts from 'plugin_dir'.
    Each script can import @plugin from here to register functions.
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
    for cmd_name, fn in _plugins_registry.items():
        if cmd_name not in cmd_map:
            cmd_map[cmd_name] = fn
        if n_abbv(cmd_name) not in cmd_map:
            cmd_map[n_abbv(cmd_name)] = fn
        elif len(cmd_name) > 2 and n_abbv(cmd_name, 2) not in cmd_map:
            cmd_map[n_abbv(cmd_name, 2)] = fn
        seps = ["-", "_"]
        for sep in seps:
            split_cmd = cmd_name.split(sep)
            if split_cmd:
                cmd_map[split_cmd[0]] = fn
                
    cmd_map["h"] = cmd_map["help"] = help
    cmd_map["q"] = cmd_map["quit"] = quit
    
    return cmd_map