import os
import json
from typing import Optional, TypedDict, Dict, List, Type, Tuple
from api import get_completion
from utils import content_input, path_input, colors

class Message(TypedDict):
    role: str
    content: any

def load_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    ll_path = path_input(args.ll_file, args.ll_dir)
    print(f"Loading messages from {ll_path}")
    if not os.path.exists(ll_path):
        with open(ll_path, 'w') as file:
            json.dump([], file, indent=2)
        return messages
    with open(ll_path, 'r') as file:
        messages.extend(json.load(file))
    return messages

def write_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    ll_path = path_input(args.ll_file, args.ll_dir)
    print(f"Writing messages to {ll_path}")
    with open(ll_path, 'w') as file:
        json.dump(messages, file, indent=2)
    return messages

def new_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    message = Message(role=args.role, content=content_input())
    messages.append(message)
    return messages

def prompt_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
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

def detach_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    return [messages.pop()]

def append_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    messages[-2]['content'] += messages[-1]['content']
    messages.pop()
    return messages
    
def view_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    for msg in messages:
        role, content = msg['role'], msg['content']
        color = colors.get(role, colors['reset'])  
        try:
            content_lines = content.split('\n')
            if content_lines:
                print(f"{color}{role.capitalize()}:{colors['reset']} {content_lines[0]}")
                for line in content_lines[1:]:
                    print(line)
        except AttributeError:
            print("Can't view image messages yet. On todo list.")
    print(len(messages))
    return messages

def x_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    values = input("Enter values to cut: ").split(',')
    #can be integers or ranges of signed integers
    try:
        start = int(values[0])
        end = int(values[1]) if len(values) > 1 else start
        return messages[start:end]
    except ValueError:
        return messages[int(values[0]):]