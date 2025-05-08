import requests
import os
import yaml
import json
from typing import List, Dict, Any, Iterable, cast # Import cast

import anthropic
from anthropic.types import ToolUseBlock, ContentBlockStopEvent # Import ToolUseBlock and ContentBlockStopEvent
from tools import registry_to_json_schema, make_scheduled_from_tool_use, ScheduledCommand

from message import Message
from utils import (
    Colors, file_handler, input_handler, InputValue
) 
from tools import llt
from logger import llt_logger

# Cached tool schema and its version identifier
_CACHED_ANTHROPIC_TOOL_CATALOGUE = None
_CACHED_TOOLS_JSON_MTIME = None
# Path to tools.json, assuming it's in LLT_DIR or CWD (defaults to CWD if LLT_DIR is not set).
TOOLS_JSON_PATH = os.path.join(os.getenv("LLT_DIR", os.getcwd()), "tools.json")


# Type mapping from tool spec to JSON schema
TYPE_MAP = {
    "int": "integer",
    "float": "number",
    "str": "string",
    "string": "string",
    "bool": "boolean",
    "boolean": "boolean",
}

def load_config(path: str):
    try:
        with open(path, 'r') as config_file:
            config = yaml.safe_load(config_file)
            return config
    except Exception as e:
        Colors.print_colored(f"Error loading config: {e}", Colors.RED)
        return {}


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


api_config = load_config(os.path.join(os.getenv("LLT_DIR", ""), "config.yaml"))
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
    messages: List[Message],
    args: Dict[str, Any]
) -> Message:
    """
    Generic request to a completion endpoint that streams tokens.
    """
    headers = {
        "Authorization": f"Bearer {os.getenv(api_key_string)}",
        "Content-Type": "application/json",
    }
    data = {
        "messages": messages,
        "model": args.get('model'),
        "temperature": args.get('temperature'),
        "stream": True,
    }
    
    if args.get('max_tokens'):
        data["max_completion_tokens"] = args['max_tokens']

    full_response_content = ""
    response_buffer = []
    final_status_code = None

    try:
        with requests.post(
            completion_url, headers=headers, json=data, stream=True
        ) as response:
            for chunk in response.iter_lines():
                if chunk:
                    decoded_chunk = chunk.decode("utf-8")
                    response_buffer.append(decoded_chunk) # buffer all chunks

                    if decoded_chunk.startswith("data: [DONE]"):
                        break
                    if decoded_chunk.startswith("data: "):
                        payload = decoded_chunk[len("data: "):]
                        try:
                            json_data = json.loads(payload)
                            choice = json_data.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            finish_reason = choice.get("finish_reason")

                            if finish_reason is None:
                                text = delta.get("content") or delta.get("reasoning_content") or " "
                                print(text, end="", flush=True)
                                full_response_content += text
                            if finish_reason == "stop":
                                print("\r")
                                break
                        except json.JSONDecodeError:
                            # Ignore chunks that are not valid JSON in the stream if needed,
                            # but still buffer them in case they are part of an error message
                            pass # Or add specific handling if non-JSON chunks are expected normally

            final_status_code = response.status_code # Store status code after iteration

        # Check status code after the stream is processed
        if final_status_code and final_status_code >= 400:
            Colors.print_colored(f"Request failed with status code: {final_status_code}", Colors.RED)
            full_buffered_response = "\n".join(response_buffer)
            try:
                # Attempt to parse the entire buffered response as JSON
                error_data = json.loads(full_buffered_response)
                Colors.print_colored(f"Error response JSON: {json.dumps(error_data, indent=2)}", Colors.RED)
            except json.JSONDecodeError:
                # If not JSON, print the raw buffered response
                Colors.print_colored(f"Error response text: {full_buffered_response}", Colors.RED)
            # Optional: Re-raise an exception here if needed for upstream handling
            # raise requests.exceptions.HTTPError(f"{final_status_code} Client Error", response=response_obj)
            return Message(role="assistant", content=f"Error: Received status code {final_status_code}")


    except requests.RequestException as e:
        # This catches connection errors, etc., before a response is received
        Colors.print_colored(f"Request failed (pre-response): {e}", Colors.RED)
        # Print the full traceback for debugging connection errors
        import traceback
        Colors.print_colored(f"Full traceback: {traceback.format_exc()}", Colors.RED)
        return Message(role="assistant", content=f"Error: {str(e)}")

    # If status code was < 400, return the successful response
    return Message(role="assistant", content=full_response_content)

def get_anthropic_completion(messages: List[Message], args: Dict[str, Any]) -> Any:
    """
    Use the Anthropic python client for streaming completions with tool support.
    """
    try:
        anthropic_client = anthropic.Client()
    except Exception as e:
        llt_logger.log_error("Use tool mode initialization failed: Missing anthropic package.", {"error": str(e)})
        return Message(role="assistant", content=f"Error: {str(e)}")
    
    # Extract system prompt if present (only the first system message, ignore others)
    system_msgs = list(filter(lambda m: m.get("role") == "system", messages))
    system_prompt = system_msgs[0]["content"] if system_msgs else "You are a helpful assistant. You can use tools to assist the user."
    payload_msgs = list(filter(lambda m: m.get("role") != "system", messages))
    
    # Handle image content if present
    for message in payload_msgs:
        if isinstance(message.get("content"), list):
            for content_item in message["content"]:
                if content_item.get("type") == "image" and content_item["source"].get("data", "").startswith("file://"):
                    print(f"Found image in message: {content_item['source']['data']}")
                    pass  # Handle image loading if needed

    response_content = ""
    tool_blocks: List[ToolUseBlock] = []  # Explicitly type tool_blocks
    use_tool_mode = bool(args.get("use_tool", False))
        
    params = {
        "model": args.get('model', "claude-3-7-sonnet-20250219"),
        "system": system_prompt,
        "messages": payload_msgs,
        "temperature": args.get('temperature', 0.7),
    }
    
    if args.get('max_tokens'):
        params["max_tokens"] = args['max_tokens']
    
    # Add tool support if requested
    if use_tool_mode:
        llt_logger.log_info("Use tool mode enabled. Attempting to use/build tool catalogue.")
        
        global _CACHED_ANTHROPIC_TOOL_CATALOGUE, _CACHED_TOOLS_JSON_MTIME
        
        current_mtime = None
        try:
            if os.path.exists(TOOLS_JSON_PATH):
                current_mtime = os.path.getmtime(TOOLS_JSON_PATH)
            else:
                llt_logger.log_warning(f"Tool definition file {TOOLS_JSON_PATH} not found. Tool schema caching may be affected.")
        except OSError as e:
            llt_logger.log_warning(f"Could not get mtime for {TOOLS_JSON_PATH}: {e}. Tool schema caching may be affected.")

        # Cache validation logic
        if _CACHED_ANTHROPIC_TOOL_CATALOGUE is not None:
            # Case 1: File existed and mtime matches
            if current_mtime is not None and _CACHED_TOOLS_JSON_MTIME is not None and current_mtime == _CACHED_TOOLS_JSON_MTIME:
                llt_logger.log_info("Using cached tool catalogue (version match based on tools.json mtime).")
            # Case 2: File was missing/inaccessible before, and still is. Assume cache is valid for this state.
            elif current_mtime is None and _CACHED_TOOLS_JSON_MTIME is None:
                llt_logger.log_info("Using cached tool catalogue (tool file tools.json still missing/inaccessible).")
            # Case 3: Mismatch (file changed, appeared, or disappeared). Invalidate cache.
            else:
                llt_logger.log_info("Tool definition file tools.json changed, appeared, or disappeared. Regenerating tool catalogue.")
                _CACHED_ANTHROPIC_TOOL_CATALOGUE = None # Invalidate cache
        
        if _CACHED_ANTHROPIC_TOOL_CATALOGUE is None:
            llt_logger.log_info("No valid cached tool catalogue found or cache invalidated. Generating...")
            _CACHED_ANTHROPIC_TOOL_CATALOGUE = registry_to_json_schema()
            _CACHED_TOOLS_JSON_MTIME = current_mtime # Cache the mtime (or None if file was inaccessible)
            llt_logger.log_info("Tool catalogue generated and cached.")
        
        catalogue = _CACHED_ANTHROPIC_TOOL_CATALOGUE
        params["tools"] = catalogue
        params["tool_choice"] = {"type": "auto"}
        llt_logger.log_info("Sending request to Anthropic API with tools.", {
            "model": params["model"],
            "message_count": len(payload_msgs),
            "tool_count": len(catalogue) if isinstance(catalogue, list) else 0,
        })
    
    try:
        with anthropic_client.messages.stream(**params) as stream:
            for block in stream:
                if hasattr(block, "type"):
                    if block.type == "text":
                        print(block.text, end="", flush=True)
                        response_content += block.text
                    elif block.type == "content_block_stop":
                        # Assuming 'block' here is an object that has a 'content_block' attribute
                        # and that 'content_block' has a 'type' attribute.
                        # This was the original structure that seemed to work logically.
                        if hasattr(block, 'content_block') and hasattr(block.content_block, 'type') and block.content_block.type == "tool_use":
                            # If it's a tool_use content block, cast it to ToolUseBlock before appending
                            tool_blocks.append(cast(ToolUseBlock, block.content_block))
                        
                else:
                    # Fallback for older SDKs or unexpected block types
                    text = getattr(block, "text", None)
                    if text:
                        print(text, end="", flush=True)
                        response_content += text
                    print("\r")
    except Exception as e:
        Colors.print_colored(f"Anthropic API error: {str(e)}", Colors.RED)
        # Print the full traceback for debugging
        import traceback
        Colors.print_colored(f"Full traceback: {traceback.format_exc()}", Colors.RED)
        return Message(role="user", content=f"Error: {str(e)}")
    
    # Check if we have any tool use blocks and need to create scheduled commands
    if tool_blocks:
    
        # Turn tool_use blocks into ScheduledCommand objects
        try:
            scheduled = []
            # Rename loop variable to avoid potential scope collision with 'block' from the stream
            for tool_use_item in tool_blocks: 
                # Since tool_blocks is List[ToolUseBlock], tool_use_item is ToolUseBlock.
                # The getattr check for "type" == "tool_use" is redundant here if the list is correctly populated.
                llt_logger.log_info("Processing tool use block:", {"block": str(tool_use_item)})
                # make_scheduled_from_tool_use expects a ToolUseBlock.
                scheduled.append(make_scheduled_from_tool_use(tool_use_item))
            
            llt_logger.log_info("Tool use blocks processed into ScheduledCommand objects.", {
                "scheduled_count": len(scheduled),
                "scheduled_commands": [str(cmd) for cmd in scheduled],
            })
        except Exception as e:
            Colors.print_colored(f"Error processing tool use blocks: {str(e)}", Colors.RED)
            llt_logger.log_error("Failed to process tool use blocks.", {"error": str(e)})
            return messages
        
        # Automatically re-ask the model after tools run
        if scheduled:
            scheduled.append(ScheduledCommand("complete", -1))
            llt_logger.log_info("Scheduled re-ask of the model after tool execution.")
            
            return (messages, scheduled)
    
    # If no tool use or if tools aren't enabled, just return the message
    return Message(role="assistant", content=response_content)
    
def get_local_completion(messages: List[Message], args: Dict[str, Any]) -> Message:
    """
    Placeholder for a local LLM or other offline approach.
    """
    return Message(role="assistant", content="TODO: Reintegrate local LLM support. This is a placeholder response.")

@llt()
def encode_images(messages: List[Message], args: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Encode image URLs into the proper format for different providers.
    Handles both file paths and regular URLs.
    """
    encoded_messages = None
    
    for i, message in enumerate(messages):
        if message.get("role") == "user" and message.get("content") and isinstance(message["content"], list):
            for j, content_item in enumerate(message["content"]):
                if content_item.get("type") == "image_url":
                    image_url = content_item["image_url"]
                    if image_url.startswith("file://") or os.path.exists(image_url):
                        if encoded_messages is None:
                            encoded_messages = json.loads(json.dumps(messages))
                        try:
                            base64_image = file_handler.encode_image_to_base64(
                                image_url.replace("file://", "")
                            )
                            _, ext = os.path.splitext(image_url)
                            if args.get('model', '').startswith("claude"):
                                encoded_messages[i]["content"][j] = {
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
                            Colors.print_colored(f"Error encoding image: {e}", Colors.RED)
                            return messages
                        
    return encoded_messages or messages
                

@llt()
def complete(messages: List[Message], args: Dict, index: int = -1):
    """
    Description: Generate a completion from the LLM
    Type: bool
    Default: false
    flag: complete
    short:
    """
    use_tool_mode = bool(args.get("use_tool", False))
    auto_mode = bool(args.get("auto", False))

    # ------------------------------------------------------------------ #
    # Handle completions with or without tool use                        #
    # ------------------------------------------------------------------ #
    provider, api_key, completion_url = get_provider_details(
        args.get("model", "deepseek-chat")
    )
    
    if use_tool_mode and provider != "anthropic":
        llt_logger.log_error("Use tool mode is only supported with the Anthropic provider.")

    # encode_images handles creating a copy if modifications are needed for image encoding.
    # The original 'messages' list passed to 'complete' should not be mutated directly by encode_images.
    messages_with_images = encode_images(messages, args)

    if provider == "anthropic":
        result = get_anthropic_completion(messages_with_images, args)
        # Check if result is a tuple with (messages, scheduled)
        if isinstance(result, tuple) and len(result) == 2:
            return result  # Return directly if it contains scheduled commands
        completion = result  # Otherwise treat as a normal completion
    elif provider == "local":
        completion = get_local_completion(messages_with_images, args)
    else:
        completion = send_request(completion_url, api_key,
                                  messages_with_images, args)

    # Return a new list with the completion appended
    return messages_with_images + [completion]

@llt()
def modify_args(messages: List[Dict[str, Any]], args: Dict, index: int = -1) -> List[Dict[str, Any]]:
    """
    Description: Modify configuration arguments
    Type: bool
    Default: false
    flag: modify_args
    """
    
    arg_choices = [
        f"{key} ({type(value).__name__}) - {Colors.YELLOW}{value}{Colors.RESET}"
        for key, value in args.items()
    ]
    
    assert len(arg_choices) > 0, "No arguments to modify. Please add some arguments first."
    print(f"\n{Colors.BOLD}Current Configuration:{Colors.RESET}")
    selected = input_handler.get_list_input(options=arg_choices, prompt="Select an argument to modify:")
    if not selected:
        return messages

    key = selected.split()[0]
    current_value = args.get(key)
    print(f"\nCurrent value of {Colors.BOLD}{key}{Colors.RESET}: {Colors.YELLOW}{current_value}{Colors.RESET}")

    new_value: InputValue = ""
    try:
        if isinstance(current_value, bool):
            new_value = input_handler.get_list_input(["True", "False"]) == "True"
        elif key == "model":
            new_value = input_handler.get_list_input(full_model_choices)
        elif key == "role":
            new_value = input_handler.get_list_input(["user", "assistant", "system", "tool"])
        elif isinstance(current_value, (int, float)):
            type_cast = type(current_value)
            while True:
                val = input_handler.get_input(f"Enter new {type_cast.__name__} value")
                try:
                    new_value = type_cast(val)
                    break
                except ValueError:
                    Colors.print_colored(f"Invalid {type_cast.__name__}.", Colors.RED)
        else:
            new_value = input_handler.get_input("Enter new value")

        if new_value is not None:
            args[key] = new_value
            print(f"\n{Colors.GREEN}Updated {key}:{Colors.RESET}")
            print(f"  {Colors.BOLD}Old:{Colors.RESET} {current_value}")
            print(f"  {Colors.BOLD}New:{Colors.RESET} {new_value}")

    except Exception as e:
        Colors.print_colored(f"Error updating value: {str(e)}", Colors.RED)

    return messages


@llt()
def change_model(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    new_value = input_handler.get_list_input(full_model_choices)
    if new_value:
        args['model'] = new_value
        Colors.print_colored(f"Changed model to: {new_value}", Colors.GREEN)
    return messages

@llt()
def change_role(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Change the role of the message at index
    Type: string
    Default: user
    flag: change_role
    """
    if not args.get('non_interactive') and not args.get('auto'):
        new_value = input_handler.get_list_input(["user", "assistant", "system", "tool"])
    elif args.get('change_role'):
        new_value = args['change_role']
    else:
        # new value is one of available roles except current role
        new_value = next(iter(set(["user", "assistant", "system", "tool"]) - {messages[index]["role"]}))
    
    if new_value:
        messages[index]["role"] = new_value
        if not args.get('non_interactive'):
            Colors.print_colored(f"Changed role of message at index {index} to: {new_value}", Colors.GREEN)
    
    return messages
