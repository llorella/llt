"""Core runtime for command execution and audit logging."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional

from ..tools import ScheduledCommand
from .app_state import AppState, calculate_context_delta, calculate_messages_delta

Messages = List[Dict[str, Any]]
Context = Dict[str, Any]
CommandMap = Dict[str, Callable[..., Any]]

_session_store: Dict[str, AppState] = {}


def _debug(context: Context, message: str) -> None:
    if context.get("debug"):
        print(message)


def get_session(session_id: str) -> Optional[AppState]:
    return _session_store.get(session_id)


def save_session(session_id: str, state: AppState) -> None:
    _session_store[session_id] = state


def _expand(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def create_session(
    context_overrides: Optional[Dict[str, Any]] = None,
    isolated: bool = True,
) -> AppState:
    """Create a session with deterministic directory context."""

    overrides = dict(context_overrides or {})
    session_id = str(overrides.get("session_id") or uuid.uuid4())
    base_path = _expand(os.getenv("LLT_PATH", "~/.llt"))

    if isolated:
        session_base = os.path.join(base_path, "sessions", session_id)
        context: Context = {
            "session_id": session_id,
            "last_log_id": None,
            "role": "user",
            "isolated": True,
            "non_interactive": False,
            "debug": False,
            "session_base": session_base,
            "ll_dir": os.path.join(session_base, "ll"),
            "exec_dir": os.path.join(session_base, "exec"),
            "cmd_dir": os.path.join(session_base, "cmd"),
        }
    else:
        context = {
            "session_id": session_id,
            "last_log_id": None,
            "role": "user",
            "isolated": False,
            "non_interactive": False,
            "debug": False,
            "ll_dir": os.path.join(base_path, "ll"),
            "exec_dir": os.path.join(base_path, "exec"),
            "cmd_dir": os.path.join(base_path, "cmd"),
        }

    context.update({key: value for key, value in overrides.items() if value is not None})
    context["session_id"] = session_id

    for key in ("ll_dir", "exec_dir", "cmd_dir"):
        if context.get(key):
            context[key] = _expand(str(context[key]))
            os.makedirs(context[key], exist_ok=True)

    state = AppState(messages=[], context=context, command_queue=())
    save_session(session_id, state)
    return state


def get_tool_source(cmd_map: CommandMap, cmd_name: str) -> Optional[str]:
    fn = cmd_map.get(cmd_name)
    if fn is None:
        return None
    return getattr(fn, "__module__", "unknown_source")


def _log_path(context: Context) -> Optional[str]:
    session_id = context.get("session_id")
    cmd_dir = context.get("cmd_dir")
    if not session_id or not cmd_dir:
        return None
    return os.path.join(str(cmd_dir), f"session_{session_id}.log.jsonl")


def log_command_execution(
    old_state: AppState,
    new_state: AppState,
    command: ScheduledCommand,
    cmd_map: CommandMap,
    logger: Any,
    *,
    status: str,
    error: Optional[str] = None,
) -> Optional[str]:
    """Append one command audit record and return its log id."""

    log_file_path = _log_path(old_state.context)
    parent_log_id = old_state.context.get("last_log_id")
    if not log_file_path:
        logger.log_warning("Cannot write command audit log without session_id and cmd_dir.")
        return parent_log_id if isinstance(parent_log_id, str) else None

    log_id = str(uuid.uuid4())
    messages_added, messages_removed = calculate_messages_delta(
        old_state.messages,
        new_state.messages,
    )
    output_summary: Dict[str, Any] = {
        "status": status,
        "message_count": len(new_state.messages),
    }
    entry: Dict[str, Any] = {
        "log_id": log_id,
        "parent_id": parent_log_id,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "command": {
            "name": command.name,
            "value": command.value,
            "args": command.args,
            "index": command.index,
            "tool_source": get_tool_source(cmd_map, command.name),
        },
        "state_delta": {
            "context_changed": calculate_context_delta(old_state.context, new_state.context),
            "messages_added": messages_added,
            "messages_removed_indices": messages_removed,
        },
        "resource_references": {},
        "output_summary": output_summary,
    }
    if error:
        output_summary["error"] = error

    try:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        with open(log_file_path, "a", encoding="utf-8") as handle:
            json.dump(entry, handle)
            handle.write("\n")
        return log_id
    except OSError as exc:
        logger.log_error(f"Failed to write command audit log: {exc}", {"log_file": log_file_path})
        return parent_log_id if isinstance(parent_log_id, str) else None


def _apply_command_value(context: Context, command: ScheduledCommand) -> Context:
    next_context = dict(context)
    if command.value is not None:
        next_context[command.name] = command.value
    return next_context


def _with_log_id(state: AppState, log_id: Optional[str]) -> AppState:
    context = dict(state.context)
    context["last_log_id"] = log_id
    return state.with_context(context)


def _save_current(state: AppState) -> AppState:
    session_id = state.context.get("session_id")
    if isinstance(session_id, str):
        save_session(session_id, state)
    return state


def process_command(
    cmd_map: CommandMap,
    cmd: ScheduledCommand,
    state: AppState,
    logger: Any,
) -> AppState:
    """Execute one command and return the next state."""

    _debug(state.context, f"process_command: {cmd.name!r} value={cmd.value!r} index={cmd.index}")

    if not cmd.name:
        return state

    if cmd.name not in cmd_map:
        content = cmd.name if cmd.value is None else f"{cmd.name} {cmd.value}"
        new_state = state.with_messages(
            state.messages + [{"role": state.context.get("role", "user"), "content": content}]
        )
        pseudo = ScheduledCommand(name="prompt", index=-1, value=content)
        log_id = log_command_execution(
            state,
            new_state,
            pseudo,
            cmd_map,
            logger,
            status="success",
        )
        return _save_current(_with_log_id(new_state, log_id))

    messages, context = state.to_tool_args()
    context = _apply_command_value(context, cmd)

    try:
        result = cmd_map[cmd.name](messages, context, cmd.index)
        if isinstance(result, tuple) and len(result) == 2:
            new_messages, queued = result
            command_queue = tuple(state.command_queue) + tuple(queued)
        else:
            new_messages = result
            command_queue = tuple(state.command_queue)

        if not isinstance(new_messages, list):
            raise TypeError(f"Command {cmd.name!r} returned {type(new_messages).__name__}, expected list")

        new_state = AppState(
            messages=new_messages,
            context=context,
            command_queue=command_queue,
        )
        log_id = log_command_execution(
            state,
            new_state,
            cmd,
            cmd_map,
            logger,
            status="success",
        )
        return _save_current(_with_log_id(new_state, log_id))
    except SystemExit:
        raise
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}"
        logger.log_error(error_text, {"traceback": traceback.format_exc()})
        if not state.context.get("non_interactive"):
            print(f"Command failed: {error_text}")
        log_id = log_command_execution(
            state,
            state,
            cmd,
            cmd_map,
            logger,
            status="failure",
            error=error_text,
        )
        return _save_current(_with_log_id(state, log_id))


def get_next_command(
    state: AppState,
    cmd_map: CommandMap,
    interactive_input_fn: Callable[[list[str]], tuple[str, Any, Optional[int]]],
) -> Optional[ScheduledCommand]:
    """Read the next interactive command, or return queued command preview."""

    if state.command_queue:
        return state.command_queue[0]
    if state.context.get("non_interactive"):
        return None
    cmd_name, value, index = interactive_input_fn(sorted(cmd_map.keys()))
    return ScheduledCommand(cmd_name, index if index is not None else -1, value=value)


def run_llt(
    initial_state: AppState,
    cmd_map: CommandMap,
    logger: Any,
    interactive_input_fn: Callable[[list[str]], tuple[str, Any, Optional[int]]],
    stop_on_empty_queue: bool = False,
) -> AppState:
    """Run the LLT command loop and return the final state."""

    state = initial_state
    while True:
        try:
            if state.command_queue:
                cmd = state.command_queue[0]
                state = state.with_queue(state.command_queue[1:])
            else:
                cmd = get_next_command(state, cmd_map, interactive_input_fn)

            if cmd is None:
                return _save_current(state)
            if not cmd.name:
                if state.context.get("non_interactive") or stop_on_empty_queue:
                    return _save_current(state)
                continue

            state = process_command(cmd_map, cmd, state, logger)
        except KeyboardInterrupt:
            if state.context.get("non_interactive"):
                raise
            logger.log_info("Received keyboard interrupt")
            try:
                time.sleep(0.5)
            except KeyboardInterrupt:
                raise SystemExit(1)
            return _save_current(state)
        except SystemExit:
            raise
        except Exception as exc:
            logger.log_error(str(exc), {"traceback": traceback.format_exc()})
            if not state.context.get("non_interactive"):
                print(f"Error: {exc}")
            if state.context.get("non_interactive") or stop_on_empty_queue:
                return _save_current(state)
