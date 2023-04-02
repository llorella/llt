from main import run_thread
import sys
import argparse

model = "gpt-3.5-turbo"
folder = "./sandbox/"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--directory', help="Directory for loading and storing JSON history files.")
    parser.add_argument('-f', '--file', help="JSON file containing history of previous runs.")
    parser.add_argument('-p', '--prompts', type=str, help="List of preset prompts.")
    args = parser.parse_args()

    if not ( args.file or args.directory or args.prompts  ):
        raise parser.error("Either --history or --prompts must be provided.")
    else: 
        prompts = args.prompts.split(",") if args.prompts else []
        run_thread(model, args.directory, args.file, prompts)