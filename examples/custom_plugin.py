"""Example LLT plugin using explicit command metadata."""

from __future__ import annotations

from typing import Any, Dict, List

from llt.tools import ScheduledCommand, get_plugin_args, llt

Messages = List[Dict[str, Any]]


@llt(
    flag="hello-world",
    type="bool",
    description="Print a greeting",
    params={
        "name": {"type": "str", "default": "World", "description": "name to greet"},
        "uppercase": {"type": "bool", "default": False, "description": "uppercase the greeting"},
    },
)
def hello_world(messages: Messages, context: Dict[str, Any], index: int) -> Messages:
    args = get_plugin_args(context, "hello-world")
    greeting = f"Hello, {args.get('name', 'World')}!"
    if args.get("uppercase", False):
        greeting = greeting.upper()
    print(greeting)
    return messages


@llt(
    flag="add-greeting",
    type="str",
    default="Hello",
    description="Append a greeting and optionally schedule a follow-up",
    params={"follow_up": {"type": "bool", "default": True}},
    needs_index=True,
)
def add_greeting(
    messages: Messages,
    context: Dict[str, Any],
    index: int,
) -> tuple[Messages, list[ScheduledCommand]]:
    args = get_plugin_args(context, "add-greeting")
    greeting = args.get("input", "Hello")
    new_messages = messages + [
        {
            "role": "assistant",
            "content": f"{greeting}! Added by an explicit plugin.",
        }
    ]
    queued = []
    if args.get("follow_up", True):
        queued.append(
            ScheduledCommand(
                name="hello-world",
                value={"enabled": True, "name": "Plugin User", "uppercase": True},
            )
        )
    return new_messages, queued


@llt(
    flag="count",
    short="c",
    type="bool",
    description="Print message counts by role",
    params={"detailed": {"type": "bool", "default": False}},
)
def count_messages(messages: Messages, context: Dict[str, Any], index: int) -> Messages:
    counts: dict[str, int] = {}
    for message in messages:
        role = str(message.get("role", "unknown"))
        counts[role] = counts.get(role, 0) + 1

    print(f"Total messages: {len(messages)}")
    for role, count in sorted(counts.items()):
        print(f"{role}: {count}")

    if get_plugin_args(context, "count").get("detailed") and messages:
        first = messages[0]
        last = messages[-1]
        print(f"first={first.get('role')} last={last.get('role')}")
    return messages
