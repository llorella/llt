#!/usr/bin/python3
import os
import json
import datetime
import argcomplete
import argparse
from typing import List, Dict
from enum import Enum, auto
import traceback

from message import load_message, write_message, view_message, new_message, remove_message, detach_message, append_message, cut_message, change_role, insert_message
from editor import code_message, include_file, execute_command, edit_content, copy_to_clipboard
from utils import Colors, quit_program, tokenize, export_messages, convert_text_base64, get_valid_index, save_config, update_config
from api import api_config, full_model_choices, get_completion
from gmail import send_email
from web import process_web_request

#from logcmd_llt_branch_1 import search_messages, export_messages_to_markdown

from exa import llt_plugin

class ArgKey(Enum):
    LL = auto()
    DETACH = auto()
    FILE = auto()
    PROMPT = auto()
    COMPLETE = auto()
    EXPORT = auto()
    ROLE = auto()
    EXEC = auto()
    SEARCH = auto()
    URL = auto()
    EMAIL = auto()
    BASE64 = auto()
    VIEW = auto()
    NON_INTERACTIVE = auto()
    WRITE = auto()

plugins = {
    'load': load_message,
    'write': write_message,
    'view': view_message,
    'prompt': new_message,
    'complete': get_completion,
    'edit': code_message,
    'file': include_file,
    'quit': quit_program,
    'insert': insert_message,
    'remove': remove_message,
    'detach': detach_message,
    'append': append_message,
    'cut': cut_message,
    'exa': llt_plugin
}

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    def get_ll_files(prefix: str, parsed_args: argparse.Namespace, **kwargs) -> List[str]:
        ll_dir = parsed_args.ll_dir if parsed_args.ll_dir else os.path.join(os.getenv('LLT_PATH'), api_config['ll_dir'])
        return [f for f in os.listdir(ll_dir) if f.startswith(prefix)]

    parser.add_argument('--ll', '-l', type=str, help="Language log file. JSON formatted list of natural language messages.", default="").completer = get_ll_files
    parser.add_argument('--file', '-f', type=str, help="Read content from a file and include it in the ll.", default="")
    parser.add_argument('--image_path', type=str, default="")

    parser.add_argument('--prompt', '-p', type=str, help="Prompt string.", default="")
    parser.add_argument('--role', '-r', type=str, help="Specify role.", default="user")

    parser.add_argument('--model', '-m', type=str, help="Specify model.", default="gpt-4-turbo", choices=full_model_choices)
    parser.add_argument('--temperature', '-t', type=float, help="Specify temperature.", default=0.9)
    
    parser.add_argument('--max_tokens', type=int, help="Maximum number of tokens to generate.", default=4096)
    parser.add_argument('--logprobs', type=int, help="Include log probabilities in the output, up to the specified number of tokens.", default=0)
    parser.add_argument('--top_p', type=float, help="Sample from top P tokens.", default=1.0)

    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['cmd_dir']))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['exec_dir']))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['ll_dir']))

    parser.add_argument('--non_interactive', '-n', action='store_true', help="Run in non-interactive mode.")

    # All plugin flags here
    parser.add_argument('--complete', action='store_true', help="Complete the last message.")
    parser.add_argument('--detach', action='store_true', help="Pop last message from given ll.")
    parser.add_argument('--export', action='store_true', help="Export messages to a file.")
    parser.add_argument('--exec', action='store_true', help="Execute the last message")
    parser.add_argument('--view', action='store_true', help="Print the last message.")
    parser.add_argument('--write', action='store_true', help="Write conversation to file (for non-interactive mode).")

    parser.add_argument('--search', action='store_true', help="Exa search plugin.")
    parser.add_argument('--email', action='store_true', help="Send an email with the last message.")
    parser.add_argument('--url', type=str, help="Dump a list of user specified tags and their contents to next message.", default=None, choices=['pre', 'p'])

    argcomplete.autocomplete(parser)
    return parser.parse_args()

def init_directories(args: argparse.Namespace) -> None:
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)

def log_command(command: str, messages: List[Dict], args: dict) -> None:
    if command.startswith('v') or command.startswith('h') or not messages: return
    tokens = tokenize(messages, args) if messages else 0
    log_path = os.path.join(args.cmd_dir, os.path.splitext(os.path.basename(args.ll))[0] + ".log")
    if not os.path.exists(log_path): os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, 'a') as logfile:
        logfile.write(f"COMMAND_START\n")
        logfile.write(f"timestamp: {datetime.datetime.now().isoformat()}\n")
        logfile.write(f"before_command: {json.dumps(messages, indent=2)}\n")  
        logfile.write(f"args: {json.dumps(vars(args), indent=2)}\n")
        logfile.write(f"command: {command}\n")
        logfile.write(f"input: TO IMPLEMENT\n")
        logfile.write(f"after_command: {json.dumps(messages[-1], indent=2)}\n")
        logfile.write(f"tokens: {tokens}\n")
        logfile.write(f"COMMAND_END\n\n")

def help_message(messages: List[Dict], args: argparse.Namespace) -> List[Dict]:
    function_to_commands = {}
    for command, function in get_combined_commands().items():
        if function not in function_to_commands:
            function_to_commands[function] = []
        function_to_commands[function].append(command)

    for function, cmds in function_to_commands.items():
        cmds.sort(key=lambda x: len(x), reverse=True)
        print(f"({', '.join(cmds)}): {function}")
    return messages

test_commands = {
    'sc': save_config,
    'uc': update_config,
    'cr': change_role,
    'ec': edit_content,
    'help': help_message, 
    'base64': convert_text_base64,
    'execute': execute_command,
    'email': send_email,
    'web': process_web_request}

def get_combined_commands():
    combined = {}
    for command, function in {**plugins, **test_commands}.items():
        combined[command] = function
        if command[0] not in combined: combined[command[0]] = function
        elif len(command) > 2 and command[1] not in combined: combined[command[1]] = function
    return combined    

def run_non_interactive(messages: List[Dict], args: argparse.Namespace) -> None:
    if args.ll and args.write: write_message(messages, args)
    quit_program(messages, args)

user_greeting = lambda username, args: f"Hello {username}! You are using ll file {args.ll if args.ll else None}, with model {args.model} set to temperature {args.temperature}. Type 'help' for available commands."
#  add buffer for any input that is not a command nor a message
#  only available for interactive mode user input spec: function type that invokes some input fn with format string specific to plugin command invocation
#  i.e., load and write calls input fn with format string "Enter file path (default is {default_file}): "
#  n cmd and/or freeforn at the cmd line, "the meta-command" is the else clause in main cmd loop
def main() -> None:
    args = parse_arguments()
    init_directories(args)
    messages = list()

    startup_functions =  {
        ArgKey.LL: load_message,
        ArgKey.FILE: include_file,
        ArgKey.PROMPT: new_message,
        ArgKey.DETACH: detach_message,
        ArgKey.EXPORT: export_messages,
        ArgKey.SEARCH: llt_plugin,
        ArgKey.EXEC: execute_command,
        ArgKey.URL: process_web_request,
        ArgKey.EMAIL: send_email,
        ArgKey.BASE64: convert_text_base64,
        ArgKey.COMPLETE: get_completion,
        ArgKey.VIEW: view_message,
        ArgKey.NON_INTERACTIVE: run_non_interactive,
        ArgKey.WRITE: write_message
    }
    
    for arg_key, func in startup_functions.items():
        if getattr(args, arg_key.name.lower(), None):
            messages = func(messages, args)

    Colors.print_header()
    print(user_greeting(os.getenv('USER'), args))
    command_map = get_combined_commands()
    while True:
        try:
            cmd = input('llt> ')
            if cmd in command_map:
                messages = command_map[cmd](messages, args)
                log_command(cmd, messages, args)
            elif cmd: messages.append({'role': args.role, 'content': f"{cmd}"})
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}\nAppend error ")
            print(traceback.format_exc())

if __name__ == "__main__":
    main()