#!/usr/bin/python3
import os
import json
import argparse
import importlib.util
from typing import List, Dict, Callable
import traceback
import argcomplete

from utils import Colors, llt_input
from plugins import plugins


def load_plugins(plugin_dir: str) -> None:
    """Dynamically load llt plugins from scripts in the specified directory."""
    for filename in os.listdir(plugin_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            file_path = os.path.join(plugin_dir, filename)
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            try:
                module = importlib.util.module_from_spec(spec)
                if module:
                    spec.loader.exec_module(module)
            except ImportError as e:
                print(f"Failed to import {module_name} due to {e}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    def get_ll_files(prefix: str, parsed_args: argparse.Namespace, **kwargs) -> List[str]:
        ll_dir = parsed_args.ll_dir if hasattr(parsed_args, 'll_dir') else os.path.join(os.getenv('LLT_PATH', ''), 'll')
        return [f for f in os.listdir(ll_dir) if f.startswith(prefix)]

    parser.add_argument('--load', '--ll', '-l', type=str, help="Conversation history file. JSON formatted list of natural language messages.", default="").completer = get_ll_files
    parser.add_argument('-f', '--file', type=str, help="Source file to include in the current session.", default="")
    parser.add_argument('-p', '--prompt', type=str, help="Prompt string.", default="")
    parser.add_argument('-r', '--role', type=str, help="Specify role.", default="user")
    parser.add_argument('-m', '--model', type=str, help="Specify model.", default="gpt-4-turbo")
    parser.add_argument('-t', '--temperature', type=float, help="Specify temperature.", default=0.9)
    parser.add_argument('--max_tokens', type=int, help="Maximum number of tokens to generate.", default=4096)
    parser.add_argument('--logprobs', type=int, help="Include log probabilities in the output.", default=0)
    parser.add_argument('--top_p', type=float, help="Sample from top P tokens.", default=1.0)
    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'cmd'))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'exec'))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'll'))
    parser.add_argument('-n', '--non_interactive', action='store_true', help="Run in non-interactive mode.")

    # Plugin flags
    parser.add_argument('-c', '--completion', action='store_true', help="Complete the last message.")
    parser.add_argument('--detach', action='store_true', help="Pop last message from given ll.")
    parser.add_argument('--execute', action='store_true', help="Execute the last message")
    parser.add_argument('--view', action='store_true', help="Print the last message.")
    parser.add_argument('--write', action='store_true', help="Write conversation to file (for non-interactive mode).")
    parser.add_argument('--email', action='store_true', help="Send an email with the last message.")
    parser.add_argument('--url', type=str, help="Dump a list of user specified tags to the next message.", default=None, choices=['pre', 'p'])

    argcomplete.autocomplete(parser)
    return parser.parse_args()


def init_directories(args: argparse.Namespace) -> None:
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)

def log_command(command: str, message: dict, args: argparse.Namespace) -> None:
    """Log the executed command with transformed message to a specified log file."""
    log_path = f"{args.cmd_dir}/{os.path.splitext(os.path.basename(args.load))[0]}.jsonl"
    with open(log_path, 'a') as logfile:
        logfile.write(json.dumps({'command': command, 'message': message}) + "\n")

def llt_shell_log(cmd: str) -> None:
    file_path = os.path.join(os.getenv('LLT_PATH', ''), 'llt_shell.log')
    with open(file_path, 'a') as logfile:
        logfile.write(f"llt> {cmd}\n")

n_abbv = lambda s, n=1: s[:n].lower() 

def init_cmd_map()-> Dict[str, Callable]:
    command_map = {}
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
            if split_cmd: command_map[split_cmd[0]] = function
    return command_map

def user_greeting(username: str, args: argparse.Namespace) -> str:
    return f"Hello {username}! Using ll file {args.load}, with model {args.model} at temperature {args.temperature}. Type 'help' for commands."

def llt() -> None:
    args = parse_arguments()
    init_directories(args)
    messages = []

    cmds = init_cmd_map()
    startup_cmds = ['load', 'file', 'prompt', 'completion']
    for cmd in cmds:
        if getattr(args, cmd, None) and cmd in startup_cmds:
            messages = cmds[cmd](messages, args)

    Colors.print_header()
    print(user_greeting(os.getenv('USER', 'User'), args))

    while True:
        try:
            cmd = llt_input(list(cmds.keys()))
            if cmd in cmds:
                messages = cmds[cmd](messages, args)
                log_command(cmd, messages, args)
            else:
                messages.append({'role': args.role, 'content': cmd})
            llt_shell_log(cmd)
        except KeyboardInterrupt:
            print("\nCommand interrupted.")
        except Exception as e:
            print(f"An error occurred: {e}\n{traceback.format_exc()}")

if __name__ == "__main__":
    plugin_dir = os.path.join(os.getenv('LLT_DIR', ''), 'plugins')
    load_plugins(plugin_dir)
    llt()