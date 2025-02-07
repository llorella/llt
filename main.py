#!/usr/bin/env python3
# main.py

import os
import argparse
import traceback

from logger import llt_logger
from utils import Colors, llt_input
from plugins import (
    load_plugins, 
    add_plugin_arguments,
    init_cmd_map,
    schedule_startup_commands,
    ScheduledCommand
)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    # Common arguments
    parser.add_argument('--role', '-r', type=str, help="Specify role (user, system, etc.)", default="user")
    parser.add_argument('--model', '-m', type=str, help="Which LLM model to use", default="deepseek-chat")
    parser.add_argument('--temperature', '-t', type=float, help="Sampling temperature", default=0.9)
    parser.add_argument('--max_tokens', type=int, help="Max tokens to generate", default=8192)
    parser.add_argument('--logprobs', type=int, help="Include logprobs in completion", default=0)
    parser.add_argument('--top_p', type=float, help="Top-p sampling", default=1.0)

    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'cmd'))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'exec'))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH', ''), 'll/'))

    parser.add_argument('--tools', action='store_true', help="Enable tool usage calls.")
    parser.add_argument('--non_interactive', '-n', action='store_true', 
                        help="Run in non-interactive mode.")
    
    return parser


def init_directories(args: argparse.Namespace) -> None:
    if args.exec_dir == ".":
        args.exec_dir = os.path.join(os.getcwd())
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)


def user_greeting(username: str, args: argparse.Namespace) -> str:
    load_file = getattr(args, "load")
    return (
        f"Hello {username}! ll {load_file} is loaded "
        f"with model {args.model} at temperature {args.temperature}. "
        f"Type 'help' for commands."
    )


def display_greeting(username: str, args: argparse.Namespace) -> None:
    greeting_text = user_greeting(username, args)
    header = (
        f"{Colors.BOLD}{Colors.WHITE}{'='*len(greeting_text)}\n"
        f"{greeting_text}\n"
        f"{'='*len(greeting_text)}{Colors.RESET}"
    )
    print(header)


def llt_shell_log(cmd: str) -> None:
    """Log shell commands to a log file."""
    llt_path = os.getenv("LLT_PATH", "")
    if not llt_path:
        return
    file_path = os.path.join(llt_path, "llt_shell.log")
    try:
        with open(file_path, "a") as logfile:
            logfile.write(f"llt> {cmd}\n")
    except Exception as e:
        Colors.print_colored(f"Failed to log shell command '{cmd}': {e}", Colors.RED)


def llt() -> None:
    plugin_dir = os.path.join(os.getenv("LLT_DIR"), "plugins")
    load_plugins(plugin_dir)
    
    # add plugin arguments to parser
    parser = parse_arguments()
    add_plugin_arguments(parser)
    args = parser.parse_args()
    
    init_directories(args)
    messages = []

    cmd_map = init_cmd_map()

    # Initialize command queue with startup commands received from parser
    command_queue = schedule_startup_commands(args)

    Colors.print_header()
    print(user_greeting(os.getenv('USER', 'User'), args))
    while True:
        try:
            # Get next command, either from queue or interactive input
            if command_queue:
                cmd = command_queue.popleft()
                cmd_name, index = cmd.name, cmd.index
                print(f"Executing queued command: {cmd_name} (index: {index})")
            elif args.non_interactive:
                print("Non-interactive mode complete, exiting...")
                break
            else:
                print("\nWaiting for command input...")
                cmd_name, index = llt_input(list(cmd_map.keys()))
                print(f"Received command: {cmd_name} (index: {index})")

            if cmd_name in cmd_map:
                print(f"\nExecuting command: {cmd_name}")
                messages_before = messages.copy()
                messages = cmd_map[cmd_name](messages, args, index)

                # if the last message is a llt message, add it to the command queue
                if messages and messages[-1]["role"] == "llt":
                    print(f"LLT role message detected: {messages[-1]['content']}")
                    if not args.non_interactive:
                        if input("Add this LLT command to queue? (y/N): ").lower() == 'y':
                            command_queue.append(ScheduledCommand(messages[-1]["content"], index))
                            print("Command added to queue")
                        else:
                            print("Command skipped")
                    else:
                        command_queue.append(ScheduledCommand(messages[-1]["content"], index))
                        print("Command automatically queued in non-interactive mode")
                
                llt_logger.log_command(cmd_name, messages_before, messages, args)
                llt_shell_log(cmd_name)
                print(f"Command {cmd_name} completed")
            else:
                # Treat as user message if not a command
                print(f"\nAdding user message with role '{args.role}'")
                messages.append({'role': args.role, 'content': cmd_name})
                print(f"Added message of length {len(cmd_name)}")
                llt_logger.log_info("User input added", {
                    "role": args.role, 
                    "content_length": len(cmd_name)
                })

        except KeyboardInterrupt:
            print("\nReceived keyboard interrupt")
            llt_logger.log_info("Command interrupted")
            print("\nCommand interrupted.")
        except Exception as e:
            print("\nEncountered error:")
            llt_logger.log_error(str(e), {"traceback": traceback.format_exc()})
            print(f"An error occurred: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    llt()
