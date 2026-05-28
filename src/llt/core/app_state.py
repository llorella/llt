"""Immutable runtime state and audit-delta helpers."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple

Message = Dict[str, Any]
Messages = List[Message]
Context = Dict[str, Any]
MessagePlaceholder = Dict[str, Any]


@dataclass(frozen=True)
class AppState:
    """Runtime state passed between LLT commands."""

    messages: Messages
    context: Context
    command_queue: tuple[Any, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "messages", copy.deepcopy(list(self.messages)))
        object.__setattr__(self, "context", copy.deepcopy(dict(self.context)))
        object.__setattr__(self, "command_queue", tuple(self.command_queue))

    def with_messages(self, new_messages: Messages) -> "AppState":
        context = dict(self.context)
        context.pop("last_log_id", None)
        return AppState(new_messages, context, self.command_queue)

    def with_context(self, new_context: Context) -> "AppState":
        return AppState(self.messages, new_context, self.command_queue)

    def with_queue(self, new_queue: Iterable[Any]) -> "AppState":
        return AppState(self.messages, self.context, tuple(new_queue))

    def to_tool_args(self) -> Tuple[Messages, Context]:
        """Return deep mutable copies for command/plugin execution."""

        return copy.deepcopy(self.messages), copy.deepcopy(self.context)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def calculate_context_delta(old_context: Context, new_context: Context) -> Dict[str, Any]:
    """Calculate changed context keys, excluding audit bookkeeping."""

    ignored = {"session_id", "last_log_id"}
    delta: Dict[str, Any] = {}
    for key in sorted(set(old_context) | set(new_context)):
        if key in ignored:
            continue
        if key not in new_context:
            delta[key] = None
        elif key not in old_context or old_context[key] != new_context[key]:
            delta[key] = new_context[key]
    return delta


def _message_placeholder(message: Message, index: int) -> MessagePlaceholder:
    content = message.get("content", "")
    content_text = content if isinstance(content, str) else _stable_json(content)
    content_bytes = content_text.encode("utf-8")
    return {
        "type": "message_ref",
        "role": message.get("role", "unknown"),
        "content_length": len(content_bytes),
        "content_sha256": hashlib.sha256(content_bytes).hexdigest(),
        "index_in_new_state": index,
    }


def calculate_messages_delta(
    old_messages: Messages,
    new_messages: Messages,
) -> Tuple[List[MessagePlaceholder], List[int]]:
    """Return message additions and removals for the audit log."""

    if old_messages == new_messages:
        return [], []

    old_len = len(old_messages)
    new_len = len(new_messages)

    if new_len > old_len and new_messages[:old_len] == old_messages:
        return [
            _message_placeholder(message, old_len + offset)
            for offset, message in enumerate(new_messages[old_len:])
        ], []

    if new_len == old_len - 1:
        for old_index in range(old_len):
            if old_messages[:old_index] + old_messages[old_index + 1 :] == new_messages:
                return [], [old_index]

    if old_len == 0:
        return [
            _message_placeholder(message, index)
            for index, message in enumerate(new_messages)
        ], []

    return [
        _message_placeholder(message, index)
        for index, message in enumerate(new_messages)
    ], list(range(old_len))
