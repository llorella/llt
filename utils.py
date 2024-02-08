def user_input_role():
    roles = ["user", "system", "assistant"]
    role = input(f"Enter role (default is {roles[0]}): ") or roles[0]
    return role

def user_input_content():
    content = input(f"Enter content: ") 
    return content

def user_input_file():
    file_path = input(f"Enter file path: ") 
    return file_path

import pprint

class Colors:
    YELLOW = '\033[93m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

    def print_colored(text, color):
        print(color + text + Colors.RESET)

    def pretty_print_dict(message: dict):
        formatted_message = pprint.pformat(message, indent=4)
        Colors.print_colored(formatted_message, Colors.WHITE)

    def print_header() -> None:
        Colors.print_colored("***** Welcome to llt, the little language terminal. *****", Colors.WHITE)
        Colors.print_colored("*********************************************************", Colors.YELLOW)

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

def open_file(file_path: str):
    with open(file_path, 'r') as file:
        data = file.read()
    return data