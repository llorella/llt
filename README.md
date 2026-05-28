# llt

`llt` is an auditable CLI and Python SDK for transforming language-model
message logs. A session is a list of `{role, content}` messages plus a command
audit log. Commands are ordinary Python functions registered with explicit
metadata.

This is not an agent framework. LLT does not autonomously choose tools. The CLI,
SDK caller, or a plugin schedules commands explicitly.

## Install

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## CLI

```bash
LLT_PATH=$HOME/.llt llt --prompt "hello" --view --non_interactive
llt --prompt "one" --prompt "two" --view --view-all --non_interactive
llt --prompt "draft an outline" --save outline.ll --non_interactive
llt --load outline.ll --view --non_interactive
```

By default, LLT writes under `$LLT_PATH` or `~/.llt`:

```text
ll/     saved message logs
cmd/    JSONL command audit logs
exec/   plugin workspace
```

## Audit Logs

Every command records one JSONL entry under `cmd/session_<id>.log.jsonl`.
Records include the command name, value, index, plugin source module, parent log
id, context delta, message additions by SHA-256 reference, removals, and success
or failure status. Message bodies stay in the message log; the command log stays
small enough to inspect.

## Plugins

Plugins use explicit metadata. LLT does not parse docstrings.

```python
from llt.tools import get_plugin_args, llt

@llt(
    flag="shout",
    type="str",
    default=None,
    description="Append an uppercase message",
    params={"role": {"type": "str", "default": "user"}},
)
def shout(messages, context, index):
    args = get_plugin_args(context, "shout")
    return messages + [{
        "role": args.get("role", "user"),
        "content": str(args["input"]).upper(),
    }]
```

Run a plugin explicitly:

```bash
llt --plugins ./my_plugin.py --shout "audit me" --view --non_interactive
```

Plugin paths can also come from `LLT_PLUGIN_PATHS`, separated by `:`.

See [docs/usage-demo.md](docs/usage-demo.md) for a full redaction workflow that
creates a raw log, sanitizes it with a plugin, saves the result, and inspects the
JSONL audit trail.

## Completion

`--complete` is a small optional command, not the core programming model. It
appends one assistant message and never requests or executes tools.

```bash
uv pip install -e ".[providers]"
llt --prompt "say hi" --complete --complete-provider openai --complete-model gpt-4o-mini
```

## SDK

```python
from llt import AppState, ScheduledCommand, process_command
from llt.logging import llt_logger
from llt.tools import init_cmd_map, load_tools

load_tools([])
state = AppState(
    messages=[],
    context={
        "session_id": "example",
        "cmd_dir": "/tmp/llt-cmd",
        "ll_dir": "/tmp/llt-ll",
        "exec_dir": "/tmp/llt-exec",
        "role": "user",
        "non_interactive": True,
    },
)

state = process_command(
    init_cmd_map(),
    ScheduledCommand("prompt", value="hello from the SDK"),
    state,
    llt_logger,
)
```

## Development

```bash
uv run --extra dev pytest -q
uv run python -m llt.cli --prompt "smoke" --view --non_interactive
```
