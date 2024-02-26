import os
import pprint

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
        Colors.print_colored("***** Welcome to llt, the little language terminal. *****", Colors.WHITE)
        Colors.print_colored("*********************************************************", Colors.YELLOW)

def input_role(role: str) -> str:
    return input(f"Enter role(default is {role}): ") or role

def content_input() -> str:
    return input("Enter content: ")

def file_input(default_file: str = "empty") -> str:
    file_path = input(f"Enter file path (default is {default_file}): ")
    return os.path.expanduser(file_path) if file_path else default_file

def setup_command_shortcuts(commands: dict) -> dict:
    command_map = {}
    for command, func in commands.items():
        command_map[command] = func
        shortcut = command[0]
        if shortcut not in command_map:
            command_map[shortcut] = func
    return command_map

def print_available_commands(command_map: dict) -> None:
    commands_display = ", ".join(
        [f"{full}({short})" for full, short in command_map.items() if len(full) > 1]
    )
    print(f"Available commands: {commands_display}")