# completion.py
import requests
import os
import yaml
import json
from typing import List, Dict, Any

from message import Message
from utils.helpers import list_input, content_input, encode_image_to_base64, Colors
from plugins import llt
import anthropic  # For anthropic Client usage, if needed


def load_config(path: str):
    with open(path, 'r') as config_file:
        return yaml.safe_load(config_file)


def list_model_names(providers: Dict[str, Any]) -> List[str]:
    """
    Helper to produce a list of "model-version" strings from your config.
    """
    return [
        f"{model}-{version}"
        for _, details in providers.items()
        for model, versions in details.get('models', {}).items()
        for version in versions
    ]


api_config = load_config(os.path.join(os.getenv("LLT_PATH", ""), "config.yaml"))
full_model_choices = list_model_names(api_config["providers"])


def get_provider_details(model_name: str):
    """
    Returns (provider, api_key_string, completion_url)
    or raises ValueError if not found in config.
    """
    for provider, details in api_config["providers"].items():
        for model, versions in details.get("models", {}).items():
            possible_names = [f"{model}-{ver}" for ver in versions]
            if model_name in possible_names:
                return (
                    provider,
                    details.get("api_key", None),
                    details.get("completion_url", None)
                )
    raise ValueError(f"Model {model_name} not found in config.")


def send_request(
    completion_url: str,
    api_key_string: str,
    messages: List[Dict[str, Any]],
    args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generic request to a completion endpoint that streams tokens.
    """
    headers = {
        "Authorization": f"Bearer {os.getenv(api_key_string)}",
        "Content-Type": "application/json",
    }
    data = {
        "messages": messages,
        "model": args.model,
        "max_completion_tokens": args.max_tokens,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "stream": True,
    }

    full_response_content = ""
    try:
        with requests.post(
            completion_url, headers=headers, json=data, stream=True
        ) as response:
            response.raise_for_status()
            for chunk in response.iter_lines():
                if chunk:
                    decoded_chunk = chunk.decode("utf-8")
                    if decoded_chunk.startswith("data: [DONE]"):
                        break
                    if decoded_chunk.startswith("data: "):
                        payload = decoded_chunk[len("data: "):]
                        json_data = json.loads(payload)
                        choice = json_data["choices"][0]
                        delta = choice["delta"]
                        finish_reason = choice["finish_reason"]

                        if finish_reason is None:
                            text = delta.get("content", "") or ""
                            print(text, end="", flush=True)
                            full_response_content += text
                        if finish_reason == "stop":
                            print("\r")
                            break
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        if e.response is not None:
            print(f"Error details: {e.response.status_code}\n{e.response.text}")

    return {"role": "assistant", "content": full_response_content}


def get_anthropic_completion(messages: List[Dict[str, Any]], args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Example for using the Anthropic python client for streaming completions.
    """
    anthropic_client = anthropic.Client()

    if messages and messages[0].get("role") == "system":
        system_prompt = messages[0]["content"]
        messages = messages[1:]
    else:
        system_prompt = "You are a helpful assistant."

    for message in messages:
        # If you want to handle any image encoding in the messages, do so here
        if isinstance(message.get("content"), list):
            for content_item in message["content"]:
                if content_item.get("type") == "image" and content_item["source"].get("data", "").startswith("file://"):
                    pass

    response_content = ""
    try:
        with anthropic_client.messages.stream(
            model=args.model,
            system=system_prompt,
            messages=messages,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                response_content += text
            print("\r")
    except Exception as e:
        print(f"Anthropic API request failed: {e}")

    return {"role": "assistant", "content": response_content}


def get_local_completion(messages: List[Message], args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder for a local LLM or other offline approach.
    """
    return {"role": "assistant", "content": "[local model output]"}


@llt
def complete(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Generate a completion from the LLM
    Type: bool
    Default: false
    flag: complete
    short:
    """
    provider, api_key, completion_url = get_provider_details(args.model)

    if provider == "anthropic":
        completion = get_anthropic_completion(messages, args)
    elif provider == "local":
        completion = get_local_completion(messages, args)
    else:
        completion = send_request(completion_url, api_key, messages, args)

    messages.append(completion)
    return messages



@llt
def format_args(args) -> str:
    """
    Description: Format arguments into a color-coded string
    Type: bool
    Default: false
    flag: format_args
    short:
    """
    args_dict = vars(args)
    max_key_length = max(len(str(key)) for key in args_dict.keys())
    formatted_str = f"\n{Colors.BOLD}Current Configuration:{Colors.RESET}\n"
    formatted_str += "=" * (max_key_length + 30) + "\n"

    categories = {
        "Model Settings": ["model", "temperature", "max_tokens", "top_p", "logprobs"],
        "Input/Output": ["load", "file", "write", "prompt"],
        "Role Settings": ["role"],
        "Directories": ["cmd_dir", "exec_dir", "ll_dir"],
        "Mode Settings": ["non_interactive"]
    }

    for category, keys in categories.items():
        relevant_args = {k: args_dict[k] for k in keys if k in args_dict}
        if relevant_args:
            formatted_str += f"\n{Colors.BLUE}{category}:{Colors.RESET}\n"
            formatted_str += "-" * (max_key_length + 30) + "\n"
            for key, value in relevant_args.items():
                key_str = f"{key}:".ljust(max_key_length + 2)
                if isinstance(value, bool):
                    value_color = Colors.GREEN if value else Colors.RED
                    formatted_str += f"{Colors.BOLD}{key_str}{Colors.RESET} {value_color}{value}{Colors.RESET}\n"
                elif key == "model":
                    formatted_str += f"{Colors.BOLD}{key_str}{Colors.RESET} {Colors.PURPLE}{value}{Colors.RESET}\n"
                elif isinstance(value, (int, float)):
                    formatted_str += f"{Colors.BOLD}{key_str}{Colors.RESET} {Colors.YELLOW}{value}{Colors.RESET}\n"
                else:
                    formatted_str += f"{Colors.BOLD}{key_str}{Colors.RESET} {value}\n"
    return formatted_str


@llt
def get_args(messages: List[Dict[str, Any]], args: Dict, index: int = -1) -> List[Dict[str, Any]]:
    """
    Description: Display current arguments in a formatted way
    Type: bool
    Default: false
    flag: get_args
    short:
    """
    print(format_args(args))
    return messages


@llt
def modify_args(messages: List[Dict[str, Any]], args: Dict, index: int = -1) -> List[Dict[str, Any]]:
    """
    Description: Enhanced interface for modifying arguments
    Type: bool
    Default: false
    flag: modify_args
    short:
    """
    print(format_args(args))
    args_dict = vars(args)

    categories = {
        "1. Model Settings": ["model", "temperature", "max_tokens"],
        "2. Input/Output": ["load", "file", "write", "prompt"],
        "3. Role Settings": ["role"],
        "4. Directories": ["cmd_dir", "exec_dir", "ll_dir"],
        "5. Mode Settings": ["non_interactive"]
    }

    print(f"\n{Colors.BOLD}Select a category to modify:{Colors.RESET}")
    category = list_input(list(categories.keys()))
    if not category:
        print("No category selected. Args remain unchanged.")
        return messages

    fields_in_category = categories[category]
    print(f"\n{Colors.BOLD}Select field to modify:{Colors.RESET}")
    field_to_modify = list_input(fields_in_category)
    if not field_to_modify:
        print("No field selected. Args remain unchanged.")
        return messages

    current_value = args_dict[field_to_modify]
    print(f"\nCurrent value of {Colors.BOLD}{field_to_modify}{Colors.RESET}: {Colors.YELLOW}{current_value}{Colors.RESET}")

    try:
        new_value = None
        if isinstance(current_value, bool):
            new_value = list_input(["True", "False"]) == "True"
        elif field_to_modify == "model":
            new_value = list_input(full_model_choices)
        elif isinstance(current_value, int):
            while True:
                val = content_input(f"Enter new int value for {field_to_modify}: ")
                try:
                    new_value = int(val)
                    break
                except ValueError:
                    print(f"{Colors.RED}Invalid int.{Colors.RESET}")
        elif isinstance(current_value, float):
            while True:
                val = content_input(f"Enter new float value for {field_to_modify}: ")
                try:
                    new_value = float(val)
                    break
                except ValueError:
                    print(f"{Colors.RED}Invalid float.{Colors.RESET}")
        else:
            new_value = content_input(f"Enter new value for {field_to_modify}: ")

        if new_value is not None:
            setattr(args, field_to_modify, new_value)
            print(f"\n{Colors.GREEN}Updated {field_to_modify}:{Colors.RESET}")
            print(f"  {Colors.BOLD}Old value:{Colors.RESET} {current_value}")
            print(f"  {Colors.BOLD}New value:{Colors.RESET} {new_value}")
        else:
            print(f"{Colors.YELLOW}Value unchanged.{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}Error updating value: {str(e)}{Colors.RESET}")

    return messages
