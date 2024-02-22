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
    

models = ['gpt-4', 'gpt-4-vision-preview', 'gpt-4-1106-preview']

def parse_arguments():
    parser = argparse.ArgumentParser(description="Message processing tool")
    parser.add_argument('--context_file', '-c', type=str, help="Specify file name for message history context.", default="out.ll")
    parser.add_argument('--content_input', '-f', type=str, help="Submit optional prompt.", default="")
    parser.add_argument('--exec_dir', '-e', type=str, help="Specify root directory.", default="exec")
    parser.add_argument('--message_dir', '-d', type=str, help="Specify message directory.", default="msg")

    # ll is language log. list of language messages over time period t. ll/t
    parser.add_argument('--role', '-r', type=str, help="Specify role.", default="user")
    parser.add_argument('--model', '-m', type=str, help="Specify model. ".join(model for model in models), default=models[0])
    parser.add_argument('--temperature', '-t', type=float, help="Specify temperature.", default=0.9)

    #use function for accepting dict of values and exposing keys for value change.
    return parser.parse_args()


def main():
    Colors.print_header()
    args = parse_arguments()
    llt_path = os.environ.get('LLT_PATH')

    args.message_dir = os.path.join(llt_path, args.message_dir)
    args.exec_dir = os.path.join(llt_path, args.exec_dir)

    if (not os.path.isdir(llt_path)):
        os.makedirs(args.message_dir)
        os.makedirs(args.exec_dir)
    
    user = os.environ.get('USER')
    greeting = f"Hello {user}! You are using model {args.model}. Type 'help' for available commands."
    print(f"{greeting}\n")

    messages: List[Dict[str, any]] = []
    if args.context_file:
        messages = load_message(messages, args)
    if args.content_input:
        #from message import Message
        messages.append({"role" : "user", "content": args.content_input})


    command_map = setup_command_shortcuts(plugins)
    print_available_commands(command_map)

    while True:
        cmd = input(f'llt> ')
        messages = command_map[cmd](messages, args)

if __name__ == "__main__":
    main()
