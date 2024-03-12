import os
import json

from typing import Optional, TypedDict, Dict, List, Type, Tuple

from api import get_completion
from utils import content_input, path_input, colors

class Message(TypedDict):
    role: str
    content: any

def load_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    (ll_file, conversation_dir) = (args.ll_file, args.conversation_dir)
    ll_file = path_input(ll_file, conversation_dir)
    if not ll_file:
        return messages
    args.ll_file = ll_file

    file_path=os.path.join(conversation_dir, ll_file)
    if not os.path.exists(file_path):
        with open(file_path, 'w') as file:
            json.dump(messages, file, indent=4)
    with open(file_path, 'r') as file:
        msgs = json.load(file)
    for msg in msgs:
        messages.append(msg)
    return messages 
   
def write_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    (ll_file, conversation_dir) = (args.ll_file, args.conversation_dir)
    ll_file = path_input(ll_file, conversation_dir) or ll_file
    if not ll_file:
        return messages
    args.ll_file = ll_file

    file_path=os.path.join(conversation_dir, ll_file)
    with open(file_path, 'w') as file:
        json.dump(messages, file, indent=4) 
    return messages

def new_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    message = Message(role=args.role , content=content_input())
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

def back_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    return messages[:-1]

def x_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    values = input("Enter values to cut: ").split(',')
    #can be integers or ranges of signed integers
    try:
        start = int(values[0])
        end = int(values[1]) if len(values) > 1 else start
        return messages[start:end]
    except ValueError:
        return messages[int(values[0]):]
    






