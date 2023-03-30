import os
import sys

sys.path.append(os.path.expanduser('~/message-history-tree'))
from message import Message, save_message_history, load_message_history

from ast import Assert
from typing import List
import json


def run_thread(model: str, filename: str, folder: str, prompts: List[str]) -> None:
    if filename:
        root_message = load_message_history(filename, folder)
    else:
        root_message = None
    
    #system denotes new instructions to assistant for handling 
    current_message = Message('system', prompts[0], root_message)
    
    
    n = len(prompts)
    idx = 1
    while True: 
        
        if (idx >= n): 
            try:
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
        
