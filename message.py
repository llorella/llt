import os
import json

from typing import Optional, TypedDict, Dict, List, Type, Tuple

from api import get_completion
from utils import content_input, file_input, colors

class Message(TypedDict):
    role: str
    content: any

def load_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    args.ll_file = args.ll_file if args.non_interactive else file_input(args.ll_file, args.conversation_dir)
    with open(os.path.join(args.conversation_dir, args.ll_file), 'r') as file:
        msgs = json.load(file)
    for msg in msgs:
        messages.append(msg)
    return messages

def write_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    print(f"Context file: {args.ll_file}")
    args.ll_file = file_input(args.ll_file, args.conversation_dir) or args.ll_file
    with open(os.path.join(args.conversation_dir, args.ll_file), 'w') as file:
        json.dump(messages, file, indent=4) 
    return messages

def new_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    content = args.prompt if args.prompt else content_input()
    args.prompt = ""
    message = Message(role=args.role , content=content)
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

def review_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
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
    return messages



