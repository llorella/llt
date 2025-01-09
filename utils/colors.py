import pprint
from typing import Dict

class Colors:
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    MAGENTA = "\033[35m"
    YELLOW = "\033[93m"
    WHITE = "\033[97m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"
    CYAN = "\033[36m"
    LIGHT_BLUE = "\033[94m"
    LIGHT_GREEN = "\033[92m"
    PURPLE = "\033[95m"

    @staticmethod
    def print_colored(text: str, color: str = "") -> None:
        print(f"{color}{text}{Colors.RESET}")

    @staticmethod
    def print_bold(text: str, color: str = "") -> None:
        print(f"{Colors.BOLD}{color}{text}{Colors.RESET}")

    @staticmethod
    def pretty_print_dict(message: Dict) -> None:
        formatted_message = pprint.pformat(message, indent=4)
        Colors.print_colored(formatted_message, Colors.WHITE)

    @staticmethod
    def print_header():
        Colors.print_colored("***** Welcome to llt, the little language terminal *****", Colors.YELLOW) 