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

def setup_command_shortcuts(commands):
    command_map = {}
    for command, func in commands.items():
        command_map[command] = func
        if command[0] not in command_map:
            command_map[command[0]] = func
    return command_map

def print_available_commands(command_map):
    commands_display = ", ".join(
        [f"{full}({short})" if full[0] == short else full for full, short in command_map.items()]
    )
    print(f"Available commands: {commands_display}")


def main():
    print_header()
    args = parse_arguments()
    messages: List[TypedDict] = []
    _plugins = plugins()
    command_map = setup_command_shortcuts(_plugins['commands'])
    print_available_commands(command_map)    
    
    while 1:
        comm = input('Enter command: ')
        messages = command_map[comm](messages, _plugins['presets']['file'])

if __name__ == "__main__":
    main()
