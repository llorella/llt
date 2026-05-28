#!/usr/bin/env python3
"""LLT command-line entry point."""

from __future__ import annotations

import argparse
import os
import sys

from llt.core.runtime import create_session, get_session, run_llt
from llt.logging import llt_logger
from llt.tools import (
    add_tool_arguments,
    init_cmd_map,
    load_tools,
    pack_namespaced_args,
    schedule_startup_commands,
)
from llt.utils.colors import Colors
from llt.utils.input_handler import llt_interactive_input


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llt",
        description="llt: auditable message logs with explicit Python plugins",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true", help="show this help message and exit")
    parser.add_argument(
        "--plugins",
        type=str,
        action="append",
        help="Python plugin file or directory; can be used multiple times",
    )
    parser.add_argument("--role", "-r", type=str, default="user", help="role for appended prompt messages")
    parser.add_argument("--non_interactive", "-n", action="store_true", help="exit after queued commands")
    parser.add_argument("--debug", action="store_true", help="print runtime debug output")

    llt_path = os.path.expanduser(os.getenv("LLT_PATH", "~/.llt"))
    parser.add_argument("--cmd_dir", type=str, default=os.path.join(llt_path, "cmd"), help="audit log directory")
    parser.add_argument("--exec_dir", type=str, default=os.path.join(llt_path, "exec"), help="plugin workspace directory")
    parser.add_argument("--ll_dir", type=str, default=os.path.join(llt_path, "ll"), help="message log directory")
    parser.add_argument("--isolated", action="store_true", default=False, help="use a fresh per-session directory")
    parser.add_argument("--session_id", type=str, help="resume an in-memory session by id")
    return parser


def _ensure_dirs(*paths: str) -> None:
    for path in paths:
        os.makedirs(os.path.abspath(os.path.expanduser(path)), exist_ok=True)


def _greeting(context: dict) -> str:
    return f"LLT session {context['session_id']}. Type 'help' for commands."


def main() -> None:
    parser = create_parser()
    partial_args, _ = parser.parse_known_args()

    plugin_count = load_tools(partial_args.plugins)
    add_tool_arguments(parser)
    args = parser.parse_args()

    if args.help:
        parser.print_help()
        return

    queue = schedule_startup_commands(args)
    non_interactive = bool(args.non_interactive)

    if args.session_id:
        state = get_session(args.session_id)
        if state is None:
            print(f"Error: session {args.session_id} is not available in this process", file=sys.stderr)
            raise SystemExit(1)
        state = state.with_queue(tuple(state.command_queue) + queue)
    else:
        context = pack_namespaced_args(args)
        if not args.isolated:
            _ensure_dirs(args.ll_dir, args.exec_dir, args.cmd_dir)
            context.update(
                {
                    "ll_dir": args.ll_dir,
                    "exec_dir": args.exec_dir,
                    "cmd_dir": args.cmd_dir,
                }
            )
        state = create_session(context, isolated=args.isolated).with_queue(queue)

    if not non_interactive:
        print(f"Loaded {plugin_count} plugin file(s)")
        Colors.print_header()
        print(_greeting(state.context))

    run_llt(state, init_cmd_map(), llt_logger, llt_interactive_input)


if __name__ == "__main__":
    main()
