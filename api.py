from openai import OpenAI
from mistralai.client import MistralClient
import anthropic
import time
import os
import yaml
import tiktoken

openai_client = OpenAI()
mistral_client = MistralClient()
anthropic_client = anthropic.Client()

def load_config():
    config_path = "config.yaml"
    with open(config_path, 'r') as config_file:
        return yaml.safe_load(config_file)

def count_tokens(message, model):
    model = "gpt-4" # todo: add support for other models
    encoding = tiktoken.encoding_for_model(model)
    num_tokens = 4 + len(encoding.encode(message['content']))
    return num_tokens

def get_completion(messages: list[dict[str, any]], args: dict) -> dict:
    config = load_config()
    available_models = config['models']
    if args.model in available_models['mistral']:
        return get_mistral_completion(messages, args)
    elif args.model in available_models['openai']:
        return get_openai_completion(messages, args)
    elif args.model in available_models['anthropic']:
        return get_anthropic_completion(messages, args)
    else:
        raise ValueError(f"Invalid model: {args.model}")

def get_openai_completion(messages: list[dict[str, any]], args: dict) -> dict:
    start_time = time.time()

    completion = openai_client.chat.completions.create(
        messages=messages,
        model=args.model,
        temperature=args.temperature,
        stream=True,
        logprobs=True,
        max_tokens=4096
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

def get_mistral_completion(messages: list[dict[str, any]], args: dict) -> dict:
    start_time = time.time()
    num_tokens = count_tokens(messages, args.model)
    print(f"Input tokens: {num_tokens}")

    completion = mistral_client.chat_stream(
        messages=messages,
        model=args.model,
        temperature=args.temperature,
        max_tokens=4096 - num_tokens
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

def get_anthropic_completion(messages: list[dict[str, any]], args: dict) -> dict:
    if messages[0]['role'] == 'system':
        system_prompt = messages[0]['content']
        messages = messages[1:]
    else:
        system_prompt = "You are a helpful programming assistant."

    response_content = ""
    start_time = time.time()
    with anthropic_client.messages.stream(
        model=args.model,
        system=system_prompt,
        messages=messages,
        max_tokens=4096
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_content += text

    return {'role': 'assistant', 'content': response_content+"\n\n"}