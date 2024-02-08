from message import load_message, write_message, view_message, new_message, prompt_message
from editor import edit_message, include_file, attach_image
from utils import Colors, setup_command_shortcuts, print_available_commands

import argparse
from typing import TypedDict, List, Dict
import pprint
import os, sys

def quit(messages, file_path):
    print("Exiting...")
    sys.exit()

plugins = {
    'load' : load_message,
    'write' : write_message,
    'view' : view_message,
    'new' : new_message,
    'complete' : prompt_message,
    'edit' : edit_message,
    'file' : include_file,
    'quit' : quit,
    'image' : attach_image  
}
    

models = ['gpt-4', 'gpt-4-vision-preview', 'gpt-4-1106-preview ']

def parse_arguments():
    parser = argparse.ArgumentParser(description="Message processing tool")
    parser.add_argument('--context_file', '-c', type=str, help="Specify file name for message history context.", default="out.txt")
    parser.add_argument('--content_file', '-f', type=str, help="Specify content file.", default="")

    parser.add_argument('--role', '-r', type=str, help="Specify role.", default="user")
    parser.add_argument('--model', '-m', type=str, help="Specify model. ".join(model for model in models), default=models[0])
    #use function for accepting dict of values and exposing keys for value change.
    return parser.parse_args()


def main():
    Colors.print_header()
    args = parse_arguments()
    
    user = os.environ.get('USER')
    greeting = f"Hello {user}! You are using model {args.model}. Type 'help' for available commands."
    print(f"{greeting}\n")

    messages: List[Dict[str, any]] = []
    if args.context_file:
        messages = load_message(messages, args)
    if args.content_file:
        messages = include_file(messages, args)
    
    command_map = setup_command_shortcuts(plugins)
    print_available_commands(command_map)
    
    while True:
        cmd = input(f'cmd> ')
        messages = command_map[cmd](messages, args)

if __name__ == "__main__":
    main()
