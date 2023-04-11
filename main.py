import os
import sys

from message import Message
from plugins import plugins, pairs, abbv
from typing import Dict
import enum

import re
import subprocess

first_n_letters = lambda x, n: x[:n]
first_n_letters_list = lambda x, n: [ first_n_letters(a, n) for a in x ]
first_letters = lambda x: first_n_letters_list(x, 1)
full_name = lambda x, arr: [ a for a in arr if x==a or x==abbv(a) ][0]

def is_valid_knob(command: str, tunable_dict: dict):
    stripped_command = command.strip()
    command_parts = re.split(r"\s*[.\s]\s*", stripped_command)
    
    if len(command_parts) == 2:
        key, value = command_parts
        if key in tunable_dict.keys() or key in first_letters(tunable_dict.keys()):
            full_key = full_name(key, tunable_dict.keys())
            values = tunable_dict[full_key]
            if type (values) == list:
                if value in values or value in first_letters(values):
                    return full_key, full_name(value, values)
            if type(values) == dict:
                if value in values.keys() or value in first_letters(values.keys()):
                    return full_key, full_name(value, values.keys())
    return None
   
def run_conversation(config: Dict) -> None:
    
    history_directory = config['io']['history_directory']
    context = config['io']['input_file']

    user_role = 'user'
    current_message = Message.load(os.path.join(history_directory, context)) if context is not None else base_message (roles[0])
    
    test_tunable = { 'api' : {'model' : "gpt-3.5-turbo", "options": {"temperature": 1.0, "top_p": 1.0}}, 'conversation': { 'current_role': 'system', 'default_depth' : 1} }
    test_plugins = plugins()
    
    while True:
        print(f"Available plugins: { pairs (test_plugins) }")
        user_input = input(f"Enter prompt or plugin command: ")
        if user_input in test_plugins:
            run_plugin = test_plugins[user_input](current_message, config)
            current_message = run_plugin if run_plugin else current_message
        elif (tune:=is_valid_knob(user_input, test_tunable)) is not None:
            (key, val) = tune
            new_val = input(f"{key}.{val}: {config[key][val]}\r\nEnter new value or return to continue: ")
            if new_val: 
                try:
                    config[key][val] = type(config[key][val])(new_val)
                except ValueError:
                    print(f"Invalid value for {type(config[key][val])} {key}.{val}: {new_val}")
        else:  
            user_message = Message(user_role, user_input, current_message, 0, config['api'])
            user_message.view(1)
            
            current_message = user_message.prompt()
            current_message.view(1)
            

        

