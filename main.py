import os
import sys

from message import Message
from plugins import plugins
from typing import Dict
import enum

import re
import subprocess
   
def run_conversation(config: Dict) -> None:
    model = config['api']['model']
    history_directory = config['io']['history_directory']
    prompts = config['conversation']['prompts']
        
    system_indexes = config['conversation']['system']
    model_options = config['api']['options']
    roles = config['conversation']['roles']
    
    current_message = Message.load(os.path.join(history_directory, config['io']['input_file'])) if config['io']['input_file'] else None
    
    test_plugins = plugins(current_message, config)
    test_plugins_abbrev = {key[0]: key for key in test_plugins.keys()}
    user_role = roles[1]
    prompt_index, num_prompts = 0, len(prompts) - 1
    while True:
        if prompt_index < num_prompts:
            user_input = prompts[prompt_index]
            user_role = 'system' if prompt_index in system_indexes else 'user'
            prompt_index += 1
        else:
            user_input = input(f"Enter prompt or user options (enter `h` to view all options): ")
            if user_input in test_plugins:
                run_plugin = test_plugins[user_input]()
                current_message = run_plugin if run_plugin else current_message
                continue
            elif user_input in roles:
                user_role = user_input
                print(f"Role set to {user_role}")
                continue
            elif user_input in model_options:
                option = float(input(f"{user_input}: {model_options[user_input]} \r\nPress enter to continue or enter new {user_input}: "))
                if option: model_options[user_input] = option
                continue
        
        user_message = Message(user_role, user_input, current_message, 0, model_options)
        user_message.view(1)
        
        current_message = user_message.prompt(model)
        current_message.view(1)
        

