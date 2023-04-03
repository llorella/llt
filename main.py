import os
import sys
import json

from message import Message
from typing import List

def save_message_history(root_message: Message, path: str) -> None:
    if not path.endswith('.json'):
        path += '.json'
    with open(path, 'w') as outfile:
        json.dump(root_message.expand_iter(), outfile, indent=4)
    print(f"Message history saved to {path}")
    
def load_message_history(path: str) -> Message:
    with open(path, 'r') as infile:
        message_dicts = json.load(infile)
    root_message = Message(message_dicts[0]['role'], message_dicts[0]['content'], None)
    current_message = root_message
    for message_dict in message_dicts[1:]:
        current_message = Message(message_dict['role'], message_dict['content'], current_message)
    return current_message

def run_conversation(model: str, dir: str, load_file: str, prompts: List[str]) -> None:
    root_message = load_message_history(os.path.join(dir, load_file)) if load_file else None
    current_message = Message('system', prompts[0], root_message)   
    
    (i, n) = (1, len(prompts))
    while True: 
        if (i < n): 
           user_input = prompts[i]
           i+=1
        elif (i >= n): 
            user_input = input("Enter prompt: ")
            if user_input == 's':
                save_file = input("Enter save file: ") or load_file 
                tp = os.path.join(dir, save_file)
                print(f"Saving to {tp}")
                save_message_history(current_message, tp)
                continue
            if user_input == 'x':
                break
            
        user_message = Message('user', user_input, current_message)
        current_message = user_message.prompt(model)
        
        print(f"{current_message.role}: {current_message.content}")
        
