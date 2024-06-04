import os
import json
from typing import Optional, Dict, List
from api import get_completion
from utils import content_input, path_input, colors, get_valid_index, role_input

class Message(Dict):
    role: str
    content: any

def load_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    ll_path = path_input(args.ll, args.ll_dir) if not args.non_interactive\
        else os.path.join(args.ll_dir, args.ll)
    if not os.path.exists(ll_path):
        os.makedirs(os.path.dirname(ll_path), exist_ok=True)
        return messages
    with open(ll_path, 'r') as file:
        messages.extend(json.load(file))
    return messages

def write_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    ll_path = path_input(args.ll, args.ll_dir) if not args.non_interactive else os.path.join(args.ll_dir, args.ll)
    with open(ll_path, 'w') as file:
        json.dump(messages, file, indent=2)
    return messages

def new_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    if args.__contains__('prompt') and args.prompt:
        content = args.prompt
        args.__delattr__('prompt')
    else:
        content = content_input()
    message = Message(role=args.role, content=content)
    messages.append(message)
    return messages

def remove_message(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "remove", index)
    messages.pop(message_index)
    return messages

def detach_message(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "detach", index)  
    return [messages.pop(message_index)]

def append_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    messages[-2]['content'] += messages[-1]['content']
    messages.pop()
    return messages

def insert_message(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "insert", index)
    messages.insert(message_index, Message(role=args.role, content=args.prompt))
    return messages

def view_message(messages: List[Message], args: Optional[Dict] = None, index: int = 0) -> List[Message]:
    def view_helper(message: Message) -> str:
        role, content = message['role'], message['content']
        if type(content) == list: content = "Image data."
        color = colors.get(role, colors['reset'])
        print(f"{color}[{role.capitalize()}]{colors['reset']}")
        for line in content.split('\\n'): print(line)
        print(f"{color}[/{role.capitalize()}]{colors['reset']}")
    if not messages: return messages
    message_index = 0 # can also set message_index = get_valid_index(messages, "view", index), based on preference
    start, end = 0, len(messages)
    if message_index < 0: start, end = len(messages) + index, len(messages)
    elif message_index > 0: start, end = index, index + 1
    for i in range(start, end): view_helper(messages[i])
    print(f"\nTotal messages shown: {end - start}")
    return messages

def cut_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    values = input("Enter values to cut: ").split(',')
    start = int(values[0]) - 1
    end = int(values[1]) if len(values) > 1 else start + 1
    user_input = input(f"Cutting messages {start} to {end}. Proceed? (Enter any key for yes, empty to cancel): ")
    return messages[start:end] if user_input else messages
    
def change_role(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "change role of", index)
    messages[message_index]['role'] = role_input(messages[message_index]['role'])   
    return messages