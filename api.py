from openai import OpenAI
from mistralai.client import MistralClient
import anthropic
import time
import os
import yaml

openai_client = OpenAI()
mistral_client = MistralClient()
anthropic_client = anthropic.Client()

def load_config(path: str):
    with open(path, 'r') as config_file:
        return yaml.safe_load(config_file)

api_config = load_config(os.path.join(os.getenv('LLT_PATH'), "config.yaml"))

def collect_messages(completion_stream):
    collected_messages = []
    for chunk in completion_stream:
        chunk_message = chunk.choices[0].delta.content
        print(chunk_message or "\n", end="")
        if chunk_message is not None:
            collected_messages.append(chunk_message)
    full_reply_content = ''.join(collected_messages)
    return full_reply_content

def get_start_time():
    return time.time()

def get_completion(messages: list[dict[str, any]], args: dict) -> dict:
    available_models = api_config['models']
    func_map = {func.__name__.split("_")[1]: func for func in [get_anthropic_completion, get_openai_completion, get_mistral_completion]}
    provider = next((provider for provider, models in available_models.items() if args.model in models), None)
    if provider and provider in func_map:
        return func_map[provider](messages, args)
    else:
        raise ValueError(f"Invalid model: {args.model}")

def get_openai_completion(messages: list[dict[str, any]], args: dict) -> dict:
    start_time = get_start_time()
    completion = openai_client.chat.completions.create(
        messages=messages,
        model=args.model,
        temperature=args.temperature,
        stream=True,
        logprobs=True,
        max_tokens=4096
    )
    full_reply_content = collect_messages(completion)
    return {'role': 'assistant', 'content': full_reply_content}

def get_mistral_completion(messages: list[dict[str, any]], args: dict) -> dict:
    start_time = get_start_time()
    completion = mistral_client.chat_stream(
        messages=messages,
        model=args.model,
        temperature=args.temperature,
        max_tokens=4096
    )
    full_reply_content = collect_messages(completion)
    return {'role': 'assistant', 'content': full_reply_content}

def get_anthropic_completion(messages: list[dict[str, any]], args: dict) -> dict:
    if messages[0]['role'] == 'system':
        system_prompt = messages[0]['content']
        messages = messages[1:]
    else:
        system_prompt = "You are a helpful programming assistant."

    response_content = ""
    start_time = get_start_time()
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

full_model_choices = [f"{model_family}-{model}" for provider in api_config['models'] 
                      for model_family in api_config['models'][provider] 
                      for model in api_config['models'][provider][model_family]]