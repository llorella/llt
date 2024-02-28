from openai import OpenAI
from mistralai.client import MistralClient
import time
import os

client = OpenAI()
mistral_api_key = os.getenv("MISTRAL_API_KEY")
mistral_client = MistralClient(api_key=mistral_api_key)

openai_models = ["gpt-4", "gpt-4-vision-preview", "gpt-4-1106-preview"]
mistral_models = ["open-mistral-7b", "open-mixtral-8x7b", "mistral-small-latest", "mistral-medium-latest", "mistral-large-latest"]

def get_completion(messages: list[dict[str, str]], args: dict) -> dict:
    if args.model in mistral_models:
        return get_mistral_completion(messages, args)
    elif args.model in openai_models:
        return get_openai_completion(messages, args)
    else:
        raise ValueError(f"Invalid model: {args.model}")


def get_openai_completion(messages: list[dict[str, str]], args: dict) -> dict:
    start_time = time.time()
    completion = client.chat.completions.create(
        messages=messages,
        model=args.model,
        temperature=args.temperature,
        stream=True)

    collected_chunks = []
    collected_messages = []
    for chunk in completion:
        chunk_time = time.time() - start_time
        collected_chunks.append(chunk)
        chunk_message = chunk.choices[0].delta.content
        print(chunk_message or "\n", end="")
        collected_messages.append(chunk_message)
        
    collected_messages = [m for m in collected_messages if m is not None]
    full_reply_content = ''.join(collected_messages)
    
    return {'role': 'assistant', 'content': full_reply_content}

def get_mistral_completion(messages: list[dict[str, str]], args: dict) -> dict:
    start_time = time.time()
    completion = mistral_client.chat_stream(
        messages=messages,
        model=args.model,
        temperature=args.temperature,
    )

    collected_chunks = []
    collected_messages = []
    for chunk in completion:
        chunk_time = time.time() - start_time
        collected_chunks.append(chunk)
        chunk_message = chunk.choices[0].delta.content
        print(chunk_message or "\n", end="")
        collected_messages.append(chunk_message)
        
    collected_messages = [m for m in collected_messages if m is not None]
    full_reply_content = ''.join(collected_messages)
    
    return {'role': 'assistant', 'content': full_reply_content}