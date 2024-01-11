from typing import Optional, TypedDict, Dict, List, Type
import json
from api import get_completion

class Message(TypedDict):
    role: str
    content: str
    opts: Optional[Dict[str, any]]
    prev: Optional[TypedDict]

def load_message(messages: List[Message], file_path: str) -> List[TypedDict]:
    file_input = input(file_path + " is your current file. Change? (enter for no, any string for yes): ")
    if file_input:
        file_path = file_input
    with open(file_path, 'r') as file:
        msgs = json.load(file)
    for msg in msgs:
        messages.append(msg)
    return messages

def write_message(messages: List[Message], file_path: str) -> List[TypedDict]:
    file_input = input(file_path + " is your current file. Change? (enter for no, any string for yes): ")
    if file_input:
        file_path = file_input
    with open(file_path, 'w') as file:
        json.dump(messages, file, indent=4) 
    return messages

def new_message(messages: List[TypedDict], file_path: Optional[str]) -> List[TypedDict]:
    message = Message(role='user', content='')
    for field in message.keys():
        user_input = input(f"Enter {field}: ")
        message[field] = message.get(field, '') if not user_input else user_input

    messages.append(message)
    return messages

def prompt_message(messages: List[Message], file_path: Optional[str]) -> List[TypedDict]:
    completion_msg = get_completion(messages)
    messages.append(Message(role=completion_msg.role, content=completion_msg.content))
    return messages

def view_message(messages: List[Message], file_path: Optional[str]) -> List[TypedDict]:
    print(messages)
    return messages
