import argparse
from typing import TypedDict, List
import pprint
from plugins import plugins

class Colors:
    YELLOW = '\033[93m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

def print_colored(text, color):
    print(color + text + Colors.RESET)

def pretty_print_dict(message: TypedDict):
    formatted_message = pprint.pformat(message, indent=4)
    print_colored(formatted_message, Colors.WHITE)

def print_header():
    print_colored("***********************************", Colors.YELLOW)
    print_colored("***** WELCOME TO MY CLI TOOL *****", Colors.WHITE)
    print_colored("***********************************", Colors.YELLOW)

def get_user_input(prompt):
    print_colored(f"[CMD QUIZ] {prompt}: ", Colors.YELLOW, end='')
    return input()

def parse_arguments():
    parser = argparse.ArgumentParser(description="Message processing tool")
    parser.add_argument('--file', '-f', type=str, help="Specify file descriptor to read input from.", default=None)
    return parser.parse_args()

def main_loop():
    messages: List[TypedDict] = []
    _plugins = plugins()
    #make plugin
    print('Available commands:', { [(comm[0], comm) for comm in _plugins['commands'].keys()]})     
    while 1:
        comm = input('Enter command: ')
        messages = _plugins['commands'][comm](messages, _plugins['presets']['file'])


def main():
    print_header()
    args = parse_arguments()
    main_loop()



if __name__ == "__main__":
    main()
