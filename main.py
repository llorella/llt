import argparse
import os
import sys

from message import load_message, write_message, view_message, new_message, prompt_message, remove_message, detach_message, append_message, cut_message
from editor import edit_message, include_file, attach_image
from utils import Colors, setup_command_shortcuts, print_available_commands
from api import count_tokens, load_config

import json
import datetime

def quit_program(messages, args):
    print("Exiting...")
    sys.exit(0)

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
    'xcut': cut_message
}

def init_arguments():
    def parse_arguments():
        parser = argparse.ArgumentParser(description="llt, the little language terminal")
        
        parser.add_argument('--ll_file', '-l', type=str, 
                            help="Language log file. Log of natural language messages by at least one party.", default="")
        parser.add_argument('--content_file', '-f', type=str, 
                            help="Content file. (Needs renovating).", default="") 
        parser.add_argument('--prompt', '-p', type=str, help="Prompt string.", default="")
        parser.add_argument('--role', '-r', type=str, 
                            help="Specify role.", default="user")
        parser.add_argument('--model', '-m', type=str, 
                            help="Specify model.", default="gpt-4")
        parser.add_argument('--temperature', '-t', type=float, 
                            help="Specify temperature.", default=0.9)
        parser.add_argument('--non_interactive', action='store_true', help="Run in non-interactive mode.")
        parser.add_argument('--image_path', '-i', type=str, default="hello.png")
        parser.add_argument('--code_dir', '-e', type=str, default="exec")
        parser.add_argument('--conversation_dir', '-c', type=str, default="msg")
        parser.add_argument('--cmd_dir', '-d', type=str, default="commands")
        return parser.parse_args()
    
    args = parse_arguments()
    llt_path = os.getenv('LLT_PATH')
    if llt_path:
        args.conversation_dir = os.path.join(llt_path, args.conversation_dir)
        args.code_dir = os.path.join(llt_path, args.code_dir)
        args.cmd_dir = os.path.join(llt_path, args.cmd_dir)
        if not os.path.isdir(args.conversation_dir):
            os.makedirs(args.conversation_dir)
        if not os.path.isdir(args.code_dir):
            os.makedirs(args.code_dir)
        if not os.path.isdir(args.cmd_dir):
            os.makedirs(args.cmd_dir)
    
    return args

def log_command(command: str, message_before: dict, message_after: dict, model, log_path: str) -> None:
    tokens_before = count_tokens(message_before, model)
    tokens_after = count_tokens(message_after, model)
    token_delta = tokens_after - tokens_before

    with open(log_path, 'a') as logfile:
        logfile.write(f"COMMAND_START\n")
        logfile.write(f"timestamp: {datetime.datetime.now().isoformat()}\n")
        logfile.write(f"before_command: {json.dumps(message_before)}\n")  
        logfile.write(f"model: {model}\n")  
        logfile.write(f"command: {command}\n")
        logfile.write(f"after_command: {json.dumps(message_after)}\n") 
        logfile.write(f"tokens_before: {tokens_before}\n")
        logfile.write(f"tokens_after: {tokens_after}\n")
        logfile.write(f"token_delta: {token_delta}\n")
        logfile.write(f"COMMAND_END\n\n")

def main():
    args = init_arguments()
    messages = list()
    if args.ll_file:
        messages = load_message(messages, args)
    if args.content_file:
        messages = include_file(messages, args)
    if args.prompt:
        messages[-1]['content']+= "\n" + args.prompt
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
            message_before = messages[-1]  # shallow copy of message before command execution
            messages = command_map[cmd](messages, args)
            log_command(cmd, message_before, messages[-1], args.model, os.path.join(args.cmd_dir, os.path.splitext(args.ll_file)[0] + ".log"))
        else:
            print("Unknown command.")

if __name__ == "__main__":
    main()