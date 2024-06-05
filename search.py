## BEGIN 0 exa.py
import requests

def exa_search(query: str) -> str:
    url = "https://api.exa.ai/search"

    payload = {
        "query": query,
        "useAutoprompt": True,
        "type": "neural",
        "numResults": 10,

    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-api-key": "ad9058c5-02c3-46dc-b5b4-9dfd4f53be53"
    }

    response = requests.post(url, json=payload, headers=headers)

    print(response.text)

    return response.text

## END 0 exa.py

## BEGIN 1 exa.py
from message import Message
from typing import Dict, List
from utils import get_valid_index
import json
def search_plugin(messages: List[Message], args: Dict[str, any]) -> List[Message]: 
    idx = get_valid_index(messages=messages, prompt="search with exa from")
    message = messages[idx]
    results = exa_search(message['content'])
    obj = json.loads(results)
    messages.append(Message(role="user", content=json.dumps(obj['results'])))
    messages.append(Message(role="assistant", content=obj['autopromptString']))
    return messages

