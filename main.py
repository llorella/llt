#!/usr/bin/python3
import os
import json
import datetime
import argcomplete
import argparse
from typing import List, Dict, Callable
import traceback
from utils import Colors, llt_input

from plugins import plugins

import importlib.util
def load_plugins(plugin_dir):
    """Dynamically load llt plugins from scripts in the specified dir."""
    for filename in os.listdir(plugin_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            file_path = os.path.join(plugin_dir, filename)
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    def get_ll_files(prefix: str, parsed_args: argparse.Namespace, **kwargs) -> List[str]:
        ll_dir = parsed_args.ll_dir if parsed_args.ll_dir else os.path.join(os.getenv('LLT_PATH'), 'll')
        return [f for f in os.listdir(ll_dir) if f.startswith(prefix)]

    parser.add_argument('--load', '--ll', '-l', type=str, help="Language log file. JSON formatted list of natural language messages.", default="").completer = get_ll_files
    parser.add_argument('--file', '-f', type=str, help="Read content from a file and include it in the ll.", default="")

    parser.add_argument('--prompt', '-p', type=str, help="Prompt string.", default="")
    parser.add_argument('--role', '-r', type=str, help="Specify role.", default="user")

    parser.add_argument('--model', '-m', type=str, help="Specify model.", default="gpt-4-turbo")
    parser.add_argument('--temperature', '-t', type=float, help="Specify temperature.", default=0.9)
    parser.add_argument('--max_tokens', type=int, help="Maximum number of tokens to generate.", default=4096)
    parser.add_argument('--logprobs', type=int, help="Include log probabilities in the output, up to the specified number of tokens.", default=0)
    parser.add_argument('--top_p', type=float, help="Sample from top P tokens.", default=1.0)

    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), 'cmd'))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), 'exec'))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), 'll'))

    parser.add_argument('--non_interactive', '-n', action='store_true', help="Run in non-interactive mode.")

    # All plugin flags here
    parser.add_argument('--completion', '-c', action='store_true', help="Complete the last message.")
    parser.add_argument('--detach', action='store_true', help="Pop last message from given ll.")
    parser.add_argument('--execute', action='store_true', help="Execute the last message")
    parser.add_argument('--view', action='store_true', help="Print the last message.")
    parser.add_argument('--write', action='store_true', help="Write conversation to file (for non-interactive mode).")

    parser.add_argument('--email', action='store_true', help="Send an email with the last message.")
    parser.add_argument('--url', type=str, help="Dump a list of user specified tags and their contents to next message.", default=None, choices=['pre', 'p'])

    argcomplete.autocomplete(parser)
    return parser.parse_args()

def init_directories(args: argparse.Namespace) -> None:
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)

def log_command(command: str, message: dict, args) -> None:
    log_path = f'{args.cmd_dir}/{os.path.splitext(os.path.basename(args.load))[0]}.jsonl'
    with open(log_path, 'a') as logfile:
        logfile.write(json.dumps({'command': command, 'message': message}))

def llt_shell_log(cmd: str):
    file_path = os.path.join(os.getenv('LLT_PATH'), 'llt_shell.log')
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

user_greeting = lambda username, args: f"Hello {username}! You are using ll file {args.load if args.load else None}, with model {args.model} set to temperature {args.temperature}. Type 'help' for available commands."

def llt() -> None:
    args = parse_arguments()
    init_directories(args)
    messages = list()

    cmds = init_cmd_map()
    startup_cmds =  ['load', 'file', 'prompt', 'completion']
    for cmd in cmds:
        if args.__contains__(cmd) and args.__getattribute__(cmd) and cmd in startup_cmds:
            messages = cmds[cmd](messages, args)

    Colors.print_header()
    print(user_greeting(os.getenv('USER'), args))

    while True:
        try:
            cmd = llt_input(cmds.keys())
            if cmd in cmds:
                messages = cmds[cmd](messages, args)
                log_command(cmd, messages, args)
            else: messages.append({ 'role': args.role, 'content': cmd})
            llt_shell_log(cmd)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}\n")
            print(traceback.format_exc())

if __name__ == "__main__":
    plugin_dir = os.getenv('LLT_DIR') + '/plugins' if os.getenv('LLT_DIR') else './plugins'
    load_plugins(plugin_dir)
    llt()