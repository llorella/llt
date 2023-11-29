from typing import Optional, TypedDict, Dict, List, Type
import json
from api import get_completion

class Message(TypedDict):
    role: str
    content: str
    opts: Optional[Dict[str, any]]
    prev: Optional[TypedDict]

def load_message(messages: List[Message], file_path: str) -> List[TypedDict]:
    with open(file_path, 'r') as file:
        msgs = json.load(file)
    for msg in msgs:
        messages.append(msg)
    return messages

def write_message(messages: List[Message], file_path: str) -> List[TypedDict]:
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


""" from typing import Optional, Dict, List
import json
import os
import api
from pathlib import Path
from pydantic import BaseModel
    
class Message:
    def __init__(self, msg: Optional[Dict[str, any]], prev=None) -> None:
        self.role = msg['role']
        self.content = msg['content']
        self.size = 0
        self.prev = prev
        
    def read(self, file: Optional[Path], offset: int = 0) -> Optional[ None ]:
        with open(file, 'r') as f:
            msg = json.load(f)[offset]
        return msg

    def write(self, file: Optional[str], offset: int = 0) -> Optional[ None ]:
        with open('file', mode='w') as f:
            json.dump(self.unroll(), f)
        
    def load(self, file: Optional[Path], offset: int = 0) -> Optional[ None ]:
        with open(file, 'r') as f:
            msg = json.load(f)[offset]
        return msg

    def complete(self) -> 'Message':
        completion = api.get_completion(self.unroll())
        return Message(completion, self)
        
    def evaluate(self) -> Optional[int]:
        pass

    def unroll(self) -> List[Dict[str, str]]:
        curr, msg_dict = self, []
        while curr is not None:
            msg_dict.append({'role': curr.role, 'content': curr.content})
            curr = curr.prev
        return msg_dict        
        
   
    
     """