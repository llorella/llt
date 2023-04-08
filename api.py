import openai
import os
import json
from typing import NamedTuple, Dict

class Completion(NamedTuple):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    content: str
    role: str
    finish_reason: str
    index: int  
    
def get_completion(model: str, messages: list[dict], options: Dict) -> Completion:
    completion = openai.ChatCompletion.create(
        model = model,
        messages= messages,
        temperature = options['temperature'])
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
