from openai import OpenAI
import os
import json
from typing import List, Dict
import time

client = OpenAI()

def get_completion(messages: List[Dict[str, str]], args={}) -> Dict:
    start_time = time.time()
    completion = client.chat.completions.create(
        messages= messages,
        model=args.model,
        temperature=args.temperature,
        stream=True)

    collected_chunks = []
    collected_messages = []
    for chunk in completion:
        chunk_time = time.time() - start_time  # calculate the time delay of the chunk
        collected_chunks.append(chunk)  # save the event response
        chunk_message = chunk.choices[0].delta.content 
        print(chunk_message or "\n", end = "")
        collected_messages.append(chunk_message)  
        #print(f"Message received {chunk_time:.2f} seconds after request: {chunk_message}") 
        
    collected_messages = [m for m in collected_messages if m is not None]
    full_reply_content = ''.join([m if m is not None else '\n' for m in collected_messages])
    
    return {'role': 'assistant', 'content': full_reply_content}


"""
 model="gpt-4-vision-preview",
  messages=[
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "What’s in this image?"},
        {
          "type": "image_url",
          "image_url": {
            "url": "",
          },
        },
      ],
    }
  ],
"""

""" def get_embeddings(texts: list[str]) -> list[dict]:
    embeddings = openai.Embedding.create(
        model = "text-embedding-ada-002",
        queries = texts
    )
    return embeddings
 """