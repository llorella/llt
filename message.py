from typing import Optional, TypedDict, Dict, List, Type
import json
from api import get_completion
from utils import open_file, user_input_role, user_input_content, user_input_file

class Message(TypedDict):
    role: str
    content: any
    opts: Optional[Dict[str, any]]
    prev: Optional[TypedDict]

def load_message(messages: List[Message], args: Optional[Dict]) -> List[TypedDict]:
    file_path=user_input_file() if not args.context_file else args.context_file
    with open(file_path, 'r') as file:
        msgs = json.load(file)
    for msg in msgs:
        messages.append(msg)
    return messages

def write_message(messages: List[Message], args: Optional[Dict]) -> List[TypedDict]:
    file_path=user_input_file() or args.context_file
    with open(file_path, 'w') as file:
        json.dump(messages, file, indent=4) 
    return messages

def new_message(messages: List[Message], args: Optional[Dict]) -> List[TypedDict]:
    content=user_input_content() or open_file(args.content_file)
    role=user_input_role() or args.role
    message = Message(role=role, content=content)
    messages.append(message)
    return messages

def prompt_message(messages: List[Message], args=Optional[Dict]) -> List[TypedDict]:
    completion_msg = get_completion(messages, args)
    messages.append(Message(role=completion_msg['role'], content=completion_msg['content']))
    return messages


def view_message(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
    colors = {
        'system': '\033[34m',    # Blue
        'user': '\033[32m',      # Green
        'assistant': '\033[35m', # Magenta
        'reset': '\033[0m'
    }
    
    for msg in messages:
        role, content = msg['role'], msg['content']
        color = colors.get(role, colors['reset'])  

        content_lines = content.split('\n')
        
        if content_lines:
            # Print role and first line of content with color
            print(f"{color}{role.capitalize()}:{colors['reset']} {content_lines[0]}")

            # Print the remaining lines without role and color
            for line in content_lines[1:]:
                print(line)

    return messages

    def add_image(messages: List[Message], args: Optional[Dict] = None) -> List[Message]:
        image_url = input("Enter image url: ")
        messages.append(Message(role='user', content=image_url))
        return messages


