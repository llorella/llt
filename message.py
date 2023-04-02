from typing import Optional, Dict, List
from api import get_completion

class Message:
    def __init__(self, role: str, content: str, prev=None, tokens=0) -> None:
        self.role = role
        self.content = content
        self.prev = prev
        self.tokens = tokens
        
    def prompt(self, model: str) -> 'Message':
        completion = get_completion(model, self.expand_iter())
        self.tokens = completion.prompt_tokens
        completion_message = Message(completion.role, completion.content, self, completion.completion_tokens)
        return completion_message   
        
    def expand_rec(self) -> int:
        if self.prev == None: 
            return self.tokens 
        else: 
            return self.tokens + self.prev.expand_rec()
    
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
        return "role: " + self.role + ", content: " + self.content


