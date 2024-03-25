import os
from message import load_message, write_message, view_message, new_message, prompt_message, remove_message, detach_message, append_message, x_message
from editor import edit_message, include_file, attach_image
from utils import Colors, quit_program
from sequencing import sequence_messages

from api import api_config, full_model_choices

#todo: move count_tokens to plugin that runs every cycle
from utils import count_tokens

import json
import datetime

# PYTHON_ARGCOMPLETE_OK
import argcomplete, argparse

plugins = {
    'load': load_message,
    'write': write_message,
    'view': view_message,
    'new': new_message,
    'complete': prompt_message,
    'edit': edit_message,
    'file': include_file,
    'quit': quit_program,
    'image': attach_image,
    'remove': remove_message,
    'detach': detach_message,
    'append': append_message,
    'xcut': x_message,
    'sequence': sequence_messages
}

def init_arguments():
    llt_path = os.getenv('LLT_PATH') or exit("LLT_PATH environment variable not set.")
    config = api_config
    default_cmd_dir = os.path.join(llt_path, config['cmd_dir'])
    default_exec_dir = os.path.join(llt_path, config['exec_dir'])
    default_ll_dir = os.path.join(llt_path, config['ll_dir'])
    for directory in [default_ll_dir, default_exec_dir, default_cmd_dir]:
        if not os.path.isdir(directory):
            os.makedirs(directory)

    def parse_arguments():
        parser = argparse.ArgumentParser(description="llt, the little language terminal")

        def get_ll_files(prefix, parsed_args, **kwargs):
            ll_dir = parsed_args.ll_dir if parsed_args.ll_dir else default_ll_dir
            return [f for f in os.listdir(ll_dir) if f.startswith(prefix)]

        parser.add_argument('--ll_file', '-l', type=str,
                            help="Language log file. List of natural language messages stored as JSON.",
                            default="").completer = get_ll_files
        parser.add_argument('--file_include', '-f', type=str,
                            help="Read content from a file and include it in the ll.", default="")
        parser.add_argument('--image_path', type=str, default="")

        parser.add_argument('--prompt', '-p', type=str, help="Prompt string.", default="")
        parser.add_argument('--role', '-r', type=str,
                            help="Specify role.", default="user")

        parser.add_argument('--model', '-m', type=str,
                            help="Specify model.", default="claude-3-opus-20240229", 
                            choices=full_model_choices)
        parser.add_argument('--temperature', '-t', type=float,
                            help="Specify temperature.", default=0.9)
        
        parser.add_argument('--max_tokens', type=int, 
                            help="Maximum number of tokens to generate.", default=4096)
        parser.add_argument('--logprobs', type=int, 
                            help="Include log probabilities in the output, up to the specified number of tokens.", default=0)

        parser.add_argument('--cmd_dir', type=str, default=default_cmd_dir)
        parser.add_argument('--exec_dir', type=str, default=default_exec_dir)
        parser.add_argument('--ll_dir', type=str, default=default_ll_dir)

        parser.add_argument('--non_interactive', '-n', action='store_true', help="Run in non-interactive mode.")

        argcomplete.autocomplete(parser)

        return parser.parse_args()

    args = parse_arguments()
    return args

def log_command(command: str, message_before: dict, message_after: dict, args: dict) -> None:
    tokens_before = count_tokens(message_before, args.model) if message_before else 0
    tokens_after = count_tokens(message_after, args.model) if message_after else 0
    token_delta = tokens_after - tokens_before
    log_path = os.path.join(args.cmd_dir, os.path.splitext(args.ll_file)[0] + ".log")
    with open(log_path, 'a') as logfile:
        logfile.write(f"COMMAND_START\n")
        logfile.write(f"timestamp: {datetime.datetime.now().isoformat()}\n")
        logfile.write(f"before_command: {json.dumps(message_before, indent=2)}\n")  
        logfile.write(f"model: {args.model}\n")  
        logfile.write(f"command: {command}\n")
        logfile.write(f"after_command: {json.dumps(message_after, indent=2)}\n")
        logfile.write(f"tokens_before: {tokens_before}\n")
        logfile.write(f"tokens_after: {tokens_after}\n")
        logfile.write(f"token_delta: {token_delta}\n")
        logfile.write(f"COMMAND_END\n\n")

def help_message(messages: list, args: dict) -> list:
    print("Available commands:")
    for command, func in plugins.items():
        print(f"  {command}: {func}")
    return messages

def main():
    args = init_arguments()
    messages = list()
    if args.ll_file:
        messages = load_message(messages, args)
    if args.file_include:
        messages = include_file(messages, args)
    if args.prompt:
        messages.append({'role': 'user', 'content': args.prompt})
    if args.non_interactive:
        messages = prompt_message(messages, args)
        quit_program(messages, args)
    
    Colors.print_header()
    
    greeting = f"Hello {os.getenv('USER')}! You are using model {args.model}. Type 'help' for available commands."
    print(f"{greeting}\n")

    command_map = {**plugins, **{command[0]: func for command, func in plugins.items() if command[0] not in plugins}, 'help': help_message}

    while True:
        cmd = input('llt> ')
        if cmd in command_map:
            message_before = messages[-1] if messages else {}
            messages = command_map[cmd](messages, args)
            log_command(cmd, message_before, messages[-1] if messages else {}, args)
        else:
            print("Unknown command.")

if __name__ == "__main__":
    main()

