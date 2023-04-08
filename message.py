from typing import Optional, Dict, List
from api import get_completion
import json

class Message:
    def __init__(self, role: str, content: str, prev=None, tokens=0, options=None) -> None:
        self.role = role
        self.content = content
        self.prev = prev
        self.tokens = tokens
        self.options = options
        
    def prompt(self, model: str) -> 'Message':
        completion = get_completion(model, self.expand_iter(), self.options)
        self.tokens = completion.prompt_tokens
        completion_message = Message(completion.role, completion.content, self, completion.completion_tokens)
        return completion_message   
        
    def expand_rec(self) -> int:
        if self.prev == None: 
            return self.tokens 
        else: 
            return self.tokens + self.prev.expand_rec()
        
    def get_root(self) -> 'Message':
        current_message = self
        while current_message.prev is not None:
            current_message = current_message.prev
        return current_message
    
    def expand_iter(self) -> List[Dict[str, str]]:
        message_dicts = []
        current_message = self
        while current_message is not None:
            message_dicts.append(current_message.format())
            current_message = current_message.prev
        return list(reversed(message_dicts))
   
    def format(self) -> dict: 
        message_dict = { 'role' : self.role, 'content' : self.content }
        return message_dict
    
    def __str__(self) -> str:
        return f"role: {self.role}, content: {self.content}"
    
    def save_file(self, path: str) -> None:
        if not path.endswith('.json'):
            path += '.json'
        with open(path, 'w') as outfile:
            json.dump(self.expand_iter(), outfile, indent=4)
        print(f"Message history saved to {path}")
    
    @classmethod
    def load_file(cls, path: str) -> 'Message':
        with open(path, 'r') as infile:
            message_dicts = json.load(infile)

        current_message = None
        for message_dict in message_dicts:
            current_message = cls(message_dict['role'], message_dict['content'], current_message)

        return current_message
