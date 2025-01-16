#!/usr/bin/env python3
# main.py

import os
import sys
import argparse
import traceback
from typing import Dict, Callable

from logger import llt_logger
from utils import Colors, llt_input
from plugins import load_plugins, add_plugin_arguments, _plugins_registry  # Our plugin registry + dynamic loading

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    # Common arguments
    parser.add_argument('--role', '-r', type=str, help="Specify role (user, system, etc.)", default="user")
    parser.add_argument('--model', '-m', type=str, help="Which LLM model to use", default="deepseek-chat")
    parser.add_argument('--temperature', '-t', type=float, help="Sampling temperature", default=0.9)
    parser.add_argument('--max_tokens', type=int, help="Max tokens to generate", default=8192)
    parser.add_argument('--logprobs', type=int, help="Include logprobs in completion", default=0)
    parser.add_argument('--top_p', type=float, help="Top-p sampling", default=1.0)

    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'cmd'))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'exec'))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'll/'))

    parser.add_argument('--tools', action='store_true', help="Enable tool usage calls.")
    parser.add_argument('--non_interactive', '-n', action='store_true', 
                        help="Run in non-interactive mode.")
    
    add_plugin_arguments(parser)
    return parser.parse_args()


def init_directories(args: argparse.Namespace) -> None:
    if args.exec_dir == ".":
        args.exec_dir = os.path.join(os.getcwd())
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)


def user_greeting(username: str, args: argparse.Namespace) -> str:
    load_file = getattr(args, "load", "None")
    return (
        f"Hello {username}! ll {os.path.relpath(os.path.abspath(args.load), os.path.abspath(args.ll_dir))} is loaded "
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
    Run plugins based on their corresponding CLI flags in the order they were specified.
    """    
    argv = sys.argv[1:]
    
    plugins_to_run = []
    for arg in argv:
        arg = arg.lstrip('-') 
        for plugin_info in _plugins_registry.values():
            flag = plugin_info['flag']
            if flag is None or not hasattr(args, flag):
                continue
            if arg == flag or arg == flag[0]:
                attribute = getattr(args, flag)
                if isinstance(attribute, bool):
                    should_run = attribute
                else:
                    should_run = attribute is not None
                if should_run:
                    plugins_to_run.append(plugin_info['function'])
    
    for fn in plugins_to_run:
        messages = fn(messages, args, index=-1)
    
    return messages


def llt() -> None:
    args = parse_arguments()
    init_directories(args)
    messages = []

    # Build a cmd_map from the plugin registry
    from plugins import init_cmd_map
    cmd_map = init_cmd_map()

    messages = run_startup_plugins(messages, args, cmd_map)

    from utils import Colors
    Colors.print_header()

    """llt_logger.log_info("llt interactive session started", {
        key: val for key, val in vars(args).items()
    })
    """
    print(user_greeting(os.getenv('USER', 'User'), args))

    if args.non_interactive:
        return

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
