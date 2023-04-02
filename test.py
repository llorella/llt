from main import run_conversation
import sys
import argparse

from api import model, history_directory, prompts

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help="JSON file containing history of previous runs.")
    parser.add_argument('-p', '--prompts', type=str, nargs='*', help="List of preset prompts.")
    args = parser.parse_args()

    input_prompts = args.prompts.split(',') if args.prompts else prompts
    # prompts list must always contain at least one item for the system to start the conversation.
    if not args.file and not input_prompts:
        input_prompts = input("Enter system prompt to continue: ")

    run_conversation(model, history_directory, args.file, input_prompts)
