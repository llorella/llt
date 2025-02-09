# completion.py
import requests
import os
import yaml
import json
from typing import List, Dict, Any

from message import Message
from utils import list_input, content_input, encode_image_to_base64, Colors
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
                            text = delta.get("content") or delta.get("reasoning_content") or ""
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
    anthropic_client = anthropic.Client()
    
    # Extract system prompt if present
    if messages and messages[0].get("role") == "system":
        system_prompt = messages[0]["content"]
        messages = messages[1:]
    else:
        system_prompt = "You are a helpful assistant."    

    # Handle image content if present
    for message in messages:
        if isinstance(message.get("content"), list):
            for content_item in message["content"]:
                if content_item.get("type") == "image" and content_item["source"].get("data", "").startswith("file://"):
                    print(f"Found image in message: {content_item['source']['data']}")
                    pass  # Handle image loading if needed

    response_content = ""
    params = {
        "model": args.model,
        "system": system_prompt,
        "messages": messages,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
    }
    
    
        
    with anthropic_client.messages.stream(**params) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_content += text
        print("\r")
    return {"role": "assistant", "content": response_content}


    
def get_local_completion(messages: List[Message], args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder for a local LLM or other offline approach.
    """
    return {"role": "assistant", "content": "[local model output]"}

@llt
def encode_images(messages: List[Message], args: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Encode image URLs into the proper format for different providers.
    Handles both file paths and regular URLs.
    """
    # Create a deep copy of messages
    encoded_messages = None
    
    for i, message in enumerate(encoded_messages):
        if message.get("role") == "user" and message.get("content") and isinstance(message["content"], list):
            for j, content_item in enumerate(message["content"]):
                if content_item.get("type") == "image_url":
                    image_url = content_item["image_url"]
                    if image_url.startswith("file://") or os.path.exists(image_url):
                        if encoded_messages is None:
                            encoded_messages = json.loads(json.dumps(messages))
                        try:
                            base64_image = encode_image_to_base64(image_url.replace("file://", ""))
                            _, ext = os.path.splitext(image_url)
                            if args.model.startswith("claude"):
                                encoded_messages[i]["content"] = {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": f"image/{ext[1:].lower()}",
                                        "data": base64_image
                                    }
                                }
                            else:  # OpenAI format
                                encoded_messages[i]["content"][j] = {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{ext[1:].lower()};base64,{base64_image}"
                                    }
                                }
                        except Exception as e:
                            print(f"Error encoding image: {e}")
                            return None
    return encoded_messages
                

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

    messages_with_images = encode_images(messages.copy(), args)

    if provider == "anthropic":
        completion = get_anthropic_completion(messages_with_images, args)
    elif provider == "local":
        completion = get_local_completion(messages_with_images, args)
    else:
        completion = send_request(completion_url, api_key, messages_with_images, args)

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

@llt
def suggest_tool(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Suggest a tool to use with optimized prompt structure
    Type: bool
    Default: false
    flag: suggest_tool
    """
    anthropic_client = anthropic.Client()

    last_messages = messages[-3:] if len(messages) > 3 else messages
    conversation_context = "\n".join([
        f"{msg['role']}: {msg['content'][:100]}..." for msg in last_messages
    ])

    # Load and process tools
    try:
        tools_path = os.path.join(os.getenv("LLT_DIR", ""), "tools.json")
        with open(tools_path, 'r') as f:
            tools_data = json.load(f)
            tools = []
            tool_names = []
            
            for func_name, func_data in tools_data.get("functions", {}).items():
                tool_names.append(func_name)
                tools.append({
                    "name": func_name,
                    "description": func_data.get("description", ""),
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "index": {
                                "type": "integer",
                                "description": "Message index to operate on (-1 for last message)",
                                "default": -1
                            },
                            **{
                                param: {"type": "string", "description": desc} 
                                for param, desc in func_data.get("parameters", {}).items()
                            }
                        },
                        "required": ["index"]
                    }
                })
    except Exception as e:
        print(f"{Colors.RED}Error loading tools: {str(e)}{Colors.RESET}")
        return messages

    # Construct optimized prompt
    optimized_prompt = f"""Given the conversation context and available tools, determine the most appropriate next action:

1. CONTEXT:
- Current model: {args.model}
- Available tools: {', '.join(tool_names)}
- Conversation state:
{conversation_context}

2. CONSTRAINTS:
- Must output only: <command> <index>
- Index defaults to -1 for most recent
- Commands must be valid LLT plugins
- Consider conversation flow and state

3. EVALUATION CRITERIA:
- Immediate utility to conversation
- Command appropriateness
- Context relevance
- Action impact

OUTPUT FORMAT:
<command> <index>

NO explanation or additional text."""

    system_prompt = "You are a tool selection specialist. Your only task is to analyze context and select the most appropriate tool command and index. Respond with exactly two values: command and index."

    try:
        completion = anthropic_client.messages.create(
            model=args.model,
            system=system_prompt,
            messages=[{"role": "user", "content": optimized_prompt}],
            temperature=0.3,  # Lower temperature for more focused tool selection
            max_tokens=50,    # Minimal tokens needed for command + index
            tools=tools,
            tool_choice={"type": "auto"}
        )

        for content in completion.content:
            print(f"{Colors.CYAN}Processing content type: {content.type}{Colors.RESET}")
            if content.type == "text":
                print(f"{Colors.YELLOW}Received text response: {content.text.strip()}{Colors.RESET}")
            elif content.type == "tool_use":
                print(f"{Colors.YELLOW}Received tool suggestion: {content.name}{Colors.RESET}")
                print(f"{Colors.YELLOW}Tool arguments: {content.input}{Colors.RESET}")
            if content.type == "text":
                # Parse the response into command and index
                response = content.text.strip().split()
                if len(response) == 2 and response[0] in tool_names:
                    command, idx = response
                    messages.append({
                        "role": "llt",
                        "content": f"{command}{idx}"
                    })
                    print(f"{Colors.GREEN}Tool selected: {command} {idx}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Invalid tool selection format{Colors.RESET}")
            elif content.type == "tool_use":
                tool_message = {
                    "role": "tool",
                    "content": f"Tool use: {content.name} with args {content.input}"
                }
                messages.append(tool_message)
                print(f"{Colors.GREEN}Tool use suggested: {content.name}{Colors.RESET}")

    except Exception as e:
        print(f"{Colors.RED}Error during tool suggestion: {str(e)}{Colors.RESET}")

    return messages


@llt
def use_tool(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Use a tool
    Type: bool
    Default: false
    flag: use_tool
    """
    

    return messages


@llt
def change_model(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    new_value = list_input(full_model_choices)
    if new_value:
        args.model = new_value
        Colors.print_colored(f"Changed model to: {new_value}", Colors.GREEN)
    return messages