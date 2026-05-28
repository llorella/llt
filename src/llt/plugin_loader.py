"""Explicit external plugin loading."""

from __future__ import annotations

import glob
import hashlib
import importlib.util
import os
import sys
from typing import List, Optional, Set

import logging

logger = logging.getLogger("llt.plugin_loader")


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def _default_plugin_paths() -> list[str]:
    paths: list[str] = []
    env_paths = os.getenv("LLT_PLUGIN_PATHS")
    if env_paths:
        paths.extend(part for part in env_paths.split(os.pathsep) if part)
    llt_path = os.path.expanduser(os.getenv("LLT_PATH", "~/.llt"))
    paths.append(os.path.join(llt_path, "plugins"))
    return paths


def discover_plugins(paths: List[str]) -> List[str]:
    """Return concrete Python plugin files from explicit files/directories."""

    plugin_files: list[str] = []
    for raw_path in paths:
        path = normalize_path(raw_path)
        if os.path.isfile(path) and path.endswith(".py"):
            plugin_files.append(path)
        elif os.path.isdir(path):
            for candidate in glob.glob(os.path.join(path, "*.py")):
                if not os.path.basename(candidate).startswith("_"):
                    plugin_files.append(os.path.abspath(candidate))
        else:
            logger.warning("Plugin path not found: %s", raw_path)
    return sorted(dict.fromkeys(plugin_files))


def _module_name(file_path: str) -> str:
    digest = hashlib.sha256(file_path.encode("utf-8")).hexdigest()[:12]
    stem = os.path.splitext(os.path.basename(file_path))[0].replace("-", "_")
    return f"llt_external_{stem}_{digest}"


def load_plugin_file(file_path: str, loaded_modules: Set[str]) -> bool:
    """Execute one plugin file in its own stable module namespace."""

    module_name = _module_name(file_path)
    if module_name in loaded_modules:
        return False

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        logger.error("Could not load plugin spec: %s", file_path)
        return False

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("Error loading plugin: %s", file_path)
        sys.modules.pop(module_name, None)
        return False

    loaded_modules.add(module_name)
    logger.info("Loaded plugin: %s", file_path)
    return True


def load_plugins(plugin_paths: Optional[List[str]] = None) -> int:
    """Load explicit plugin paths and return the number of files loaded."""

    paths = plugin_paths if plugin_paths is not None else _default_plugin_paths()
    plugin_files = discover_plugins(paths)
    loaded_modules: Set[str] = set()
    return sum(1 for plugin_file in plugin_files if load_plugin_file(plugin_file, loaded_modules))
