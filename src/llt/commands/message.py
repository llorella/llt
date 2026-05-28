"""Built-in message-log commands."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from llt.tools import get_plugin_args, llt
from llt.utils import input_handler
from llt.utils.colors import Colors
from llt.utils.input_handler import get_valid_index

Message = Dict[str, Any]
Messages = List[Message]


def _is_interactive(context: Dict[str, Any]) -> bool:
    return not context.get("non_interactive", False)


def _resolve_ll_path(context: Dict[str, Any], value: str) -> str:
    path = os.path.expanduser(value)
    if not os.path.isabs(path):
        path = os.path.join(str(context.get("ll_dir", os.getcwd())), path)
    return os.path.abspath(path)


def _validate_messages(value: Any) -> Messages:
    if not isinstance(value, list):
        raise ValueError("message log must be a JSON array")
    for index, message in enumerate(value):
        if not isinstance(message, dict):
            raise ValueError(f"message {index} is not an object")
        if not isinstance(message.get("role"), str):
            raise ValueError(f"message {index} is missing string field 'role'")
        if "content" not in message:
            raise ValueError(f"message {index} is missing field 'content'")
    return value


def _normalize_index(messages: Messages, index: int, *, allow_end: bool = False) -> int:
    if not messages:
        return 0
    if index < 0:
        index = len(messages) + index
    upper = len(messages) if allow_end else len(messages) - 1
    return max(0, min(index, upper))


@llt(flag="load", short="l", type="str", default="default.ll", description="Load a JSON message log")
def load(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    path_value = context.get("load") or "default.ll"
    if _is_interactive(context):
        selected = input_handler.get_path_input(
            "Enter path to ll file",
            default=str(path_value),
            root_dir=str(context.get("ll_dir", os.getcwd())),
        )
        if not selected:
            return messages
        path_value = selected

    ll_path = _resolve_ll_path(context, str(path_value))
    with open(ll_path, "r", encoding="utf-8") as handle:
        loaded = _validate_messages(json.load(handle))
    context["load"] = ll_path
    if _is_interactive(context):
        Colors.print_colored(f"Loaded {len(loaded)} messages from '{ll_path}'.", Colors.GREEN)
    return loaded


@llt(flag="save", short="s", type="str", default="temp.ll", description="Save the current message log")
def save(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    path_value = context.get("save") or "temp.ll"
    if path_value == ".":
        path_value = context.get("load") or "temp.ll"

    if _is_interactive(context):
        selected = input_handler.get_path_input(
            "Enter path to save ll file",
            default=str(path_value),
            root_dir=str(context.get("ll_dir", os.getcwd())),
        )
        if not selected:
            return messages
        path_value = selected

    ll_path = _resolve_ll_path(context, str(path_value))
    os.makedirs(os.path.dirname(ll_path), exist_ok=True)
    with open(ll_path, "w", encoding="utf-8") as handle:
        json.dump(messages, handle, indent=2)
        handle.write("\n")
    context["save"] = ll_path
    if _is_interactive(context):
        Colors.print_colored(f"Saved {len(messages)} messages to '{ll_path}'.", Colors.GREEN)
    return messages


@llt(flag="prompt", short="p", type="str", default=None, description="Append a message")
def prompt(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    content = context.get("prompt")
    if content is None and _is_interactive(context):
        content = input("Prompt: ")
    if content is None:
        return messages
    return messages + [{"role": context.get("role", "user"), "content": str(content)}]


@llt(flag="remove", type="bool", default=False, description="Remove one message", needs_index=True)
def remove(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    if not messages:
        return messages
    if _is_interactive(context):
        index = get_valid_index(messages, "remove", index)
    index = _normalize_index(messages, index)
    return messages[:index] + messages[index + 1 :]


@llt(flag="attach", type="str", default="bridge.ll", description="Insert messages from another log", needs_index=True)
def attach(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    path_value = context.get("attach") or "bridge.ll"
    if _is_interactive(context):
        selected = input_handler.get_path_input(
            "Enter path to attach ll file",
            default=str(path_value),
            root_dir=str(context.get("ll_dir", os.getcwd())),
        )
        if not selected:
            return messages
        path_value = selected

    attach_path = _resolve_ll_path(context, str(path_value))
    with open(attach_path, "r", encoding="utf-8") as handle:
        incoming = _validate_messages(json.load(handle))
    insert_at = _normalize_index(messages, index, allow_end=True)
    return messages[:insert_at] + incoming + messages[insert_at:]


@llt(flag="detach", type="bool", default=False, description="Keep only one selected message", needs_index=True)
def detach(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    if not messages:
        return messages
    if _is_interactive(context):
        index = get_valid_index(messages, "detach", index)
    return [messages[_normalize_index(messages, index)]]


@llt(flag="fold", type="bool", default=False, description="Merge adjacent messages with the same role")
def fold(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    if not messages:
        return messages
    folded: Messages = []
    for message in messages:
        if folded and folded[-1].get("role") == message.get("role"):
            folded[-1] = {
                **folded[-1],
                "content": f"{folded[-1].get('content', '')}\n{message.get('content', '')}",
            }
        else:
            folded.append(dict(message))
    return folded


@llt(
    flag="insert",
    type="str",
    default="",
    description="Insert a new message",
    needs_index=True,
    params={"role": {"type": "str", "default": "user", "description": "role for the inserted message"}},
)
def insert(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    args = get_plugin_args(context, "insert")
    content = args.get("input", "")
    role = args.get("role", "user")
    insert_at = _normalize_index(messages, index, allow_end=True)
    return messages[:insert_at] + [{"role": role, "content": content}] + messages[insert_at:]


@llt(
    flag="modify-role",
    type="str",
    default="user",
    description="Change the role for one message",
    needs_index=True,
)
def modify_role(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    if not messages:
        return messages
    new_role = str(context.get("modify-role") or "user")
    if _is_interactive(context):
        index = get_valid_index(messages, "modify role of", index)
        selected = input_handler.get_input(
            "Select new role for the message",
            ["user", "assistant", "system", "tool"],
        )
        if selected:
            new_role = selected
    index = _normalize_index(messages, index)
    updated = [dict(message) for message in messages]
    updated[index]["role"] = new_role
    return updated


@llt(
    flag="view",
    short="v",
    type="bool",
    default=False,
    description="Print messages",
    needs_index=True,
    params={"all": {"type": "bool", "default": False, "description": "print every message"}},
)
def view(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    if not messages:
        print("No messages.")
        return messages

    args = get_plugin_args(context, "view")
    show_all = bool(args.get("all", False))

    def render(message: Message, display_index: int) -> None:
        role = str(message.get("role", "unknown"))
        print(f"[{display_index}] {role}")
        content = message.get("content", "")
        if isinstance(content, list):
            print(json.dumps(content, indent=2))
        else:
            print(content)

    if show_all:
        for offset, message in enumerate(messages):
            render(message, offset)
            if offset != len(messages) - 1:
                print("-" * 40)
    else:
        render(messages[_normalize_index(messages, index)], _normalize_index(messages, index))
    return messages


@llt(
    flag="cut",
    type="str",
    default=None,
    description="Keep a 1-based inclusive message range, for example '2,5'",
)
def cut(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    if not messages:
        return messages
    raw_range = context.get("cut")
    if raw_range is None and _is_interactive(context):
        raw_range = input("Enter start and optional end index separated by comma: ")
    if raw_range is None:
        return messages

    parts = [part.strip() for part in str(raw_range).split(",") if part.strip()]
    if not parts:
        return messages
    start = max(0, int(parts[0]) - 1)
    end = int(parts[1]) if len(parts) > 1 else start + 1
    if start >= end or start >= len(messages):
        raise ValueError("invalid cut range")
    return messages[start : min(end, len(messages))]


@llt(flag="format", type="str", default=None, description="Format one message with previous content", needs_index=True)
def format_message(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    if len(messages) < 2:
        return messages
    var_name = context.get("format")
    if not var_name:
        return messages
    index = _normalize_index(messages, index)
    if index == 0:
        raise ValueError("format requires a previous message")

    current = dict(messages[index])
    previous = messages[index - 1]
    current["content"] = str(current.get("content", "")).format(
        **{str(var_name): previous.get("content", "")}
    )
    updated = [dict(message) for message in messages]
    updated[index] = current
    return updated
