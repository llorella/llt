import openai
import os
import json
from typing import NamedTuple

openai.api_key = (os.environ.get('OPENAI_API_KEY'))

with open ('config.json', 'r') as f:
    config = json.load(f)
    
model = config['model']
history_directory = config['history_directory']
prompts = config.get('prompts')

class Completion(NamedTuple):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    content: str
    role: str
    finish_reason: str
    index: int  
    
def get_completion(model: str, messages: list[dict]) -> Completion:
    completion = openai.ChatCompletion.create(
        model = model,
        messages= messages,
        max_tokens = 800,
        temperature = 0.9)
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
