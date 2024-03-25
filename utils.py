import os, sys
import pprint
import readline
from typing import Optional, Dict
import json

def quit_program(messages: list, args: dict) -> None:
    print("Exiting...")
    sys.exit(0)

colors = {  
    'system': '\033[34m',    # blue
    'user': '\033[32m',      # green
    'assistant': '\033[35m', # magenta
    'reset': '\033[0m'
}

class Colors:
    YELLOW = '\033[93m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

    @staticmethod
    def print_colored(text, color):
        print(color + text + Colors.RESET)

    @staticmethod
    def pretty_print_dict(message: dict):
        formatted_message = pprint.pformat(message, indent=4)
        Colors.print_colored(formatted_message, Colors.WHITE)

    @staticmethod
    def print_header():
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("***** Welcome to llt, the little language terminal. *****", Colors.WHITE)
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("*********************************************************\n", Colors.YELLOW)

def input_role(role: str) -> str:
    return input(f"Enter role(default is {role}): ") or role

def content_input() -> str:
    return input("Enter content: ")

def directory_completer(dir_path):
    def completer(text, state):
        files = os.listdir(dir_path)
        matches = [file for file in files if file.startswith(text)]
        return matches[state] if state < len(matches) else None
    return completer

def path_completer(text, state):
    line = readline.get_line_buffer().split()
    if '~' in text:
        text = os.path.expanduser('~') + text[1:]
    if os.path.isdir(text) and not text.endswith(os.path.sep):
        return [text + os.path.sep][state]
    return [x for x in os.listdir(os.path.dirname(text)) if x.startswith(os.path.basename(text))][state]
    
def path_input(default_file: str = None, exec_dir: str = None) -> str:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(directory_completer(exec_dir) if dir else path_completer)
    file_path = input(f"Enter file path (default is {default_file}): ")
    print(f"Path: {os.path.expanduser(file_path)}")
    return os.path.expanduser(file_path) if file_path else default_file

def get_file_path(args: Optional[Dict]) -> Optional[str]:
    ll_file, ll_dir = args.ll_file, args.ll_dir
    ll_file = path_input(ll_file, ll_dir)
    if not ll_file:
        return None
    args['ll_file'] = ll_file 

    file_path = os.path.join(ll_dir, ll_file)
    if not os.path.exists(file_path):
        with open(file_path, 'w') as file:
            json.dump([], file, indent=2)  
    return file_path

import tiktoken
def count_tokens(message, model):
    model = "gpt-4" # todo: add support for other models
    encoding = tiktoken.encoding_for_model(model)
    num_tokens = 4 + len(encoding.encode(message['content']))
    return num_tokens