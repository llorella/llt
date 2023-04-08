import os
import sys

from message import Message
from typing import Dict    

def run_conversation(config: Dict) -> None:
    model = config['api']['model']
    history_directory = config['io']['history_directory']
    prompts = config['conversation']['prompts']
    system_indexes = config['conversation']['system']
    options = config['conversation']['options']
    current_message = Message.load_file(os.path.join(history_directory, config['io']['input_file'])) if config['io']['input_file'] else None

    prompt_index, num_prompts = 0, len(prompts) - 1

    while True:
        if prompt_index < num_prompts:
            user_input = prompts[prompt_index]
            user_role = 'system' if prompt_index in system_indexes else 'user'
            prompt_index += 1
        else:
            user_input = input(f"Enter prompt (x: exit, s: save, option_name in { [key for key in options.keys()] } ): ")

            if user_input == 'x':
                print("Goodbye.")
                return None
            if user_input == 's': 
                save_file = input("Enter save file: ") or config['io']['input_file']
                path = os.path.join(config['io']['history_directory'], save_file)
                print(f"Saving to {path}")
                current_message.save_file(path)
                continue
            if user_input == 'r':
                print("Current message history: ")
                print(current_message.expand_iter())
                continue
            if user_input == 'l':
                load = input("Enter load file path: ")
                load_message = Message.load_file(load)
                load_message.get_root().prev = current_message
                current_message = load_message
                continue
            if user_input in options.keys():
                option = float(input(f"{user_input}: {options[user_input]} \r\nPress enter to continue or enter new {user_input}: "))
                if option: options[user_input] = option
                continue

        user_message = Message('user', user_input, current_message, 0, options)
        current_message = user_message.prompt(model)

        print(f"{current_message.role}: {current_message.content}")
        
