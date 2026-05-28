import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def run_llt(tmp_path, *args):
    env = os.environ.copy()
    env["LLT_PATH"] = str(tmp_path / "llt-home")
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-m", "llt.cli", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )


def audit_entries(tmp_path):
    logs = list((tmp_path / "llt-home" / "cmd").glob("session_*.log.jsonl"))
    assert len(logs) == 1
    return [json.loads(line) for line in logs[0].read_text().splitlines()]


def all_audit_entries(tmp_path):
    entries = []
    for log in sorted((tmp_path / "llt-home" / "cmd").glob("session_*.log.jsonl")):
        entries.extend(json.loads(line) for line in log.read_text().splitlines())
    return entries


def test_cli_prompt_view_writes_audit_log(tmp_path):
    result = run_llt(
        tmp_path,
        "--prompt",
        "hello audit",
        "--view",
        "--non_interactive",
    )

    assert result.returncode == 0, result.stderr
    assert "hello audit" in result.stdout

    entries = audit_entries(tmp_path)
    assert [entry["command"]["name"] for entry in entries] == ["prompt", "view"]
    assert entries[0]["state_delta"]["messages_added"][0]["content_sha256"]
    assert entries[1]["output_summary"]["status"] == "success"


def test_repeated_commands_and_view_all_preserve_cli_order(tmp_path):
    result = run_llt(
        tmp_path,
        "--prompt",
        "one",
        "--prompt",
        "two",
        "--view",
        "--view-all",
        "--non_interactive",
    )

    assert result.returncode == 0, result.stderr
    assert "one" in result.stdout
    assert "two" in result.stdout
    assert [entry["command"]["value"] for entry in audit_entries(tmp_path)] == [
        "one",
        "two",
        {"enabled": True, "all": True},
    ]


def test_cli_loads_custom_plugin_with_params(tmp_path):
    result = run_llt(
        tmp_path,
        "--plugins",
        str(ROOT / "examples" / "custom_plugin.py"),
        "--hello-world",
        "--hello-world-name",
        "Codex",
        "--hello-world-uppercase",
        "--non_interactive",
    )

    assert result.returncode == 0, result.stderr
    assert "HELLO, CODEX!" in result.stdout


def test_command_failure_is_audited(tmp_path):
    plugin = tmp_path / "bad_plugin.py"
    plugin.write_text(
        """
from llt.tools import llt

@llt(flag="explode", type="bool", description="raise an error")
def explode(messages, context, index):
    raise RuntimeError("boom")
""".strip()
    )

    result = run_llt(
        tmp_path,
        "--plugins",
        str(plugin),
        "--explode",
        "--non_interactive",
    )

    assert result.returncode == 0, result.stderr
    entries = audit_entries(tmp_path)
    assert entries[0]["command"]["name"] == "explode"
    assert entries[0]["output_summary"]["status"] == "failure"
    assert "RuntimeError: boom" == entries[0]["output_summary"]["error"]


def test_redact_plugin_sanitizes_saved_log_and_audits_delta(tmp_path):
    secret = "sk-demo-ABC123"
    raw = run_llt(
        tmp_path,
        "--prompt",
        f"rotate leaked key {secret}",
        "--save",
        "raw.ll",
        "--non_interactive",
    )
    assert raw.returncode == 0, raw.stderr

    redacted = run_llt(
        tmp_path,
        "--plugins",
        str(ROOT / "examples" / "redact_plugin.py"),
        "--load",
        "raw.ll",
        "--redact",
        "--redact-pattern",
        "sk-demo-[A-Za-z0-9]+",
        "--redact-replacement",
        "[ROTATED_KEY]",
        "--save",
        "redacted.ll",
        "--view",
        "--non_interactive",
    )
    assert redacted.returncode == 0, redacted.stderr
    assert "[ROTATED_KEY]" in redacted.stdout
    assert secret not in redacted.stdout

    saved = json.loads((tmp_path / "llt-home" / "ll" / "redacted.ll").read_text())
    assert saved[0]["content"] == "rotate leaked key [ROTATED_KEY]"

    redact_entries = [
        entry for entry in all_audit_entries(tmp_path) if entry["command"]["name"] == "redact"
    ]
    assert len(redact_entries) == 1
    assert redact_entries[0]["state_delta"]["messages_removed_indices"] == [0]
    assert redact_entries[0]["state_delta"]["messages_added"][0]["content_sha256"]
