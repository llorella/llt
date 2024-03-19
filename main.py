import os
import sys

from message import load_message, write_message, view_message, new_message, prompt_message, remove_message, detach_message, append_message, x_message
from editor import edit_message, include_file, attach_image
from utils import Colors, setup_command_shortcuts, print_available_commands
from api import count_tokens, api_config

import json
import datetime

# PYTHON_ARGCOMPLETE_OK
import argcomplete, argparse

def quit_program(messages, args):
    print("Exiting...")
    sys.exit(0)

def log_command(command: str, message_before: dict, message_after: dict, args: dict) -> None:
    tokens_before = count_tokens(message_before, args.model) if message_before else 0
    tokens_after = count_tokens(message_after, args.model) if message_after else 0
    token_delta = tokens_after - tokens_before
    log_path = os.path.join(args.cmd_dir, os.path.splitext(args.ll_file)[0] + ".log")
    with open(log_path, 'a') as logfile:
        logfile.write(f"COMMAND_START\n")
        logfile.write(f"timestamp: {datetime.datetime.now().isoformat()}\n")
        logfile.write(f"before_command: {json.dumps(message_before, indent=4)}\n")  
        logfile.write(f"model: {args.model}\n")  
        logfile.write(f"command: {command}\n")
        logfile.write(f"after_command: {json.dumps(message_after, indent=4)}\n")
        logfile.write(f"tokens_before: {tokens_before}\n")
        logfile.write(f"tokens_after: {tokens_after}\n")
        logfile.write(f"token_delta: {token_delta}\n")
        logfile.write(f"COMMAND_END\n\n")

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
    'xcut': x_message
}

def init_arguments():
    llt_path = os.getenv('LLT_PATH') or exit("LLT_PATH environment variable not set.")
    config = api_config
    default_conversation_dir = os.path.join(llt_path, config['conversation_dir'])
    default_code_dir = os.path.join(llt_path, config['code_dir'])
    default_cmd_dir = os.path.join(llt_path, config['cmd_dir'])
    for directory in [default_conversation_dir, default_code_dir, default_cmd_dir]:
        if not os.path.isdir(directory):
            os.makedirs(directory)

    def parse_arguments():
        parser = argparse.ArgumentParser(description="llt, the little language terminal")

        def get_conversation_files(prefix, parsed_args, **kwargs):
            conversation_dir = parsed_args.conversation_dir if parsed_args.conversation_dir else default_conversation_dir
            return [f for f in os.listdir(conversation_dir) if f.startswith(prefix)]

        parser.add_argument('--ll_file', '-l', type=str,
                            help="Language log file. Log of natural language messages by at least one party.",
                            default="").completer = get_conversation_files

        parser.add_argument('--file_include', '-f', type=str,
                            help="Content file. (Needs renovating).", default="")
        parser.add_argument('--prompt', '-p', type=str, help="Prompt string.", default="")
        parser.add_argument('--role', '-r', type=str,
                            help="Specify role.", default="user")

        parser.add_argument('--model', '-m', type=str,
                            help="Specify model.", default=config['models']['anthropic'][0], 
                            choices=[model for provider in config['models'] 
                                     for model in config['models'][provider]])
        parser.add_argument('--temperature', '-t', type=float,
                            help="Specify temperature.", default=0.1)
        parser.add_argument('--non_interactive', '-n', action='store_true', help="Run in non-interactive mode.")
        parser.add_argument('--image_path', type=str, default="hello.png")
        parser.add_argument('--code_dir', type=str, default=default_code_dir)
        parser.add_argument('--conversation_dir', type=str, default=default_conversation_dir)
        parser.add_argument('--cmd_dir', type=str, default=default_cmd_dir)

        argcomplete.autocomplete(parser)

        return parser.parse_args()

    args = parse_arguments()
    return args



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

    user = os.getenv('USER')
    greeting = f"Hello {user}! You are using model {args.model}. Type 'help' for available commands."
    print(f"{greeting}\n")

    command_map = setup_command_shortcuts(plugins)
    print_available_commands(command_map)

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
