import os
import json
import datetime
import argcomplete
import argparse
from typing import List, Dict

from message import load_message, write_message, view_message, new_message, prompt_message, remove_message, detach_message, append_message, x_message
from editor import edit_message, include_file, attach_image, previous_message_content_edit
from utils import Colors, quit_program, count_tokens
from api import api_config, full_model_choices

plugins = {
    'load': load_message,
    'write': write_message,
    'view': view_message,
    'new': new_message,
    'complete': prompt_message,
    'edit': edit_message,
    'file': include_file,
    'quit': quit_program,
    'image': attach_image,
    'remove': remove_message,
    'detach': detach_message,
    'append': append_message,
    'xcut': x_message
}

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="llt, the little language terminal")

    def get_ll_files(prefix: str, parsed_args: argparse.Namespace, **kwargs) -> List[str]:
        ll_dir = parsed_args.ll_dir if parsed_args.ll_dir else os.path.join(os.getenv('LLT_PATH'), api_config['ll_dir'])
        return [f for f in os.listdir(ll_dir) if f.startswith(prefix)]

    parser.add_argument('--ll_file', '-l', type=str, help="Language log file. List of natural language messages stored as JSON.", default="").completer = get_ll_files
    parser.add_argument('--file_include', '-f', type=str, help="Read content from a file and include it in the ll.", default="")
    parser.add_argument('--image_path', type=str, default="")

    parser.add_argument('--prompt', '-p', type=str, help="Prompt string.", default="")
    parser.add_argument('--role', '-r', type=str, help="Specify role.", default="user")

    parser.add_argument('--model', '-m', type=str, help="Specify model.", default="gpt-4-0125-preview", choices=full_model_choices)
    parser.add_argument('--temperature', '-t', type=float, help="Specify temperature.", default=0.9)
    
    parser.add_argument('--max_tokens', type=int, help="Maximum number of tokens to generate.", default=4096)
    parser.add_argument('--logprobs', type=int, help="Include log probabilities in the output, up to the specified number of tokens.", default=0)

    parser.add_argument('--cmd_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['cmd_dir']))
    parser.add_argument('--exec_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['exec_dir']))
    parser.add_argument('--ll_dir', type=str, default=os.path.join(os.getenv('LLT_PATH'), api_config['ll_dir']))

    parser.add_argument('--non_interactive', '-n', action='store_true', help="Run in non-interactive mode.")

    argcomplete.autocomplete(parser)
    return parser.parse_args()

def init_directories(args: argparse.Namespace) -> None:
    for directory in [args.ll_dir, args.exec_dir, args.cmd_dir]:
        os.makedirs(directory, exist_ok=True)

def log_command(command: str, message_before: Dict, message_after: Dict, args: argparse.Namespace) -> None:
    tokens_before = count_tokens(message_before, args.model) if message_before else 0
    tokens_after = count_tokens(message_after, args.model) if message_after else 0
    token_delta = tokens_after - tokens_before
    log_path = os.path.join(args.cmd_dir, os.path.splitext(args.ll_file)[0] + ".log")
    with open(log_path, 'a') as logfile:
        logfile.write(f"COMMAND_START\n")
        logfile.write(f"timestamp: {datetime.datetime.now().isoformat()}\n")
        logfile.write(f"before_command: {json.dumps(message_before, indent=2)}\n")  
        logfile.write(f"model: {args.model}\n")  
        logfile.write(f"command: {command}\n")
        logfile.write(f"after_command: {json.dumps(message_after, indent=2)}\n")
        logfile.write(f"tokens_before: {tokens_before}\n")
        logfile.write(f"tokens_after: {tokens_after}\n")
        logfile.write(f"token_delta: {token_delta}\n")
        logfile.write(f"COMMAND_END\n\n")

def help_message(messages: List[Dict], args: argparse.Namespace) -> List[Dict]:
    print("Available commands:")
    for command, func in plugins.items():
        print(f"  {command}: {func}")
    return messages

def main() -> None:
    args = parse_arguments()
    init_directories(args)

    messages = list()
    if args.ll_file:
        messages = load_message(messages, args)
    if args.file_include:
        messages = include_file(messages, args)
    if args.prompt:
        messages.append({'role': 'user', 'content': args.prompt})
    if args.non_interactive:
        messages = prompt_message(messages, args)
        quit_program(messages, args)
    
    Colors.print_header()
    
    greeting = f"Hello {os.getenv('USER')}! You are using model {args.model}. Type 'help' for available commands."
    print(f"{greeting}\n")

    command_map = {**plugins, **{command[0]: func for command, func in plugins.items() if command[0] not in plugins}, 'help': help_message}

    test_command = "prev_edit"
    command_map[test_command] = previous_message_content_edit
    command_map[test_command[0]] = previous_message_content_edit

    while True:
        try:
            cmd = input('llt> ')
            if cmd in command_map:
                message_before = messages[-1] if messages else {}
                messages = command_map[cmd](messages, args)
                log_command(cmd, message_before, messages[-1] if messages else {}, args)
            else:
                print("Unknown command.")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()