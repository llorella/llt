import argparse
import os
import sys
from message import load_message, write_message, view_message, new_message, prompt_message, remove_message
from editor import edit_message, include_file, attach_image
from utils import Colors, setup_command_shortcuts, print_available_commands

def quit_program(messages, file_path):
    print("Exiting...")
    sys.exit(0)

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
    'remove': remove_message
}

def parse_arguments():
    parser = argparse.ArgumentParser(description="Message processing tool")
    
    available_models = ['gpt-4', 'gpt-4-vision-preview', 'gpt-4-1106-preview']
    parser.add_argument('--context_file', '-c', type=str, 
                        help="Specify file name for message history context.", default="out.ll")
    parser.add_argument('--content_input', '-f', type=str, 
                        help="Submit optional prompt.", default="")
    parser.add_argument('--exec_dir', '-e', type=str, 
                        help="Specify root directory.", default="exec")
    parser.add_argument('--message_dir', '-d', type=str, 
                        help="Specify message directory.", default="msg")
    parser.add_argument('--role', '-r', type=str, 
                        help="Specify role.", default="user")
    parser.add_argument('--model', '-m', type=str, 
                        help="Specify model. Options: " + ", ".join(available_models), default=available_models[0])
    parser.add_argument('--temperature', '-t', type=float, 
                        help="Specify temperature.", default=0.9)
    parser.add_argument('--non_interactive', action='store_true', help="Run in non-interactive mode.")
    
    return parser.parse_args()

def main():
    args = parse_arguments()

    llt_path = os.getenv('LLT_PATH')
    if llt_path:
        args.message_dir = os.path.join(llt_path, args.message_dir)
        args.exec_dir = os.path.join(llt_path, args.exec_dir)
        if not os.path.isdir(args.message_dir):
            os.makedirs(args.message_dir)
        if not os.path.isdir(args.exec_dir):
            os.makedirs(args.exec_dir)

    messages = []
    if args.context_file:
        messages = load_message(messages, args)
    if args.content_input:
        messages.append({"role": args.role, "content": args.content_input})
    if args.non_interactive:
        from api import get_completion
        completion = get_completion(messages, args)
        exit()
    
    Colors.print_header()

    user = os.getenv('USER')
    greeting = f"Hello {user}! You are using model {args.model}. Type 'help' for available commands."
    print(f"{greeting}\n")

    command_map = setup_command_shortcuts(plugins)
    print_available_commands(command_map)

    while True:
        cmd = input('llt> ')
        if cmd in command_map:
            messages = command_map[cmd](messages, args)
        else:
            print("Unknown command.")

if __name__ == "__main__":
    main()

