from openai import OpenAI
import os
import json
from typing import List, Dict

client = OpenAI()

def get_completion(messages: List[Dict[str, str]], args={'model' : 'gpt-4', 'temperature' : 1}) -> Dict:
    completion = client.chat.completions.create(
        messages= messages,
        model=args['model'],
        temperature=args['temperature'])
    return completion.choices[0].message
     
""" def get_embeddings(texts: list[str]) -> list[dict]:
    embeddings = openai.Embedding.create(
        model = "text-embedding-ada-002",
        queries = texts
    )
    return embeddings
 """