import requests
import os
import subprocess
import yaml
import json
from typing import List, Dict, Any
    
def load_config(path: str):
    with open(path, 'r') as config_file:
        return yaml.safe_load(config_file)
    
def list_model_names(providers):
    return [f"{model}-{version}"
            for _, details in providers.items()
            for model, versions in details.get('models', {}).items()
            for version in versions]

api_config = load_config(os.path.join(os.getenv('LLT_PATH'), "config.yaml"))
full_model_choices = list_model_names(api_config['providers'])

def get_provider_details(model_name: str):
    for provider, details in api_config['providers'].items():
        for model, versions in details.get('models', {}).items():
            if model_name in [f"{model}-{version}" for version in versions]:
                api_key_string, completion_url = None, None
                if details.__contains__("api_key"):
                    api_key_string = details.__getitem__("api_key")
                if details.__contains__("completion_url"):
                    completion_url = details.__getitem__("completion_url")
                return provider, api_key_string, completion_url
    raise ValueError(f"Model {model_name} not found in configuration.")

def send_request(completion_url: str, api_key_string: str, messages: List[Dict[str, Any]], args: Dict[str, Any]) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {os.getenv(api_key_string)}",
        "Content-Type": "application/json"
    }
    data = {
        "messages": messages,
        "model": args.model,
        "temperature": args.temperature,             
        "max_tokens": args.max_tokens,
        "stream": True
    }
    full_response_content = ""
    try:
        with requests.post(completion_url, headers=headers, json=data, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_lines():
                if chunk:
                    decoded_chunk = chunk.decode('utf-8')
                    if decoded_chunk.startswith("data: "):
                        if decoded_chunk.startswith("data: [DONE]"):
                            break
                        json_data = json.loads(decoded_chunk[6:])
                        choice = json_data['choices'][0]
                        delta = choice['delta']
                        finish_reason = choice['finish_reason']
                        if finish_reason is None:
                            print(delta['content'] or "\n", end="", flush=True)
                            full_response_content += delta['content']   
                        if finish_reason == 'stop': 
                            print("\r")
                            break
    except requests.RequestException as e:
        print(f"Request failed: {e}")
    return { 'role': 'assistant', 'content': full_response_content }

# anthropic's api is  different from other providers
import anthropic
def get_anthropic_completion(messages: List[Dict[str, any]], args: Dict) -> Dict[str, any]:
    anthropic_client = anthropic.Client()
    if messages[0]['role'] == 'system':
        system_prompt = messages[0]['content']
        messages = messages[1:]
    else:
        system_prompt = "You are a helpful programming assistant."
    response_content = ""
    with anthropic_client.messages.stream(
        model=args.model,
        system=system_prompt,
        messages=messages,
        temperature=args.temperature,
        max_tokens=args.max_tokens
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_content += text
        print("\r")
    return {'role': 'assistant', 'content': response_content}

def get_local_completion(messages: List[Dict[str, any]], args: Dict) -> Dict[str, any]:
    llamacpp_root_dir = os.getenv('LLAMACPP_DIR')
    llamacpp_log_dir = os.getenv('LLAMACPP_LOG_DIR')
    if not llamacpp_root_dir or not llamacpp_log_dir:
        raise EnvironmentError("LLAMACPP environment variables not set.")
    model_options = api_config['llamacpp'][args.model.split('-')[0].lower()]
    model_path = api_config['local_llms_dir'] + args.model + '.gguf'
    def format_message(messages: List[Dict[str, any]]) -> str:
        prompt_string = model_options['prompt-prefix']
        for i, msg in enumerate(messages):
            prompt_string += model_options['format'].format(role=msg['role'], content=msg['content'])
            if i == len(messages) - 1: prompt_string += model_options['in-suffix']
        return prompt_string
    command = [llamacpp_root_dir + 'main','-m', str(model_path), 
                '--color', '--temp', str(args.temperature), '-n', f"{str(args.max_tokens)}",
                '-p', format_message(messages),
                '-r', f"{model_options['stop']}", '-ld', llamacpp_log_dir]
    try:
        try: 
            completion = subprocess.run(command, 
                                    check=True, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True, 
                                    cwd=os.getenv('HOME'))
            print("\n")
            log_files = [os.path.join(llamacpp_log_dir, f) for f in os.listdir(llamacpp_log_dir) if os.path.isfile(os.path.join(llamacpp_log_dir, f))]
            return {'role': 'assistant', 'content': str(load_config(max(log_files, key=os.path.getmtime))['output'])}
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running local model {args.model}: {e.stderr}")
    
from plugins import plugin
from message import Message

@plugin
def completion(messages: List[Message], args: Dict) -> Dict[str, any]: 
    provider, api_key_string, completion_url = get_provider_details(args.model)
    if provider == 'anthropic': completion = get_anthropic_completion(messages, args)
    elif provider == 'local': completion = get_local_completion(messages, args)
    else: completion = send_request(completion_url, api_key_string, messages, args)
    messages.append(completion)
    return messages

@plugin
def model(messages: List[Message], args: Dict) -> Dict[str, any]:
    from utils import list_input
    model = list_input(full_model_choices, "Select model to use")
    if model: args.model = model
    return messages

@plugin
def temperature(messages: List[Message], args: Dict) -> Dict[str, any]:
    from utils import list_input
    temperature = input(f"Enter temperature (default is {args.temperature}): ")
    if temperature: args.temperature = float(temperature)
    return messages

@plugin
def max_tokens(messages: List[Message], args: Dict) -> Dict[str, any]:
    from utils import list_input
    max_tokens = input(f"Enter max tokens (default is {args.max_tokens}): ")
    if max_tokens: args.max_tokens = int(max_tokens)
    return messages