#!/usr/bin/python3

import os
import argparse
import importlib.util
from typing import Dict, Callable
import traceback
import argcomplete

from utils import Colors, llt_input
from plugins import plugins
from logger import llt_logger

def load_plugins(plugin_dir: str) -> None:
    """Dynamically load llt plugins from scripts in the specified directory."""
    Colors.print_bold(f"Loading plugins from directory: {plugin_dir}", Colors.BLUE)
    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and not filename.startswith("__"):
            file_path = os.path.join(plugin_dir, filename)
            module_name = filename[:-3]
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            try:
                module = importlib.util.module_from_spec(spec)
                if module:
                    spec.loader.exec_module(module)
            except ImportError as e:
                llt_logger.log_error(f"Failed to import {module_name}", {"error": str(e)})

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments with dynamic plugin flags."""
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    parser.add_argument('--load', '--ll', '-l', type=str, help="Conversation history file. JSON formatted list of natural language messages.", default="")
    parser.add_argument('-f', '--file', type=str, help="Source files to include in the current session.", default="")
    parser.add_argument('-p', '--prompt', type=str, help="Prompt string.", default="")
    parser.add_argument('-r', '--role', type=str, help="Specify role.", default="user")
    parser.add_argument('-m', '--model', type=str, help="Specify model.", default="gpt-4o-mini")
    parser.add_argument('-t', '--temperature', type=float, help="Specify temperature.", default=0.9)
    parser.add_argument('--max_tokens', type=int, help="Maximum number of tokens to generate.", default=4096)
    parser.add_argument('--logprobs', type=int, help="Include log probabilities in the output.", default=0)
    parser.add_argument('--top_p', type=float, help="Sample from top P tokens.", default=1.0)
    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'cmd'))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'exec'))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'll/'))
    parser.add_argument('-n', '--non_interactive', '--quit', action='store_true', help="Run in non-interactive mode.")
    


    # Plugin flags
    parser.add_argument('-c', '--complete', action='store_true', help="Complete the last message.")
    parser.add_argument('--write', type=str, help="Write conversation to file (for non-interactive mode).")

    parser.add_argument('--detach', action='store_true', help="Pop last message from given ll.")
    parser.add_argument('--fold', action='store_true', help="Fold consecutive messages from the same role into a single message.")
    parser.add_argument('--execute', action='store_true', help="Execute the last message")
    parser.add_argument('--view', action='store_true', help="Print the last message.")
    parser.add_argument('--email', action='store_true', help="Send an email with the last message.")
    parser.add_argument('--url', type=str, help="The url to fetch.", default=None)
    parser.add_argument('--tags', type=str, help="Tag group or comma-separated list of HTML tags to fetch.", default='content' )

    parser.add_argument('--xml_wrap', '--xml', type=str, help="The xml tag to wrap in.", default=None)
    
    parser.add_argument('--embeddings', type=str, help="The path to the embeddings file.", default="plugins/embeddings.csv")    

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    return args

def init_directories(args: argparse.Namespace) -> None:
    """Initialize necessary directories."""
    if args.exec_dir == ".":
        args.exec_dir = os.path.join(os.getcwd())
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)

def llt_shell_log(cmd: str) -> None:
    """Log shell commands to a log file."""
    file_path = os.path.join(os.getenv("LLT_PATH", ""), "llt_shell.log")
    try:
        with open(file_path, "a") as logfile:
            logfile.write(f"llt> {cmd}\n")

    except Exception as e:
        Colors.print_colored(f"Failed to log shell command '{cmd}': {e}", Colors.RED)


n_abbv = lambda s, n=1: s[:n].lower()


def init_cmd_map() -> Dict[str, Callable]:
    """Initialize a command map with plugin commands and their abbreviations."""
    command_map = {}
    plugin_keys = ", ".join(plugins.keys())
    Colors.print_colored(f"Available plugins: {plugin_keys}", Colors.LIGHT_GREEN)
    for cmd, function in plugins.items():
        if cmd not in command_map:
            command_map[cmd] = function
        if n_abbv(cmd) not in command_map:
            command_map[n_abbv(cmd)] = function
        elif len(cmd) > 2 and n_abbv(cmd, 2) not in command_map:
            command_map[n_abbv(cmd, 2)] = function
        seps = ["-", "_"]
        for sep in seps:
            split_cmd = cmd.split(sep)
            if split_cmd:
                command_map[split_cmd[0]] = function
    return command_map


def user_greeting(username: str, args: argparse.Namespace) -> str:
    """Generate a greeting message for the user."""
    load_file = getattr(args, "load", "None")
    greeting = (
        f"Hello {username}! Using ll file {load_file}, "
        f"with model {args.model} at temperature {args.temperature}. "
        f"Type 'help' for commands."
    )
    return greeting


def display_greeting(username: str, args: argparse.Namespace) -> None:
    """Display the user greeting in a stylized format."""
    greeting_text = user_greeting(username, args)
    header = (
        f"{Colors.BOLD}{Colors.WHITE}{'='*len(greeting_text)}\n"
        f"{greeting_text}\n"
        f"{'='*len(greeting_text)}{Colors.RESET}"
    )
    print(header)


def llt() -> None:
    """Main function to run the llt shell."""
    args = parse_arguments()
    init_directories(args)
    messages = []

    cmds = init_cmd_map()
    startup_cmds = ['load', 'file', 'execute', 'xml', 'url', 'prompt', 'fold', 'complete', 'write', 'quit']
    for cmd in startup_cmds:
        if getattr(args, cmd, None):
            messages = cmds[cmd](messages, args, index=-1)

    Colors.print_header()
    
    llt_logger.log_info("llt interactive session started", {key: val for key, val in vars(args).items() if key not in startup_cmds})
    
    print(user_greeting(os.getenv('USER', 'User'), args))

    while True:
        try:
            (cmd, index) = llt_input(list(cmds.keys()))
            print(cmd, index)
            if cmd in cmds:
                messages_before = messages.copy()
                messages = cmds[cmd](messages, args, index)
                llt_logger.log_command(cmd, messages_before, messages, args)
            else:
                messages.append({'role': args.role, 'content': cmd})
                llt_logger.log_info("User input added", {"role": args.role, "content_length": len(cmd)})
            llt_shell_log(cmd)
        except KeyboardInterrupt:
            llt_logger.log_info("Command interrupted")
            print("\nCommand interrupted.")
        except Exception as e:
            llt_logger.log_error(str(e), {"traceback": traceback.format_exc()})
            print(f"An error occurred: {e}\n{traceback.format_exc()}")

if __name__ == "__main__":
    plugin_dir = os.path.join(os.getenv("LLT_DIR", ""), "plugins")
    load_plugins(plugin_dir)
    llt()
