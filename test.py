import sys
import argparse
import json

from api import get_config
from main import run_conversation

def merge_args_and_config(args, config):
    if args.history:
        config['io']['history_directory'] = args.history
    if args.file:
        config['io']['input_file'] = args.file
    if args.prompts:
        config['conversation']['prompts'] = args.prompts
    if args.temperature is not None:
        config['api']['options'] = args.temperature

    return config

def parse_arguments():
    """
    Parse command-line arguments and return the parsed arguments object.
    """
    parser = argparse.ArgumentParser(description="Chatbot using OpenAI's GPT model.")
    parser.add_argument('-c', '--config', help="Specify a custom configuration file.")
    parser.add_argument('-d', '--history', help="Set directory to look for save and load files.")
    parser.add_argument('-f', '--file', help="Load a JSON file containing the history of previous runs.")
    parser.add_argument('-p', '--prompts', type=str, nargs='*', help="Provide a list of preset prompts.")
    parser.add_argument('-t', '--temperature', type=float, help="Set the temperature for generating responses.")
    return parser.parse_args()

if __name__ == "__main__":
    print("Welcome to chat-cli, a highly configurable GPT chat client.")
    print("Type 'x' to exit, 's' to save the conversation, or 'h' for more options.")

    args = parse_arguments()
    config = get_config(args.config)
    config = merge_args_and_config(args, config)
    
    run_conversation(config)

