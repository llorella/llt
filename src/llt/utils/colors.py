"""
colors.py - Terminal color utilities for LLT

This module provides ANSI color code constants and helper functions for
terminal output formatting.
"""

class Colors:
    """ANSI color code constants and helper functions for terminal output."""
    
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    MAGENTA = '\033[95m'
    WHITE = '\033[97m'

    @staticmethod
    def print_colored(text: str, color: str) -> None:
        """Print text with the specified color."""
        print(f"{color}{text}{Colors.RESET}")

    @staticmethod
    def print_header() -> None:
        """Print the LLT header with formatting."""
        print(f"{Colors.HEADER}Welcome to LLT{Colors.RESET}")
