#!/usr/bin/python3

import os
import json
import argparse
import importlib.util
from typing import List, Dict, Callable
import traceback
import argcomplete
import time  # Added for timing

from utils import Colors, llt_input
from plugins import plugins

startup_cmds = ["load", "execute", "prompt", "file", "completion", "remove", "fold"]


def load_plugins(plugin_dir: str) -> None:
    """Dynamically load llt plugins from scripts in the specified directory."""
    Colors.print_bold(f"Loading plugins from directory: {plugin_dir}", Colors.BLUE)
    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            file_path = os.path.join(plugin_dir, filename)
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            try:
                module = importlib.util.module_from_spec(spec)
                if module:
                    spec.loader.exec_module(module)
            except ImportError as e:
                Colors.print_colored(
                    f"Failed to import {module_name} due to {e}", Colors.RED
                )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments with dynamic plugin flags."""
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    for plugin in plugins.keys():
        if plugin not in ["help", "quit"]:  # these are already added
            parser.add_argument(f"--{plugin}", type=str, help=f"Run {plugin} plugin.")

    parser.add_argument(
        "--model", type=str, help="Specify model.", default="gpt-4o-latest"
    )
    parser.add_argument("--role", type=str, help="Specify role.", default="user")
    parser.add_argument(
        "--temperature", type=float, help="Specify temperature.", default=0.3
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        help="Maximum number of tokens to generate.",
        default=4096,
    )
    parser.add_argument(
        "--logprobs",
        type=int,
        help="Include log probabilities in the output.",
        default=0,
    )
    parser.add_argument(
        "--top_p", type=float, help="Sample from top P tokens.", default=1.0
    )

    parser.add_argument(
        "--cmd_dir", type=str, default=os.path.join(os.getenv("LLT_PATH", ""), "cmd")
    )
    parser.add_argument(
        "--exec_dir", type=str, default=os.path.join(os.getenv("LLT_PATH", ""), "exec")
    )
    parser.add_argument(
        "--ll_dir", type=str, default=os.path.join(os.getenv("LLT_PATH", ""), "ll")
    )

    parser.add_argument(
        "-n",
        "--non_interactive",
        action="store_true",
        help="Run in non-interactive mode.",
    )

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    return args


def init_directories(args: argparse.Namespace) -> None:
    """Initialize necessary directories."""
    if args.exec_dir == ".":
        args.exec_dir = os.path.join(os.getcwd())
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)


def log_command(command: str, message: dict, args: argparse.Namespace) -> None:
    """Log the executed command with transformed message to a specified log file."""
    log_filename = os.path.splitext(args.load if args.load else "zero")[0]
    log_path = os.path.join(args.cmd_dir, f"{log_filename}.jsonl")
    try:
        with open(log_path, "a") as logfile:
            logfile.write(json.dumps({"command": command, "message": message}) + "\n")
    except Exception as e:
        Colors.print_colored(f"Failed to log command '{command}': {e}", Colors.RED)


def llt_shell_log(cmd: str) -> None:
    """Log shell commands to a log file."""
    file_path = os.path.join(os.getenv("LLT_PATH", ""), "llt_shell.log")
    try:
        with open(file_path, "a") as logfile:
            logfile.write(f"llt> {cmd}\n")

    except Exception as e:
        Colors.print_colored(f"Failed to log shell command '{cmd}': {e}", Colors.RED)


n_abbv = lambda s, n=1: s[:n].lower()


def init_cmd_map() -> Dict[str, Callable]:
    """Initialize a command map with plugin commands and their abbreviations."""
    command_map = {}
    plugin_keys = ", ".join(plugins.keys())
    Colors.print_colored(f"{f'Available plugins'}: {plugin_keys}", Colors.LIGHT_GREEN)
    for cmd, function in plugins.items():
        if cmd not in command_map:
            command_map[cmd] = function
        if n_abbv(cmd) not in command_map:
            command_map[n_abbv(cmd)] = function
        elif len(cmd) > 2 and n_abbv(cmd, 2) not in command_map:
            command_map[n_abbv(cmd, 2)] = function
        seps = ["-", "_"]
        for sep in seps:
            split_cmd = cmd.split(sep)
            if split_cmd:
                command_map[split_cmd[0]] = function
    return command_map


def user_greeting(username: str, args: argparse.Namespace) -> str:
    """Generate a greeting message for the user."""
    load_file = getattr(args, "load", "None")
    greeting = (
        f"Hello {username}! Using ll file {load_file}, "
        f"with model {args.model} at temperature {args.temperature}. "
        f"Type 'help' for commands."
    )
    return greeting


def display_greeting(username: str, args: argparse.Namespace) -> None:
    """Display the user greeting in a stylized format."""
    greeting_text = user_greeting(username, args)
    header = (
        f"{Colors.BOLD}{Colors.WHITE}{'='*len(greeting_text)}\n"
        f"{greeting_text}\n"
        f"{'='*len(greeting_text)}{Colors.RESET}"
    )
    print(header)


def llt() -> None:
    """Main function to run the llt shell."""
    args = parse_arguments()
    init_directories(args)
    messages = []

    cmds = init_cmd_map()
    for cmd in cmds:
        if hasattr(args, cmd) and getattr(args, cmd):
            messages = cmds[cmd](messages, args)

    Colors.print_header()
    display_greeting(os.getenv("USER", "User"), args)

    # Main interactive loop
    while True:
        try:
            loop_start_time = time.perf_counter()
            cmd = llt_input(list(cmds.keys()))
            if cmd in cmds:
                command_start_time = time.perf_counter()
                messages = cmds[cmd](messages, args)
                log_command(cmd, messages, args)
                command_end_time = time.perf_counter()
                Colors.print_colored(
                    f"Executed command '{cmd}' in {command_end_time - command_start_time:.4f} seconds",
                    Colors.GREEN,
                )
            else:
                messages.append({"role": args.role, "content": cmd})
            llt_shell_log(cmd)
            loop_end_time = time.perf_counter()
            Colors.print_colored(
                f"Loop iteration completed in {loop_end_time - loop_start_time:.6f} seconds",
                Colors.LIGHT_BLUE,
            )
        except KeyboardInterrupt:
            Colors.print_colored("\nCommand interrupted. Exiting...", Colors.RED)
            break  # Gracefully exit on interrupt
        except Exception as e:
            Colors.print_colored(f"An error occurred: {e}", Colors.RED)
            print(traceback.format_exc())


if __name__ == "__main__":
    plugin_dir = os.path.join(os.getenv("LLT_DIR", ""), "plugins")
    load_plugins(plugin_dir)
    llt()
