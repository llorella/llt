import os
import sys

from message import Message
from typing import Dict
import enum

import re
import subprocess
   
def extract_code_blocks(completion):
    code_blocks = re.findall(r'```(\w+)?\n(.*?)```', completion, re.DOTALL)
    return code_blocks

def save_code_blocks(code_blocks):
    for idx, (language, code) in enumerate(code_blocks, 1):
        if language:
            file_extension = language.lower()
        else:
            file_extension = 'txt'

        filename = f"code_block_{idx}.{file_extension}"
        with open(filename, 'w') as file:
            file.write(code.strip())
        print(f"Saved code block {idx} as {filename}")
        return filename

def edit_source(filename: str, editor: str = 'vim'):
    try:
        if not os.path.isfile(filename):
            print(f"Error: File '{filename}' does not exist.")
            return
        edit_command = f"{editor} {filename}"
        
        subprocess.run(vim_command, shell=True)
    except Exception as e:
        print(f"Error: {e}")

def source_plugin(msg: Message):
    code_blocks = extract_code_blocks(msg.content)
    filename = save_code_blocks(code_blocks)
    edit_source(filename)
    return "completed source plugin"

def help(config: dict):
    print("User options: ")
    for key, value in config['conversation']['user_options'].items():
        print(f"{key}: {value}")
    print(f"Model options (enter option name to read or change): { [key for key in config['api']['options'].keys()] }")
    print(f"Plugin options (enter option name to run): { [key for key in config['extensions'].keys()] }")
    print(f"Roles (enter role for next message): { config['conversation']['roles'] }")
    return None

def save_message(msg: Message, config: dict):
    save_file = input("Enter save file: ") or config['io']['input_file']
    path = os.path.join(config['io']['history_directory'], save_file)
    print(f"Saving to {path}")
    msg.save(path)
    return msg
    
def load_message(msg: Message, config: dict):
    load_file = input("Enter load filename: ")
    load_file = os.path.join(config['io']['history_directory'], load_file)
    load_message = Message.load(load_file)
    load_message.get_root().prev = msg
    return load_message

def view_messages(msg: Message, config: dict):
    depth = int(input("Enter depth: ")) or 1
    msg.view(depth)
    return msg

def run_conversation(config: Dict) -> None:
    model = config['api']['model']
    history_directory = config['io']['history_directory']
    prompts = config['conversation']['prompts']
        
    system_indexes = config['conversation']['system']
    model_options = config['api']['options']
    roles = config['conversation']['roles']
    
    plugins = {'source' : lambda: source_plugin(current_message)}
    user_option_functions = {
        'x': sys.exit,
        's': lambda: save_message(current_message, config),
        'l': lambda: load_message(current_message, config),
        'v': lambda: view_messages(current_message, config),
        'h': lambda: help(config)
    }
    
    current_message = Message.load(os.path.join(history_directory, config['io']['input_file'])) if config['io']['input_file'] else None
    user_role = roles[1]
    prompt_index, num_prompts = 0, len(prompts) - 1
    while True:
        if prompt_index < num_prompts:
            user_input = prompts[prompt_index]
            user_role = 'system' if prompt_index in system_indexes else 'user'
            prompt_index += 1
        else:
            user_input = input(f"Enter prompt or user options (enter `h` to view all options): ")
            if user_input in user_option_functions:
                user_function = user_option_functions[user_input]()
                current_message = user_function if user_function else current_message
                continue
            elif user_input in roles:
                user_role = user_input
                print(f"Role set to {user_role}")
                continue
            elif user_input in plugins:
                test_plugin = plugins[user_input]()
                continue
            elif user_input in model_options:
                option = float(input(f"{user_input}: {model_options[user_input]} \r\nPress enter to continue or enter new {user_input}: "))
                if option: model_options[user_input] = option
                continue
        
        user_message = Message(user_role, user_input, current_message, 0, model_options)
            
        current_message = user_message.prompt(model)
        current_message.view(1)
        

