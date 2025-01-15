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
    Use the Anthropic python client for streaming completions with tool support.
    """
    print("Entering get_anthropic_completion")
    anthropic_client = anthropic.Client()
    print(f"Created anthropic client")
    
    # Extract system prompt if present
    if messages and messages[0].get("role") == "system":
        system_prompt = messages[0]["content"]
        messages = messages[1:]
        print(f"Found system prompt: {system_prompt}")
    else:
        system_prompt = "You are a helpful assistant."
        print("Using default system prompt")

    # Load tools if enabled
    tools = None
    print(f"Tools enabled: {getattr(args, 'tools', False)}")
    if getattr(args, 'tools', False):
        try:
            tools_path = os.path.join(os.getenv("LLT_DIR", ""), "tools.json")
            print(f"Loading tools from {tools_path}")
            with open(tools_path, 'r') as f:
                tools_data = json.load(f)
                print(f"Loaded tools data: {tools_data}")
                # Convert tools data to format expected by Claude
                tools = []
                for func_name, func_data in tools_data.get("functions", {}).items():
                    print(f"Processing tool: {func_name}")
                    tool = {
                        "name": func_name,
                        "description": func_data.get("description", ""),
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                param: {"type": "string", "description": desc} 
                                for param, desc in func_data.get("parameters", {}).items()
                            },
                            "required": list(func_data.get("parameters", {}).keys())
                        }
                    }
                    tools.append(tool)
                print(f"Processed {len(tools)} tools")
        except Exception as e:
            print(f"Failed to load tools configuration: {e}")
            tools = None

    # Handle image content if present
    print("Checking for image content")
    for message in messages:
        if isinstance(message.get("content"), list):
            for content_item in message["content"]:
                if content_item.get("type") == "image" and content_item["source"].get("data", "").startswith("file://"):
                    print(f"Found image in message: {content_item['source']['data']}")
                    pass  # Handle image loading if needed

    response_content = ""
        # Configure message parameters
    print("Configuring message parameters")
    params = {
        "model": args.model,
        "system": system_prompt,
        "messages": messages,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
    }
    print(f"Parameters configured: {params}")
    
    # Add tools if enabled
    if tools:
        print("Adding tools to parameters")
        params["tools"] = tools
        # Let Claude decide when to use tools
        params["tool_choice"] = {"type": "auto"}
        print("Creating completion with tools")
        completion = anthropic_client.messages.create(
            model=args.model,
            system=system_prompt,
            messages=messages,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            tools=tools,
            tool_choice={"type": "auto"}
        )
        print(f"Got completion response with tools: {completion}")
        
        # Handle tool use in the response
        print(f"{completion.content[1]}")
        if len(completion.content) > 1:
            tool_result = completion.content[1]
            name = tool_result.name
            input = tool_result.input
            print(f"Tool result: {tool_result}")
            return {"role": "tool", "content": f"{name}: {input}"}

        print("No tool calls found, returning no-use message")            
        return {"role": "tool", "content": "No tool was used."}
            
    print("Streaming response without tools")
    # Stream the response
    with anthropic_client.messages.stream(**params) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_content += text
        print("\r")
        print(f"Final response content length: {len(response_content)}")


    print(f"Returning final response: {response_content[:100]}...")
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
def modify_args(messages: List[Dict[str, Any]], args: Dict, index: int = -1) -> List[Dict[str, Any]]:
    """
    Description: Modify configuration arguments
    Type: bool
    Default: false
    flag: modify_args
    """
    args_dict = vars(args)

    arg_choices = [
        f"{key} ({type(value).__name__}): {Colors.YELLOW}{value}{Colors.RESET}"
        for key, value in args_dict.items()
    ]
    
    print(f"\n{Colors.BOLD}Current Configuration:{Colors.RESET}")
    selected = list_input(arg_choices)
    if not selected:
        return messages

    key = selected.split()[0]
    current_value = args_dict[key]
    print(f"\nCurrent value of {Colors.BOLD}{key}{Colors.RESET}: {Colors.YELLOW}{current_value}{Colors.RESET}")

    try:
        # manually handle different types
        if isinstance(current_value, bool):
            new_value = list_input(["True", "False"]) == "True"
        elif key == "model":
            new_value = list_input(full_model_choices)
        elif key == "role":
            new_value = list_input(["user", "assistant", "system", "tool"])
        elif isinstance(current_value, (int, float)):
            type_cast = type(current_value)
            while True:
                val = content_input(f"Enter new {type_cast.__name__} value: ")
                try:
                    new_value = type_cast(val)
                    break
                except ValueError:
                    print(f"{Colors.RED}Invalid {type_cast.__name__}.{Colors.RESET}")
        else:
            new_value = content_input(f"Enter new value: ")

        if new_value is not None:
            setattr(args, key, new_value)
            print(f"\n{Colors.GREEN}Updated {key}:{Colors.RESET}")
            print(f"  {Colors.BOLD}Old:{Colors.RESET} {current_value}")
            print(f"  {Colors.BOLD}New:{Colors.RESET} {new_value}")

    except Exception as e:
        print(f"{Colors.RED}Error updating value: {str(e)}{Colors.RESET}")

    return messages
