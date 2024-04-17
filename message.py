import os
import json
from typing import Optional, TypedDict, Dict, List
from api import get_completion
from utils import content_input, path_input, colors

class Message(TypedDict):
    role: str
    content: any

def load_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    ll_path = path_input(args.ll_file, args.ll_dir) if not args.non_interactive\
        else os.path.join(args.ll_dir, args.ll_file)
    print(f"Loading messages from {os.path.basename(ll_path)}")
    if not os.path.exists(ll_path):
        os.makedirs(os.path.dirname(ll_path), exist_ok=True)
        with open(ll_path, 'w') as file:
            json.dump([], file, indent=2)
    with open(ll_path, 'r') as file:
        messages.extend(json.load(file))
    return messages

def write_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    ll_path = path_input(args.ll_file, args.ll_dir) if not args.non_interactive\
        else os.path.join(args.ll_dir, args.ll_file)
    print(f"Writing messages to {os.path.basename(ll_path)}")
    with open(ll_path, 'w') as file:
        json.dump(messages, file, indent=2)
    args.ll_file, args.ll_dir = os.path.basename(ll_path), os.path.dirname(ll_path)
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

def view_helper(role: str, content: str) -> str:
    color = colors.get(role, colors['reset'])
    try:
        content_lines = content.split('\\n')
        if content_lines:
            print(f"{color}[{role.capitalize()}]{colors['reset']}")
            for line in content_lines:
                print(line)
    except AttributeError:
        print("Can't view image messages yet. On todo list.")
    
def view_message(messages: List[Message], args: Optional[Dict] = None, index: int = None) -> List[Message]:
    count, messages_len = 0, len(messages)
    for i, msg in enumerate(messages):
        if not index or i == index: 
            view_helper(msg['role'], msg['content'])
            count += 1
            print(f"Displaying message {i+1} of {messages_len}.")
        
    print(f"Total messages shown: {count}")
    return messages

def x_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    values = input("Enter values to cut: ").split(',')
    user_input = input(f"Cutting messages {start} to {end}. Proceed? (Any key for yes, Ctrl+C or None to cancel): ")
    if user_input:
        start = int(values[0]) - 1
        end = int(values[1]) if len(values) > 1 else start + 1
        return messages[start:end]
    else:
        return messages