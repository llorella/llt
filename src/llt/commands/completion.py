"""Optional completion command.

The core LLT model is message-log transformation. This command is deliberately
small: it appends one assistant message from a configured provider and does not
request or execute tools.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from llt.tools import get_plugin_args, llt

Message = Dict[str, Any]
Messages = List[Message]


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _openai_completion(messages: Messages, args: Dict[str, Any]) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the provider extra to use OpenAI completions: llt[providers]") from exc

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=args["model"],
        messages=[
            {"role": message.get("role", "user"), "content": _text_from_content(message.get("content", ""))}
            for message in messages
        ],
        temperature=float(args["temperature"]),
        max_tokens=int(args["max_tokens"]),
    )
    choice = response.choices[0]
    return choice.message.content or ""


def _anthropic_completion(messages: Messages, args: Dict[str, Any]) -> str:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("Install the provider extra to use Anthropic completions: llt[providers]") from exc

    system_parts: list[str] = []
    user_messages: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role", "user")
        text = _text_from_content(message.get("content", ""))
        if role == "system":
            system_parts.append(text)
        elif role in {"user", "assistant"}:
            user_messages.append({"role": role, "content": text})

    client: Any = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    request: dict[str, Any] = {
        "model": args["model"],
        "messages": user_messages,
        "temperature": float(args["temperature"]),
        "max_tokens": int(args["max_tokens"]),
    }
    system_text = "\n\n".join(system_parts)
    if system_text:
        request["system"] = system_text
    response: Any = client.messages.create(**request)
    return "\n".join(
        str(getattr(block, "text", ""))
        for block in response.content
        if getattr(block, "type", None) == "text"
    )


@llt(
    flag="complete",
    type="bool",
    default=False,
    description="Append one assistant completion without tool execution",
    params={
        "provider": {"type": "str", "default": "openai", "description": "openai or anthropic"},
        "model": {"type": "str", "default": "gpt-4o-mini", "description": "provider model name"},
        "temperature": {"type": "float", "default": 0.7, "description": "sampling temperature"},
        "max_tokens": {"type": "int", "default": 2048, "description": "maximum output tokens"},
    },
)
def complete(messages: Messages, context: Dict[str, Any], index: int = -1) -> Messages:
    args = get_plugin_args(context, "complete")
    provider = str(args.get("provider", "openai")).lower()
    args = {
        "provider": provider,
        "model": args.get("model", "gpt-4o-mini"),
        "temperature": args.get("temperature", 0.7),
        "max_tokens": args.get("max_tokens", 2048),
    }

    if provider == "openai":
        content = _openai_completion(messages, args)
    elif provider == "anthropic":
        content = _anthropic_completion(messages, args)
    else:
        raise ValueError(f"unsupported completion provider: {provider}")

    return messages + [{"role": "assistant", "content": content}]
