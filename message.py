import os
import json
from typing import Optional, Dict, List
from utils import content_input, path_input, colors, get_valid_index, list_input

class Message(Dict):
    role: str
    content: any

def load(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    ll_path = path_input(args.load, args.ll_dir) if not args.non_interactive\
        else os.path.join(args.ll_dir, args.load)
    if os.path.isdir(ll_path): ll_path = os.path.join(ll_path, "default.ll")
    if not os.path.exists(ll_path):
        os.makedirs(os.path.dirname(ll_path), exist_ok=True)
        return messages
    with open(ll_path, 'r') as file:
        ll = json.load(file)
        idx = get_valid_index(messages, "load from", 0)
        if idx == -1: messages.extend(ll)
        elif not idx: messages = ll
        args.load = ll_path
    return messages

def write(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    ll_path = path_input(args.load, args.ll_dir) if not args.non_interactive else os.path.join(args.ll_dir, args.load)
    os.makedirs(os.path.dirname(ll_path), exist_ok=True)
    with open(ll_path, 'w') as file:
        json.dump(messages, file, indent=2)
    return messages

def prompt(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    message = Message(role=args.role, content=args.prompt)
    messages.append(message)
    return messages

def remove(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "remove", index)
    messages.pop(message_index)
    return messages

def detach(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "detach", index)  
    return [messages.pop(message_index)]

def fold(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    messages[-2]['content'] += "\n" + messages[-1]['content']
    messages.pop()
    return messages

def insert(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "insert", index)
    messages.insert(message_index, Message(role=args.role, content=args.prompt))
    return messages

def content(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    from utils import content_input
    index = get_valid_index(messages, "modify content of", index)
    messages[index]['content'] = content_input()
    return messages

def role(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    """ if not messages: 
        # on startup, 
        # add string descriptions
        messages.append(Message(role=args.role, content=args.prompt))
        return messages """
    index = get_valid_index(messages, "modify role of", index)
    messages[index]['role'] = list_input(["user", "assistant", "system", "tool"], "Select role")
    return messages

def view(messages: List[Message], args: Optional[Dict] = None, index: int = 0) -> List[Message]:
    if not messages: return messages
    def view_helper(message: Message, idx: int) -> str:
        role, content = message['role'], message['content']
        print_content = ""
        if isinstance(content, list): 
            for item in content:
                if item['type'] == 'text': 
                    print_content += item['text'] + "\n"
                elif item['type'] == 'image_url': 
                    print_content += f"Image path: {item['image_url']['url']}"
        else: 
            print_content = content
        color = colors.get(role, colors['reset'])
        print(f"{color}[{role.capitalize()}]{colors['reset']}")
        #for line in content.split('\\n'): print(line)
        print(print_content)
        print(f"{color}[/{role.capitalize()}]{colors['reset']}")
        print(f"\nMessage {idx} of {len(messages)}")
        
    for i in range(0, len(messages)): view_helper(messages[i], i+1)
    print(f"\nTotal messages shown: {len(messages)}")
    return messages

def cut(messages: List[str], args: Optional[Dict] = None) -> List[str]:
    if not messages: return messages
    try:
        values = input("Enter start and optional end index separated by comma (e.g., 2,5): ").split(',')
        start = max(0, int(values[0]) - 1)
        end = int(values[1]) if len(values) > 1 else start + 1
    except (ValueError, IndexError):
        print("Invalid input. Please enter numbers in the correct format.")
        return messages
    if start >= len(messages) or end > len(messages) or start >= end:
        print("Invalid range. Make sure start is less than end and within the message list.")
        return messages
    if input(f"Cutting messages from position {start + 1} to {end}. Proceed? (y for yes, any other key to cancel): ").strip().lower() != 'y':
        return messages
    return messages[start:end]