"""Command registry and plugin decorator for LLT."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

F = TypeVar("F", bound=Callable[..., Any])
Messages = List[Dict[str, Any]]
CommandsToQueue = List["ScheduledCommand"]
ToolResult = Union[Messages, tuple[Messages, CommandsToQueue]]

TYPE_MAP = {
    "int": ("integer", int),
    "float": ("number", float),
    "str": ("string", str),
    "string": ("string", str),
    "bool": ("boolean", bool),
    "boolean": ("boolean", bool),
}


@dataclass(frozen=True)
class ToolParam:
    """Structured metadata for a command parameter."""

    name: str
    type: str = "str"
    default: Any = None
    description: str = ""
    required: bool = False


@dataclass(frozen=True)
class ToolSpec:
    """Structured metadata for a command."""

    flag: str
    description: str
    type: str = "bool"
    default: Any = False
    short: Optional[str] = None
    params: tuple[ToolParam, ...] = field(default_factory=tuple)
    needs_index: bool = False


@dataclass
class ToolEntry:
    """Registered command implementation plus metadata."""

    function: Callable[..., Any]
    spec: ToolSpec


@dataclass(frozen=True)
class ScheduledCommand:
    """Command scheduled by the CLI, SDK, or another command."""

    name: str
    index: int = -1
    value: Optional[Any] = None
    args: Optional[Dict[str, Any]] = None


_tools_registry: Dict[str, ToolEntry] = {}
_builtins_loaded = False

__all__ = [
    "ToolParam",
    "ToolSpec",
    "ScheduledCommand",
    "ToolResult",
    "llt",
    "get_plugin_args",
    "load_tools",
    "load_builtin_tools",
    "init_cmd_map",
    "add_tool_arguments",
    "pack_namespaced_args",
    "schedule_startup_commands",
    "registry_to_json_schema",
    "write_tool_registry_to_disk",
]


def _dest(flag: str) -> str:
    return flag.replace("-", "_")


def _cli_flag(flag: str) -> str:
    return "--" + flag.replace("_", "-")


def _coerce_param(name: str, raw: ToolParam | Dict[str, Any]) -> ToolParam:
    if isinstance(raw, ToolParam):
        return raw
    return ToolParam(name=name, **raw)


def _coerce_params(params: Optional[Iterable[ToolParam] | Dict[str, Any]]) -> tuple[ToolParam, ...]:
    if params is None:
        return ()
    if isinstance(params, dict):
        return tuple(_coerce_param(name, raw) for name, raw in params.items())
    return tuple(params)


def llt(
    *,
    flag: Optional[str] = None,
    description: Optional[str] = None,
    type: str = "bool",
    default: Any = False,
    short: Optional[str] = None,
    params: Optional[Iterable[ToolParam] | Dict[str, Any]] = None,
    needs_index: bool = False,
) -> Callable[[F], F]:
    """Register a Python callable as an LLT command.

    Metadata is explicit and machine-readable. LLT does not parse docstrings to
    infer CLI or SDK behavior.
    """

    def decorator(fn: F) -> F:
        command_flag = flag or fn.__name__.replace("_", "-")
        spec = ToolSpec(
            flag=command_flag,
            description=description or (fn.__doc__ or fn.__name__).strip(),
            type=type,
            default=default,
            short=short,
            params=_coerce_params(params),
            needs_index=needs_index,
        )
        if command_flag in _tools_registry:
            existing = _tools_registry[command_flag].function
            raise ValueError(
                f"Command flag '{command_flag}' already registered by "
                f"{existing.__module__}.{existing.__name__}"
            )
        _tools_registry[command_flag] = ToolEntry(function=fn, spec=spec)
        return fn

    return decorator


class _ToolAction(argparse.Action):
    """Argparse action that records command occurrence order."""

    def __init__(self, *args: Any, llt_flag: str, **kwargs: Any) -> None:
        self.llt_flag = llt_flag
        super().__init__(*args, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Optional[str] = None,
    ) -> None:
        value = True if self.nargs == 0 else values
        setattr(namespace, self.dest, value)
        order = list(getattr(namespace, "_llt_command_order", []))
        order.append((self.llt_flag, value))
        setattr(namespace, "_llt_command_order", order)


def _argparse_type(type_name: str) -> Callable[[str], Any]:
    return TYPE_MAP.get(type_name, TYPE_MAP["str"])[1]


def _json_type(type_name: str) -> str:
    return TYPE_MAP.get(type_name, TYPE_MAP["str"])[0]


def _add_argument(
    parser: argparse.ArgumentParser,
    spec: ToolSpec,
    option_strings: list[str],
) -> None:
    dest = _dest(spec.flag)
    kwargs: Dict[str, Any] = {
        "dest": dest,
        "help": spec.description,
        "llt_flag": spec.flag,
        "action": _ToolAction,
        "default": spec.default,
    }
    if spec.type in {"bool", "boolean"}:
        kwargs["nargs"] = 0
        kwargs["default"] = False
    else:
        kwargs["type"] = _argparse_type(spec.type)
    parser.add_argument(*option_strings, **kwargs)


def add_tool_arguments(parser: argparse.ArgumentParser) -> None:
    """Add registered command flags to an argparse parser."""

    if getattr(parser, "_llt_tool_args_added", False):
        return

    used_options: set[str] = set()
    used_shorts: set[str] = set()
    for entry in _tools_registry.values():
        spec = entry.spec
        option_strings = [_cli_flag(spec.flag)]
        underscore_option = f"--{spec.flag}"
        if underscore_option != option_strings[0]:
            option_strings.append(underscore_option)
        if spec.short:
            if len(spec.short) != 1:
                raise ValueError(f"Short flag for '{spec.flag}' must be one character")
            if spec.short in used_shorts:
                raise ValueError(f"Duplicate short flag '-{spec.short}'")
            used_shorts.add(spec.short)
            option_strings.append(f"-{spec.short}")

        for option in option_strings:
            if option in used_options:
                raise ValueError(f"Duplicate command option '{option}'")
            used_options.add(option)

        _add_argument(parser, spec, option_strings)

        params = {param.name: param for param in spec.params}
        if spec.needs_index and "index" not in params:
            params["index"] = ToolParam(
                name="index",
                type="int",
                default=-1,
                description="0-based message index; negative values count from the end",
            )

        for param in params.values():
            param_dest = f"{_dest(spec.flag)}_{param.name.replace('-', '_')}"
            kwargs: Dict[str, Any] = {
                "dest": param_dest,
                "default": param.default,
                "required": param.required,
                "help": param.description or f"{spec.flag} parameter: {param.name}",
            }
            if param.type in {"bool", "boolean"}:
                kwargs["action"] = "store_true"
            else:
                kwargs["type"] = _argparse_type(param.type)
            parser.add_argument(f"{_cli_flag(spec.flag)}-{param.name.replace('_', '-')}", **kwargs)

    setattr(parser, "_llt_tool_args_added", True)


def get_plugin_args(context: Dict[str, Any], flag: str) -> Dict[str, Any]:
    """Return normalized argument data for a command."""

    value = context.get(flag, {})
    if isinstance(value, dict):
        return value
    if value is None or value is False:
        return {}
    return {"enabled": value}


def load_builtin_tools() -> int:
    """Import packaged built-in commands so their decorators register them."""

    global _builtins_loaded
    before = len(_tools_registry)
    if not _builtins_loaded:
        from .. import commands as _commands  # noqa: F401

        _builtins_loaded = True
    return len(_tools_registry) - before


def load_tools(plugin_paths: Optional[List[str]] = None) -> int:
    """Load built-in commands and explicit external plugins."""

    load_builtin_tools()
    from ..plugin_loader import load_plugins

    return load_plugins(plugin_paths)


def _help(messages: Messages, context: Dict[str, Any], index: int) -> Messages:
    print(", ".join(sorted(_tools_registry.keys())))
    return messages


def _quit(messages: Messages, context: Dict[str, Any], index: int) -> Messages:
    raise SystemExit(0)


def init_cmd_map() -> Dict[str, Callable[..., Any]]:
    """Return the command dispatch table."""

    load_builtin_tools()
    cmd_map: Dict[str, Callable[..., Any]] = {}
    short_map: Dict[str, str] = {}
    for entry in _tools_registry.values():
        spec = entry.spec
        cmd_map[spec.flag] = entry.function
        if spec.short:
            if spec.short in short_map:
                raise ValueError(
                    f"Short command '{spec.short}' maps to both "
                    f"{short_map[spec.short]} and {spec.flag}"
                )
            short_map[spec.short] = spec.flag
            cmd_map[spec.short] = entry.function
    cmd_map["help"] = cmd_map["h"] = _help
    cmd_map["quit"] = cmd_map["q"] = _quit
    return cmd_map


def _tool_dests() -> set[str]:
    dests: set[str] = {"_llt_command_order"}
    for entry in _tools_registry.values():
        spec = entry.spec
        dests.add(_dest(spec.flag))
        for param in spec.params:
            dests.add(f"{_dest(spec.flag)}_{param.name.replace('-', '_')}")
        if spec.needs_index:
            dests.add(f"{_dest(spec.flag)}_index")
    return dests


def pack_namespaced_args(args: argparse.Namespace) -> Dict[str, Any]:
    """Return only non-command CLI settings as runtime context."""

    command_dests = _tool_dests()
    return {
        key: value
        for key, value in vars(args).items()
        if key not in command_dests and key != "help"
    }


def _scheduled_value(
    spec: ToolSpec,
    namespace: argparse.Namespace,
    occurrence_value: Any,
) -> tuple[Any, int]:
    params = {param.name: param for param in spec.params}
    if spec.needs_index and "index" not in params:
        params["index"] = ToolParam(name="index", type="int", default=-1)

    if not params and spec.type in {"bool", "boolean"}:
        return True, -1
    if not params:
        return occurrence_value, -1

    value: Dict[str, Any] = {"enabled": True}
    if spec.type not in {"bool", "boolean"}:
        value["input"] = occurrence_value

    index = -1
    for param in params.values():
        attr = f"{_dest(spec.flag)}_{param.name.replace('-', '_')}"
        param_value = getattr(namespace, attr, param.default)
        if param.name == "index":
            index = int(param_value if param_value is not None else -1)
            continue
        if param_value is not None or param.required:
            value[param.name] = param_value
    return value, index


def schedule_startup_commands(args: argparse.Namespace) -> tuple[ScheduledCommand, ...]:
    """Build startup command queue from parsed CLI command occurrences."""

    scheduled: list[ScheduledCommand] = []
    for flag, occurrence_value in getattr(args, "_llt_command_order", []):
        entry = _tools_registry[flag]
        value, index = _scheduled_value(entry.spec, args, occurrence_value)
        scheduled.append(
            ScheduledCommand(name=flag, index=index, value=value, args=value if isinstance(value, dict) else None)
        )
    return tuple(scheduled)


def registry_to_json_schema(write_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return registered command metadata as JSON-schema-like objects."""

    schemas: list[dict[str, Any]] = []
    for entry in _tools_registry.values():
        spec = entry.spec
        schema: Dict[str, Any] = {
            "name": spec.flag,
            "description": spec.description,
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
        if spec.type not in {"bool", "boolean"}:
            schema["input_schema"]["properties"]["input"] = {
                "type": _json_type(spec.type),
                "description": f"Input value for {spec.flag}",
            }
            if spec.default is None:
                schema["input_schema"]["required"].append("input")

        params = list(spec.params)
        if spec.needs_index and not any(param.name == "index" for param in params):
            params.append(ToolParam(name="index", type="int", default=-1))

        for param in params:
            schema["input_schema"]["properties"][param.name] = {
                "type": _json_type(param.type),
                "description": param.description or f"{spec.flag} parameter: {param.name}",
            }
            if param.default is not None:
                schema["input_schema"]["properties"][param.name]["default"] = param.default
            if param.required:
                schema["input_schema"]["required"].append(param.name)
        schemas.append(schema)

    if write_path:
        os.makedirs(os.path.dirname(os.path.expanduser(write_path)), exist_ok=True)
        with open(os.path.expanduser(write_path), "w", encoding="utf-8") as handle:
            json.dump(schemas, handle, indent=2)
    return schemas


def write_tool_registry_to_disk(path: Optional[str] = None) -> str:
    """Write command registry metadata to disk and return the path."""

    if path is None:
        llt_path = os.path.expanduser(os.getenv("LLT_PATH", "~/.llt"))
        path = os.path.join(llt_path, "tool_registry.json")
    os.makedirs(os.path.dirname(os.path.expanduser(path)), exist_ok=True)
    payload = {
        flag: {
            **asdict(entry.spec),
            "function": f"{entry.function.__module__}.{entry.function.__name__}",
        }
        for flag, entry in _tools_registry.items()
    }
    with open(os.path.expanduser(path), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path
