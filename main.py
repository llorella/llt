#!/usr/bin/env python
import os
import json
import datetime
import argcomplete
import argparse
from typing import List, Dict

from message import load_message, write_message, view_message, new_message, prompt_message, remove_message, detach_message, append_message, x_message
from editor import edit_message, include_file, previous_message_content_edit
from utils import Colors, quit_program, count_tokens, tokenize
from api import save_config, update_config, api_config, full_model_choices
from logcmd_llt_branch_1 import undo_last_git_commit, search_messages, export_messages_to_markdown

plugins = {
    'load': load_message,
    'write': write_message,
    'view': view_message,
    'new': new_message,
    'complete': prompt_message,
    'edit': edit_message,
    'file': include_file,
    'quit': quit_program,
    'remove': remove_message,
    'detach': detach_message,
    'append': append_message,
    'xcut': x_message
}

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    def get_ll_files(prefix: str, parsed_args: argparse.Namespace, **kwargs) -> List[str]:
        ll_dir = parsed_args.ll_dir if parsed_args.ll_dir else os.path.join(os.getenv('LLT_PATH'), api_config['ll_dir'])
        return [f for f in os.listdir(ll_dir) if f.startswith(prefix)]

    parser.add_argument('--ll_file', '-l', type=str, help="Language log file. List of natural language messages stored as JSON.", default="").completer = get_ll_files
    parser.add_argument('--file_include', '-f', type=str, help="Read content from a file and include it in the ll.", default="")
    parser.add_argument('--image_path', type=str, default="")

    parser.add_argument('--prompt', '-p', type=str, help="Prompt string.", default="")
    parser.add_argument('--role', '-r', type=str, help="Specify role.", default="user")

    parser.add_argument('--model', '-m', type=str, help="Specify model.", default="gpt-4-0125-preview", choices=full_model_choices)
    parser.add_argument('--temperature', '-t', type=float, help="Specify temperature.", default=0.9)
    
    parser.add_argument('--max_tokens', type=int, help="Maximum number of tokens to generate.", default=4096)
    parser.add_argument('--logprobs', type=int, help="Include log probabilities in the output, up to the specified number of tokens.", default=0)
    parser.add_argument('--top_p', type=float, help="Sample from top P tokens.", default=1.0)

    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['cmd_dir']))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['exec_dir']))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['ll_dir']))

    parser.add_argument('--non_interactive', '-n', action='store_true', help="Run in non-interactive mode.")
    parser.add_argument('--detach', action='store_true', help="Pop last message from given ll.")

    argcomplete.autocomplete(parser)
    return parser.parse_args()

def init_directories(args: argparse.Namespace) -> None:
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)

def log_command(command: str, messages: list, args: dict) -> None:
    tokens = tokenize(messages, args) if messages else 0
    log_path = os.path.join(args['cmd_dir'], os.path.splitext(args['ll_file'])[0] + ".log")
    with open(log_path, 'a') as logfile:
        logfile.write(f"COMMAND_START\n")
        logfile.write(f"timestamp: {datetime.datetime.now().isoformat()}\n")
        logfile.write(f"before_command: {json.dumps(messages[:-1], indent=2)}\n")  
        logfile.write(f"args: {json.dumps(messages[:-1], indent=2)}\n")
        logfile.write(f"command: {command}\n")
        logfile.write(f"input: TO IMPLEMENT\n")
        logfile.write(f"after_command: {json.dumps(messages[-1], indent=2)}\n")
        logfile.write(f"tokens: {tokens}\n")
        logfile.write(f"COMMAND_END\n\n")

def help_message(messages: List[Dict], args: argparse.Namespace) -> List[Dict]:
    print("Available commands:")
    for command, func in plugins.items():
        print(f"  {command}: {func}")
    return messages

test_commands = {'h': help_message, 
                'md': export_messages_to_markdown, 
                "p": previous_message_content_edit, 
                's': search_messages,
                'sc': save_config,
                'uc': update_config}

def main() -> None:
    args = parse_arguments()
    init_directories(args)

    messages = list()
    if args.ll_file:
        messages = load_message(messages, args)
    if args.detach:
        messages = detach_message(messages, args)
    if args.file_include:
        messages = include_file(messages, args)
    if args.prompt:
        messages.append({'role': 'user', 'content': args.prompt})
    if args.non_interactive:
        messages = prompt_message(messages, args)
        if args.ll_file: write_message(messages, args)
        quit_program(messages, args)
    
    Colors.print_header()
    
    greeting = f"Hello {os.getenv('USER')}! You are using model {args.model}. Type 'help' for available commands."
    print(f"{greeting}\n")

    command_map = {**plugins, **{command[0]: func for command, func in plugins.items() if command[0] not in plugins}}           #'seq': sequence_messages,
    command_map.update(test_commands)
    while True:
        try:
            cmd = input('llt> ')
            if cmd in command_map:
                messages = command_map[cmd](messages, args)
                if not cmd.startswith('v'): log_command(cmd, messages, vars(args))
            else:
                messages.append({'role': args.role, 'content': f"{cmd}"})
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    main()
