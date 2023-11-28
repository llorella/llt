import os
import sys
import argparse

from message import Message
from plugins import plugins

from typing import Dict, List, Optional

class Colors:
    YELLOW = '\033[93m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

def print_colored(text, color):
    print(color + text + Colors.RESET)

def ask_user_input(prompt):
    print_colored(f"[INPUT REQUIRED] {prompt}: ", Colors.YELLOW, end='')
    return input()

def run_message(msg: Message, plugins: Optional[Dict[str, any]]) -> Optional[Message]:
    (presets, commands) = plugins['presets'], plugins['commands']

    while 1: 
        print('Available commands:', { (comm[0], comm) for comm in commands.keys()})     
        comm = ask_user_input('Enter command: ')
        if (comm in commands.keys()):
            msg = commands[comm](msg, presets['file'] if presets['file'] else None)

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', type=str, help="Specify file descriptor to read input from.", default=None)
    parser.add_argument('--role', '-r', type=str, help="Specify role.", default="system")
    return parser.parse_args()

if __name__ == "__main__":
    #tool that interfaces with message ops and user defined plugins
    print("Launching CLI server..")
    args = parse_arguments()
    if (args.file is not None):
        with open(args.file, 'r') as f:
            content = f.read()
    else:
        content = ''
    msg = Message({'role': args.role, 'content': content})
    plugins_dict = plugins()

    run_message(msg, plugins_dict)

