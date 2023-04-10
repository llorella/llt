from typing import Optional, Dict, List
from enum import Enum
from pydantic import BaseModel
from api import get_completion
import json
    

class Message:
    def __init__(self, role: str, content: str, prev=None, tokens=0, options=None) -> None:
        self.role = role
        self.content = content
        self.prev = prev
        self.next = None
        self.tokens = tokens
        self.options = options
        
        if prev is not None:
            prev.next = self
        
    def prompt(self, model: str) -> 'Message':
        completion = get_completion(model, self.get_message_history(), self.options)
        self.tokens = completion.prompt_tokens
        completion_message = Message(completion.role, completion.content, self, completion.completion_tokens, self.options)
        return completion_message   
    
    def get_message_history(self) -> List[Dict[str, str]]:
        message_dicts = []
        current_message = self
        while current_message is not None:
            message_dicts.append(current_message.to_dict())
            current_message = current_message.prev
        return list(reversed(message_dicts))
   
    def to_dict(self) -> dict: 
        return { 
            'role' : self.role, 
            'content' : self.content 
            }
        
    def view_with_indexes(self) -> None:
        current_message = self.get_root()
        index = 0

        while current_message is not None:
            print(f"Index: {index}")
            print(f"Role: {current_message.role}")
            print(f"Content: {current_message.content}")
            print()

            current_message = current_message.next
            index += 1
        
    def apply_recursive(self, func, depth: Optional[int] = None) -> None:
        if depth is not None and depth <= 0:
            return

        func(self)

        if self.prev is not None:
            self.prev.apply_recursive(func, depth - 1 if depth is not None else None)
    
    def view(self, depth: Optional[int] = None) -> None:
        def print_message(message: 'Message'):
            print(f"role: {message.role}\r\ncontent: {message.content}")

        self.apply_recursive(print_message, depth)

    def filter_by_role(self, target_role: str, depth: Optional[int] = None) -> List['Message']:
        matching_messages = []

        def match_role(message: 'Message'):
            if message.role == target_role:
                matching_messages.append(message)

        self.apply_recursive(match_role, depth)

        return matching_messages
    
    def filter_by_content(self, target_content: str, depth: Optional[int] = 1) -> List['Message']:
        matching_messages = []

        def match_content(message: 'Message'):
            if message.content.contains(target_content):
                matching_messages.append(message)

        self.apply_recursive(match_content, depth)

        return matching_messages
    
    def get_root(self) -> 'Message':
        current_message = self
        while current_message.prev is not None:
            current_message = current_message.prev
        return current_message
    
    def save(self, path: str) -> None:
        if not path.endswith('.json'):
            path += '.json'
        with open(path, 'w') as outfile:
            json.dump(self.get_message_history(), outfile, indent=4)
        print(f"Message history saved to {path}")
    
    @classmethod
    def load(cls, path: str) -> 'Message':
        with open(path, 'r') as infile:
            message_dicts = json.load(infile)

        current_message = None
        for message_dict in message_dicts:
            current_message = cls(message_dict['role'], message_dict['content'], current_message)

        return current_message
