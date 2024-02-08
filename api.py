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
        temperature=0.9,
        stream=True)

    # create variables to collect the stream of chunks
    collected_chunks = []
    collected_messages = []
    # iterate through the stream of events
    for chunk in completion:
        chunk_time = time.time() - start_time  # calculate the time delay of the chunk
        collected_chunks.append(chunk)  # save the event response
        chunk_message = chunk.choices[0].delta.content  # extract the message
        print(chunk_message)
        collected_messages.append(chunk_message)  # save the message
        #print(f"Message received {chunk_time:.2f} seconds after request: {chunk_message}")  # print the delay and text
        """ if chunk_message is not None:
            print(chunk_message, end="")
        else:
            print("\n") """
    # print the time delay and text received
    #print(f"Full response received {chunk_time:.2f} seconds after request")
    # clean None in collected_messages
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
            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg",
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