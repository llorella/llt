import os
import json
from typing import Optional, TypedDict, Dict, List
from api import get_completion
from utils import content_input, path_input, colors #, user_index_input

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
    if args.__contains__('prompt') and args.prompt:
        content = args.prompt
        args.__delattr__('prompt')
    else:
        content = content_input()
    message = Message(role=args.role, content=content)
    messages.append(message)
    return messages

def prompt_message(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    completion_msg = get_completion(messages, args)
    messages.append(Message(role=completion_msg['role'], content=completion_msg['content']))
    return messages

def remove_message(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    if not messages:
        print("No messages to edit.")
        return messages
    message_index = int(input(f"Enter index of previous message to remove (default is {index}, -2 for last message): ") or index)
    messages.pop(message_index)
    return messages

def detach_message(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    if not messages:
        print("No messages to edit.")
        return messages
    message_index = int(input(f"Enter index of previous message to detach (default is {index}, -2 for last message): ") or index)
    # lambda that handles user index input and formats the command name that needs index value
    # first argument of user input is parsed name from current function 
    #user_input = lambda x: input(f"Enter index of message to PYTHON_CODE_TO_PARSE_MESSAGE_CMD_FIRST_STRING {inspect.currentframe().f_code.co_name} (default is {x}, -2 for last message): ") or x
    return [messages.pop(message_index)]

def append_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    messages[-2]['content'] += messages[-1]['content']
    messages.pop()
    return messages

def view_helper(role: str, content: str) -> str:
    color = colors.get(role, colors['reset'])
    try:
        content_lines = str(content).split('\\n')
        print(f"{color}[{role.capitalize()}]{colors['reset']}")
        if content_lines:
            for line in content_lines:
                print(line)
        print(f"{color}[/{role.capitalize()}]{colors['reset']}")
    except AttributeError:
        print("Can't view image messages yet. On todo list.")
    
def view_message(messages: List[Message], args: Optional[Dict] = None, index: int = None) -> List[Message]:
    count, messages_len = 0, len(messages)
    for i, msg in enumerate(messages):
        if not index or i == index: 
            view_helper(msg['role'], msg['content'])
            count += 1
            print(f"Message {i+1} of {messages_len}.")
        
    print(f"\nTotal messages shown: {count}")
    return messages

def cut_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    values = input("Enter values to cut: ").split(',')
    start = int(values[0]) - 1
    end = int(values[1]) if len(values) > 1 else start + 1
    user_input = input(f"Cutting messages {start} to {end}. Proceed? (Any key for yes, Ctrl+C or None to cancel): ")
    if user_input:
        return messages[start:end]
    else:
        return messages