#!/usr/bin/env python3
# main.py

import os
import argparse
import traceback
import argcomplete
from typing import Dict, Callable

from logger import llt_logger
from utils.helpers import Colors, llt_input
from plugins import plugins, load_plugins  # Our plugin registry + dynamic loading


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    # Common arguments
    parser.add_argument('--load', '--ll', '-l', type=str, help="Conversation file (JSON)", default="")
    parser.add_argument('--file', '-f', type=str, help="A file path for code or data", default="")
    parser.add_argument('--prompt', '-p', type=str, help="Prompt text", default="")
    parser.add_argument('--role', '-r', type=str, help="Specify role (user, system, etc.)", default="user")
    parser.add_argument('--model', '-m', type=str, help="Which LLM model to use", default="gpt-4o-mini")
    parser.add_argument('--temperature', '-t', type=float, help="Sampling temperature", default=0.9)
    parser.add_argument('--max_tokens', type=int, help="Max tokens to generate", default=4096)
    parser.add_argument('--logprobs', type=int, help="Include logprobs in completion", default=0)
    parser.add_argument('--top_p', type=float, help="Top-p sampling", default=1.0)

    # Directories
    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'cmd'))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'exec'))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'll/'))

    # Interactive / Non-interactive
    parser.add_argument('--non_interactive', '-n', action='store_true', 
                        help="Run in non-interactive mode (batch)")

    # Plugin-related flags (direct calls)
    parser.add_argument('--complete', '-c', action='store_true', help="Call 'complete' plugin on last message")
    parser.add_argument('--write', type=str, help="Write conversation to a file")
    parser.add_argument('--detach', action='store_true', help="Detach last message")
    parser.add_argument('--fold', action='store_true', help="Fold consecutive messages of same role")
    parser.add_argument('--execute', action='store_true', help="Execute code blocks in last message")
    parser.add_argument('--view', action='store_true', help="View the last message")
    parser.add_argument('--email', action='store_true', help="Send an email with the last message")
    parser.add_argument('--url', type=str, help="Fetch content from a URL")
    parser.add_argument('--tags', type=str, help="HTML tags to fetch from URL", default='content')
    parser.add_argument('--xml_wrap', '--xml', type=str, help="Wrap last message in an XML tag")
    parser.add_argument('--embeddings', type=str, help="Path to embeddings DB (csv) or dir for generating embeddings")

    argcomplete.autocomplete(parser)
    return parser.parse_args()


def init_directories(args: argparse.Namespace) -> None:
    if args.exec_dir == ".":
        args.exec_dir = os.path.join(os.getcwd())
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)


def user_greeting(username: str, args: argparse.Namespace) -> str:
    load_file = getattr(args, "load", "None")
    return (
        f"Hello {username}! Using ll file {load_file}, "
        f"with model {args.model} at temperature {args.temperature}. "
        f"Type 'help' for commands."
    )


def display_greeting(username: str, args: argparse.Namespace) -> None:
    greeting_text = user_greeting(username, args)
    header = (
        f"{Colors.BOLD}{Colors.WHITE}{'='*len(greeting_text)}\n"
        f"{greeting_text}\n"
        f"{'='*len(greeting_text)}{Colors.RESET}"
    )
    print(header)


def llt_shell_log(cmd: str) -> None:
    """Log shell commands to a log file."""
    import sys
    llt_path = os.getenv("LLT_PATH", "")
    if not llt_path:
        return
    file_path = os.path.join(llt_path, "llt_shell.log")
    try:
        with open(file_path, "a") as logfile:
            logfile.write(f"llt> {cmd}\n")
    except Exception as e:
        Colors.print_colored(f"Failed to log shell command '{cmd}': {e}", Colors.RED)


def run_startup_plugins(messages: list, args: argparse.Namespace, cmd_map: Dict[str, Callable]) -> list:
    """
    Map certain CLI flags to plugins. 
    E.g. if args.complete is True, call the 'complete' plugin. 
    This is more flexible than a hard-coded list.
    """
    flag_to_plugin_call = [
        # (boolean_flag_or_value, plugin_name)
        (args.complete, 'complete'),
        (args.load, 'load'),
        (args.file, 'file'),
        (args.prompt, 'prompt'),
        (args.write, 'write'),       # if write is non-empty string
        (args.detach, 'detach'),
        (args.fold, 'fold'),
        (args.execute, 'execute'),   # or "execute_command" if that’s your plugin name
        (args.view, 'view'),
        (args.email, 'email'),       # if you have a plugin for emailing
        (args.url, 'url_fetch'),     # or "url" plugin
        (args.xml_wrap, 'xml_wrap'),
        (args.embeddings, 'embeddings'),  # or "embeddings" plugin
    ]

    for flag_value, plugin_name in flag_to_plugin_call:
        if flag_value:
            if plugin_name in cmd_map:
                messages = cmd_map[plugin_name](messages, args, index=-1)
    return messages


def llt() -> None:
    args = parse_arguments()
    init_directories(args)
    messages = []

    # Build a cmd_map from the plugin registry
    from plugins import init_cmd_map
    cmd_map = init_cmd_map()

    # Now call the startup plugins based on CLI flags
    messages = run_startup_plugins(messages, args, cmd_map)

    # Print header
    from utils.helpers import Colors
    Colors.print_header()

    llt_logger.log_info("llt interactive session started", {
        key: val for key, val in vars(args).items()
    })

    print(user_greeting(os.getenv('USER', 'User'), args))

    if args.non_interactive:
        # If in batch mode, we won't enter the interactive loop
        return

    # Interactive loop
    while True:
        try:
            cmd, index = llt_input(list(cmd_map.keys()))
            if cmd in cmd_map:
                messages_before = messages.copy()
                messages = cmd_map[cmd](messages, args, index)
                llt_logger.log_command(cmd, messages_before, messages, args)  # log command to file
            else:
                # Unrecognized plugin => treat as user message
                messages.append({'role': args.role, 'content': cmd})
                llt_logger.log_info("User input added", {"role": args.role, "content_length": len(cmd)})
            llt_shell_log(cmd)
        except KeyboardInterrupt:
            llt_logger.log_info("Command interrupted")
            print("\nCommand interrupted.")
        except Exception as e:
            llt_logger.log_error(str(e), {"traceback": traceback.format_exc()})
            print(f"An error occurred: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    import os
    plugin_dir = os.path.join(os.getenv("LLT_DIR", ""), "plugins")
    load_plugins(plugin_dir)  # dynamically load all plugin modules
    llt()
