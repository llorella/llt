from openai import OpenAI
from mistralai.client import MistralClient
import anthropic
import time
import os
import yaml
import subprocess

def get_start_time():
    return time.time()

mistral_client = MistralClient()
anthropic_client = anthropic.Client()
openai_client = OpenAI()

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
# local model implementations below
############################################################################
llama_cpp_options = api_config['llama_cpp']
llama_cpp_root_dir, llama_cpp_logs_dir = llama_cpp_options['root_dir'], llama_cpp_options['log_dir']

def get_local_model_path(model: str) -> str:
    path = api_config['local_llms_dir'] + model + '.gguf'
    print(f"model_path: {path}")
    return path

def get_local_completion(messages: list[dict[str, any]], args: dict) -> dict:
    if not messages:
        raise ValueError("No messages provided for completion.")
    model_prefix, model_path = args.model.split('-')[0], get_local_model_path(args.model)
    model_options = llama_cpp_options[model_prefix.lower()]

    def format_message(messages: list[dict[str, any]]) -> str:
        return ''.join([model_options['format'].format(role=message['role'], content=message['content']) for message in messages])
    
    command = [llama_cpp_root_dir + 'main','-m', str(model_path), '--color', '--temp', str(args.temperature),
                '--repeat-penalty', '1.1', '-n', f'{str(args.max_tokens)}', '-p',
                model_options['prompt-prefix'] + format_message(messages),
                '-r', f"{model_options['stop']}", '-ld', llama_cpp_logs_dir]
    try:
        completion = ""
        try: 
            completion = subprocess.run(command, 
                                    check=True, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True, 
                                    cwd=os.getenv('HOME'))
            print("\n")
            log_files = [os.path.join(llama_cpp_logs_dir, f) for f in os.listdir(llama_cpp_logs_dir) if os.path.isfile(os.path.join(llama_cpp_logs_dir, f))]
            completion = load_config(max(log_files, key=os.path.getmtime))['output']
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running local model {args.model}: {e.stderr}")
    return {'role': 'assistant', 'content': str(completion)}