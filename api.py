import openai
import os
import json
from typing import NamedTuple, Dict

def get_config(user_config_path=None):
    default_config_path = os.path.expanduser('config.json')
    
    with open(default_config_path, 'r') as f:
        config = json.load(f)

    if user_config_path:
        with open(user_config_path, 'r') as f:
            user_config = json.load(f)
        
        for key, value in user_config.items():
            if key in config:
                config[key].update(value)
            else:
                config[key] = value
    return config


class Completion(NamedTuple):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    content: str
    role: str
    finish_reason: str
    index: int  
    
def get_completion(messages: list[dict], knobs: Dict) -> Completion:
    completion = openai.ChatCompletion.create(
        model = knobs['model'],
        messages= messages,
        temperature = knobs['options']['temperature'])
    choice = completion.choices[0]
    message = choice.message
    usage = completion.usage
    return Completion(
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        content=message.content,
        role=message.role,
        finish_reason=choice.finish_reason,
        index=choice.index
    )
     
def get_embeddings(texts: list[str]) -> list[dict]:
    embeddings = openai.Embedding.create(
        model = "text-embedding-ada-002",
        queries = texts
    )
    return embeddings
