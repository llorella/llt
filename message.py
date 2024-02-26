import os
import json

from typing import Optional, TypedDict, Dict, List, Type, Tuple

from api import get_completion
from utils import input_role, content_input, file_input

class Message(TypedDict):
    role: str
    content: any

def load_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    args.context_file = args.context_file if args.non_interactive else file_input(args.context_file)
    with open(os.path.join(args.message_dir, args.context_file), 'r') as file:
        msgs = json.load(file)
    for msg in msgs:
        messages.append(msg)
    return messages

def write_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    print(f"Context file: {args.context_file}")
    args.context_file = file_input(args.context_file) or args.context_file
    with open(os.path.join(args.message_dir, args.context_file), 'w') as file:
        json.dump(messages, file, indent=4) 
    return messages

def new_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    message = Message(role=input_role(args.role) , content=content_input())
    messages.append(message)
    return messages

def prompt_message(messages: List[Message], args=Optional[Dict]) -> List[Message]:
    completion_msg = get_completion(messages, args)
    messages.append(Message(role=completion_msg['role'], content=completion_msg['content']))
    return messages

def remove_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    if messages:
        messages.pop()
        print("Last message removed.")
    else:
        print("No messages to remove.")
    return messages

def review_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    return messages

def view_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    colors = {
        'system': '\033[34m',    # blue
        'user': '\033[32m',      # green
        'assistant': '\033[35m', # magenta
        'reset': '\033[0m'
    }
    
    for msg in messages:
        role, content = msg['role'], msg['content']
        color = colors.get(role, colors['reset'])  

        content_lines = content.split('\n')
        if content_lines:
            print(f"{color}{role.capitalize()}:{colors['reset']} {content_lines[0]}")
            for line in content_lines[1:]:
                print(line)

    return messages

def add_image(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    image_url = input("Enter image url: ")
    messages.append(Message(role='user', content=image_url))
    return messages


