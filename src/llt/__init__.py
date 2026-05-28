"""LLT: an auditable CLI and SDK for message logs and custom plugins."""
from importlib.metadata import version, PackageNotFoundError

# Export core components
from .core.app_state import AppState
from .core.runtime import create_session, get_next_command, process_command, run_llt
from .tools import ScheduledCommand, ToolParam, ToolSpec, ToolResult, get_plugin_args, llt

try:
    __version__ = version("llt")
except PackageNotFoundError:
    __version__ = "0.1.0"

__all__ = [
    "AppState",
    "run_llt",
    "process_command",
    "get_next_command",
    "create_session",
    "llt",
    "ScheduledCommand",
    "ToolParam",
    "ToolSpec",
    "ToolResult",
    "get_plugin_args",
]
