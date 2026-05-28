"""Practical LLT plugin: redact sensitive text from a message log."""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List

from llt.tools import get_plugin_args, llt

Messages = List[Dict[str, Any]]


def _redact_value(value: Any, pattern: re.Pattern[str], replacement: str) -> tuple[Any, int]:
    if isinstance(value, str):
        redacted, count = pattern.subn(replacement, value)
        return redacted, count
    if isinstance(value, list):
        total = 0
        redacted_items = []
        for item in value:
            redacted_item, count = _redact_value(item, pattern, replacement)
            redacted_items.append(redacted_item)
            total += count
        return redacted_items, total
    if isinstance(value, dict):
        total = 0
        redacted_dict = {}
        for key, item in value.items():
            redacted_item, count = _redact_value(item, pattern, replacement)
            redacted_dict[key] = redacted_item
            total += count
        return redacted_dict, total
    return value, 0


@llt(
    flag="redact",
    type="bool",
    default=False,
    description="Redact regex matches from message content",
    params={
        "pattern": {
            "type": "str",
            "default": r"sk-[A-Za-z0-9_-]+",
            "description": "regular expression to redact",
        },
        "replacement": {
            "type": "str",
            "default": "[REDACTED]",
            "description": "replacement text",
        },
    },
)
def redact(messages: Messages, context: Dict[str, Any], index: int) -> Messages:
    args = get_plugin_args(context, "redact")
    pattern = re.compile(str(args.get("pattern") or r"sk-[A-Za-z0-9_-]+"))
    replacement = str(args.get("replacement") or "[REDACTED]")

    redacted_messages = copy.deepcopy(messages)
    total = 0
    for message in redacted_messages:
        redacted_content, count = _redact_value(message.get("content", ""), pattern, replacement)
        message["content"] = redacted_content
        total += count

    print(f"redact: replaced {total} occurrence(s)")
    return redacted_messages
