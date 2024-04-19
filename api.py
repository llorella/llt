from openai import OpenAI
from mistralai.client import MistralClient
import anthropic
import time
import os
import yaml
import subprocess

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
    func_map = {func.__name__.split("_")[1]: func for func in [get_anthropic_completion, get_openai_completion, get_mistral_completion, get_local_completion]}
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

############################################################################
# local model backends below
############################################################################
shared_local_llms_dir = '/usr/share/llms/'
llama_cpp_dir = os.getenv('HOME')  + '/llama.cpp/'
local_log_dir = os.getenv('HOME') + '/.llama_cpp_logs/'
local_log_file = local_log_dir + 'llg_log'

def get_local_completion(messages: list[dict[str, any]], args: dict) -> dict:
    if not messages:
        raise ValueError("No messages provided for completion.")
    model_path =  shared_local_llms_dir + 'Meta-' + args.model.title() + '-Q5_K_M.gguf'
    print(f"model_path: {model_path}")
    command = [llama_cpp_dir + 'main','-m', str(model_path), '--color', '--temp', str(args.temperature),
                '--repeat-penalty', '1.1', '-n', '1000', '-p',
                f'<|begin_of_text|><|start_header_id|>system<|end_header_id|>\nYou are llama, a helpful AI assistant.<|eot_id|><|start_header_id|>user<|end_header_id|>\n{messages[-1]["content"]}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n', 
                '-c', str(args.max_tokens), '-r', '<|eot_id|>',
                '--in-prefix', '<|start_header_id|>user<|end_header_id|>\n\n', 
                '--in-suffix', '<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n', 
                '-ld', local_log_dir, '--log-file', local_log_file]
    try:
        completion = ""
        try: 
            result = subprocess.run(command, 
                                    check=True, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
            if (os.path.exists(local_log_file)):
                llama_cpp_log = load_config(local_log_file)
                completion = llama_cpp_log['output']
            else:
                print("Error: log file not found")
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running LLaMA model: {e.stderr}")
    
    return {'role': 'assistant', 'content': str(completion)}