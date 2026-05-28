"""Public plugin protocol for LLT.

Plugins are ordinary Python callables registered with ``@llt()``. They receive
the current message log, an execution context, and a message index, then return a
new message log or a ``(messages, scheduled_commands)`` tuple.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Protocol, Tuple, Union

Message = Dict[str, Any]
Messages = List[Message]
PluginContext = Dict[str, Any]


class ScheduledCommandLike(Protocol):
    """Minimal shape accepted for queued commands."""

    name: str
    index: int
    value: Any
    args: Dict[str, Any] | None


PluginResult = Union[
    Messages,
    Tuple[Messages, List[ScheduledCommandLike]],
]


class PluginFunction(Protocol):
    """Callable shape for LLT plugins."""

    def __call__(
        self,
        messages: Messages,
        context: PluginContext,
        index: int,
    ) -> PluginResult:
        ...


PluginFactory = Callable[..., PluginFunction]
