from openai import OpenAI
from mistralai.client import MistralClient
import anthropic
import time
import os
import yaml
from utils import media_type_map, encode_image

def get_start_time():
    return time.time()

openai_client = OpenAI()
mistral_client = MistralClient()
anthropic_client = anthropic.Client()

def save_config(messages: list[dict[str, any]], args: dict) -> list[dict[str, any]]:
    config_path = input(f"Enter config file path (default is {os.path.join(os.getenv('LLT_PATH'), 'config.yaml')}, 'exit' to cancel): ")
    if config_path.lower() == 'exit':
        print("Config save canceled.")
        return messages
    
    with open(config_path, 'w') as config_file:
        yaml.dump(vars(args), config_file, default_flow_style=False)
    print(f"Config saved to {config_path}")
    return messages

def update_config(messages: list[dict[str, any]], args: dict) -> list[dict[str, any]]:
    print("Current config:")
    for arg in vars(args):
        print(f"{arg}: {getattr(args, arg)}")
    
    try:
        key = input("Enter the name of the config option to update (or 'exit' to cancel): ")
        if key.lower() == 'exit':
            print("Config update canceled.")
            return messages
        if not hasattr(args, key):
            print(f"Config {key} does not exist.")
            return messages
        current_value = getattr(args, key)
        print(f"Current value for {key}: {current_value}")
        new_value = input(f"Enter new value for {key} (or 'exit' to cancel): ")
        if new_value.lower() == 'exit':
            print("Config update canceled.")
            return messages

        casted_value = type(current_value)(new_value)
        setattr(args, key, casted_value)
        print(f"Config updated: {key} = {casted_value}")
    except ValueError as e:
        print(f"Invalid value provided. Error: {e}")
    except Exception as e:
        print(f"An error occurred while updating the configuration. Error: {e}")
    
    return messages

def load_config(path: str):
    with open(path, 'r') as config_file:
        return yaml.safe_load(config_file)

api_config = load_config(os.path.join(os.getenv('LLT_PATH'), "config.yaml"))
full_model_choices = [f"{model_family}-{model}" for provider in api_config['models'] 
                      for model_family in api_config['models'][provider] 
                      for model in api_config['models'][provider][model_family]]

def collect_messages(completion_stream: dict):
    role, collected_messages = "assistant",[]
    for chunk in completion_stream:
        chunk_message = chunk.choices[0].delta.content
        print(chunk_message or "\n", end="")
        if chunk_message is not None:
            collected_messages.append(chunk_message)
    full_reply_content = ''.join(collected_messages)
    return {'role': role, 'content': full_reply_content}

def get_completion(messages: list[dict[str, any]], args: dict) -> dict:
    providers = api_config['models']
    func_map = {func.__name__.split("_")[1]: func for func in [get_anthropic_completion, get_openai_completion, get_mistral_completion]}
    for provider, families in providers.items():
        full_model_names = [f"{family}-{model}" for family in families for model in families[family]]
        if args.model in full_model_names and provider in func_map:
            return func_map[provider](messages, args) 
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
    return collect_messages(completion)

def get_mistral_completion(messages: list[dict[str, any]], args: dict) -> dict:
    start_time = get_start_time()
    completion = mistral_client.chat_stream(
        messages=messages,
        model=args.model,
        temperature=args.temperature,
        max_tokens=4096
    )
    full_reply_content = collect_messages(completion)

def anthropic_image_helper(messages: list[dict[str, any]], args: dict) -> dict:
    #auto-detect image field in message of messages list with list comprehension
    # media_type_map
    # valid types = "TEXT" | "IMAGE"
    # ("TEXT" | "IMAGE", media_type, data) = message['content'][i]['source']
    for message in messages:
        if type(message['content']) == list:
            for i in range(len(message['content'])):
                current_message = message['content'][i]
                if current_message['type'] == 'image_url':
                    # check that args.image_path matches current_message['source']['url']
                    # convert image_url to image
                    print(f"args.image_path: {args.image_path}")
                    url = current_message['url']

                    if not args.image_path:
                        # instances of llt where args.image_path is not set, but messages to be loaded contain base 64 encoded images
                        # will use the url to download the image
                        args.image_path = url
                        print(f"args.image_path: {args.image_path}")
                        
                    media_type = media_type_map[image_type]
                    #assert (media_type == media_type_map[image_type])
                    data=encode_image(args.image_path)
                    new_message = {'role': 'user', 'source': {'type' : 'base64', 'media_type': media_type, 'data': data}}
                    print(f"new_message: {new_message}")
                    message['content'][i] = new_message
                    print(f"New message: {new_message}")
                elif current_message['type'] == 'image':
                    assert (current_message['source']['media_type'] == media_type_map[current_message['source']['media_type']])
                    print(f"Passed assertion for {current_message['source']['media_type']}")
    return messages

""" def tokenize(messages: list[dict[str, any]], args: dict) -> int:
    num_tokens, content = 0, ""
    for message in messages:
        if type(message['content']) == list:
            for i in range(len(message['content'])):
                if message['content'][i]['type'] == 'text':
                    text = message['content'][i]['text']
                    content+=text
                elif message['content'][i]['type'] == 'image_url':
                    if (os.path.splitext(args.file_include)[1] in supported_images)
                    and is_base64(message['content'][i]['image_url']['url']):
                        num_tokens += count_image_tokens(os.path.expanduser(args.file_include))
                        print(f"Image tokens: {num_tokens}")
        else:
            content+=message['content']
    encoding = tiktoken.encoding_for_model("gpt-4")
    num_tokens += 4 + len(encoding.encode(content))
    print(f"Tokens: {num_tokens}")
    return num_tokens """

def get_anthropic_completion(messages: list[dict[str, any]], args: dict) -> dict:
    if messages[0]['role'] == 'system':
        system_prompt = messages[0]['content']
        messages = messages[1:]
    else:
        system_prompt = "You are a helpful programming assistant."
    #messages = anthropic_image_helper(messages, args)
    response_content = ""
    start_time = get_start_time()
    with anthropic_client.messages.stream(
        model=args.model,
        system=system_prompt,
        messages=messages,
        temperature=args.temperature,
        max_tokens=4096
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_content += text
    return {'role': 'assistant', 'content': response_content+"\n\n"}

