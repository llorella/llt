import os
import sys

sys.path.append(os.path.expanduser('~/message-history-tree'))
from message import Message

from ast import Assert
from typing import List
import json

def save_message_history(root_message: Message, folder: str) -> None:
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = input("Enter filename: ") + ".json"
    path = os.path.join(folder, filename)
    with open(path, 'w') as outfile:
        json.dump(root_message.expand_iter(), outfile, indent=4)
    print(f"Message tree saved to {filename}")
    
def load_message_history(filename: str, folder: str) -> Message:
    path = os.path.join(folder, filename)
    with open(path, 'r') as infile:
        message_dicts = json.load(infile)
    root_message = Message(message_dicts[0]['role'], message_dicts[0]['content'], None)
    current_message = root_message
    for message_dict in message_dicts[1:]:
        current_message = Message(message_dict['role'], message_dict['content'], current_message)
    return current_message

def evaluate_message(model: str, message: Message) -> None:
    pass

def run_thread(model: str, description: str, filename: str, prompts: List[str], folder: str) -> None:
    print(f"Description: {description}")
    if filename:
        current_message = load_message_history(filename, folder)
    else:
        current_message = Message('system', description)
    
    n = len(prompts)
    idx = 0
    while True: 
        
        if (idx == n): 
            try:
                while True:
                    user_input = input("Enter prompt: ")
                    print("You entered:", user_input)
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt detected. Exiting...")
                save_message_history(current_message, folder)
                break
        elif (idx < n): 
            user_input = prompts[idx]
            idx+=1
        
    
        user_message = Message('user', user_input, current_message)
        print(f"{user_message.role}: {user_message.content}")
    
        current_message = user_message.prompt(model)
        print(f"{current_message.role}: {current_message.content}")

        print(f"Prompt tokens: {user_message.tokens}")
        print(f"Completion tokens: {current_message.tokens}")  
        print(f"Chat history token count: {current_message.expand_rec()}")
        
