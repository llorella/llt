# Usage Demo: Auditable Redaction Workflow

This is a real LLT session run against the current repository. The goal was to
use LLT as a small auditable message-log tool, not as an autonomous agent.

The workflow:

1. Create a raw message log containing an incident note.
2. Load that log and run an explicit redaction plugin.
3. Save the sanitized log.
4. Use a second plugin to inspect the sanitized log.
5. Read the JSONL audit trail to verify what happened.

## Demo Plugin

The redaction plugin lives at `examples/redact_plugin.py`. It registers one
explicit command:

```python
@llt(
    flag="redact",
    type="bool",
    description="Redact regex matches from message content",
    params={
        "pattern": {"type": "str", "default": r"sk-[A-Za-z0-9_-]+"},
        "replacement": {"type": "str", "default": "[REDACTED]"},
    },
)
```

There is no hidden tool discovery beyond the file passed with `--plugins`.

## Session

I used a temporary LLT home so the run was isolated:

```bash
rm -rf /tmp/llt-usage-demo
mkdir -p /tmp/llt-usage-demo
```

Then I created a message log:

```bash
LLT_PATH=/tmp/llt-usage-demo uv run python -m llt.cli \
  --prompt 'Incident note: customer luciano@example.com pasted key sk-demo-ABC123 into chat. Follow up: rotate it and summarize next steps.' \
  --save incident.raw.ll \
  --non_interactive
```

That wrote:

```json
[
  {
    "role": "user",
    "content": "Incident note: customer luciano@example.com pasted key sk-demo-ABC123 into chat. Follow up: rotate it and summarize next steps."
  }
]
```

Next I loaded the raw log, redacted the key, saved the sanitized log, and viewed
the result:

```bash
LLT_PATH=/tmp/llt-usage-demo uv run python -m llt.cli \
  --plugins examples/redact_plugin.py \
  --load incident.raw.ll \
  --redact \
  --redact-pattern 'sk-demo-[A-Za-z0-9]+' \
  --redact-replacement '[ROTATED_KEY]' \
  --save incident.redacted.ll \
  --view \
  --non_interactive
```

Output:

```text
redact: replaced 1 occurrence(s)
[0] user
Incident note: customer luciano@example.com pasted key [ROTATED_KEY] into chat. Follow up: rotate it and summarize next steps.
```

The sanitized log is plain JSON:

```json
[
  {
    "role": "user",
    "content": "Incident note: customer luciano@example.com pasted key [ROTATED_KEY] into chat. Follow up: rotate it and summarize next steps."
  }
]
```

Then I used the separate example plugin to inspect the saved log:

```bash
LLT_PATH=/tmp/llt-usage-demo uv run python -m llt.cli \
  --plugins examples/custom_plugin.py \
  --load incident.redacted.ll \
  --count \
  --count-detailed \
  --non_interactive
```

Output:

```text
Total messages: 1
user: 1
first=user last=user
```

## Audit Trail

The run produced normal files under `/tmp/llt-usage-demo`:

```text
cmd/session_*.log.jsonl
ll/incident.raw.ll
ll/incident.redacted.ll
logs/llt.log
```

Summarizing the audit logs:

```text
session_...570.log.jsonl
  prompt success added=1 removed=[]
  save   success added=0 removed=[]

session_...356.log.jsonl
  load   success added=1 removed=[]
  count  success added=0 removed=[]

session_...2d3.log.jsonl
  load   success added=1 removed=[]
  redact success added=1 removed=[0]
  save   success added=0 removed=[]
  view   success added=0 removed=[]
```

The `redact` audit entry records the plugin source module, command args, and a
hash reference for the new message instead of duplicating the full body:

```json
{
  "command": {
    "name": "redact",
    "value": {
      "enabled": true,
      "pattern": "sk-demo-[A-Za-z0-9]+",
      "replacement": "[ROTATED_KEY]"
    },
    "tool_source": "llt_external_redact_plugin_6c6de84fbb2a"
  },
  "state_delta": {
    "messages_added": [
      {
        "type": "message_ref",
        "role": "user",
        "content_length": 126,
        "content_sha256": "f1413640fe7104e2036cdbe8fef452064fffd75f70ba0c6e178c4d68e8ec22bd",
        "index_in_new_state": 0
      }
    ],
    "messages_removed_indices": [0]
  },
  "output_summary": {
    "status": "success",
    "message_count": 1
  }
}
```

## What This Demonstrates

LLT is useful when a language-model workflow should be inspectable as data:

- The source and sanitized conversations are ordinary JSON files.
- The redaction behavior is a small explicit Python plugin.
- The CLI command order is visible from the command line and audit log.
- The audit trail records command args, state changes, plugin source, and hashes.
- Separate plugins can operate on the same saved log without coupling.

This is the product shape worth protecting: a narrow command runner for message
logs with explicit plugins and audit records.
