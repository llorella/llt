import requests
import os
import yaml
import json
from typing import List, Dict, Any, Iterable

import anthropic

from message import Message
from utils import (
    Colors, file_handler, input_handler, InputValue
)
from tools import llt
from logger import llt_logger # Assuming logger is accessible

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
        "max_completion_tokens": args.get('max_tokens'),
        "temperature": args.get('temperature'),
        #"max_tokens": args.get('max_tokens'),
        "stream": True,
    }

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


def get_anthropic_completion(messages: List[Message], args: Dict[str, Any]) -> Message:
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
        "model": args.get('model'),
        "system": system_prompt,
        "messages": messages,
        "temperature": args.get('temperature'),
        "max_tokens": args.get('max_tokens'),
    }
    
    try:
        with anthropic_client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                response_content += text
            print("\r")
    except Exception as e:
        Colors.print_colored(f"Anthropic API error: {str(e)}", Colors.RED)
        # Print the full traceback for debugging
        import traceback
        Colors.print_colored(f"Full traceback: {traceback.format_exc()}", Colors.RED)
        return Message(role="assistant", content=f"Error: {str(e)}")
        
    return Message(role="assistant", content=response_content)


    
def get_local_completion(messages: List[Message], args: Dict[str, Any]) -> Message:
    """
    Placeholder for a local LLM or other offline approach.
    """
    return Message(role="assistant", content="TODO: Reintegrate local LLM support. This is a placeholder response.")

@llt
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
                

@llt
def complete(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Generate a completion from the LLM
    Type: bool
    Default: false
    flag: complete
    short:
    """
    provider, api_key, completion_url = get_provider_details(args.get('model', "claude-3-5-sonnet-20241022"))

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

    # Load and process tools from the generated spec
    try:
        # Assuming llt_tools.json is in the current working directory or accessible path
        tools_path = "llt_tools.json" 
        if not os.path.exists(tools_path):
             # Fallback to checking LLT_DIR if not in CWD
             llt_dir = os.getenv("LLT_DIR", "")
             if llt_dir:
                 tools_path = os.path.join(llt_dir, "llt_tools.json")

        if not os.path.exists(tools_path):
             llt_logger.log_info(f"Tool specification file not found at default path or in LLT_DIR: {tools_path}", {"path": tools_path})
             print(f"{Colors.YELLOW}Warning: Tool specification file '{tools_path}' not found. Tool suggestions may be unavailable.{Colors.RESET}")
             return messages # Or handle appropriately

        with open(tools_path, 'r') as f:
            tools_data = json.load(f)
            tools: Iterable[anthropic.types.ToolParam] = []
            tool_names = []
            
            for func_name, func_data in tools_data.get("functions", {}).items():
                tool_names.append(func_name)
                
                tool_desc = func_data.get("description", "")
                tool_type = func_data.get("type")
                tool_default = func_data.get("default")

                # Base properties including the standard 'index'
                properties = {
                    "index": {
                        "type": "integer",
                        "description": "Message index to operate on (-1 for last message)",
                        "default": -1
                    }
                }
                # Base required properties
                required = ["index"]

                # Add specific property for the tool's argument if it's not a boolean flag
                if tool_type and tool_type not in ("bool", "boolean"):
                    schema_type = TYPE_MAP.get(tool_type, "string") # Default to string if type unknown
                    prop_name = "value" # Generic name for the value parameter
                    properties[prop_name] = {
                        "type": schema_type,
                        "description": f"Value for the {func_name} command ({tool_desc})" 
                    }
                    if tool_default is not None:
                        # Attempt to cast default based on type for JSON schema compliance
                        try:
                            if schema_type == "integer":
                                properties[prop_name]["default"] = int(tool_default)
                            elif schema_type == "number":
                                properties[prop_name]["default"] = float(tool_default)
                            elif schema_type == "boolean": # Should not happen here, but for safety
                                properties[prop_name]["default"] = str(tool_default).lower() == 'true'
                            else:
                                properties[prop_name]["default"] = str(tool_default)
                        except (ValueError, TypeError):
                             llt_logger.log_info(f"Could not cast default value '{tool_default}' for {func_name}", {"tool": func_name})
                             properties[prop_name]["default"] = str(tool_default) # Keep as string if cast fails

                    # Only require the value if no default is provided
                    if tool_default is None:
                       required.append(prop_name)

                # Even for booleans, Anthropic might expect a property definition
                elif tool_type in ("bool", "boolean"):
                     prop_name = "enabled" # Simple name for boolean flag
                     properties[prop_name] = {
                         "type": "boolean",
                         "description": f"Enable the {func_name} flag ({tool_desc})",
                         "default": str(tool_default).lower() == 'true' if tool_default is not None else False
                     }
                     # Boolean flags are typically optional in schema
                
                schema: anthropic.types.ToolParam = {
                    "name": func_name,
                    "description": tool_desc,
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
                tools.append(schema)
            
            # --- Rest of the function (prompt construction, API call) ---
            # This part remains largely the same, just uses the new 'tools' list
            # For debugging, let's print the constructed tools and return for now
            print("-------------------------")
            llt_logger.log_info("Constructed tools for suggestion.", {"count": len(tools)})
            # TODO: Remove the return below and implement the actual Anthropic API call
            # return messages 
            # -------------------------------------------------------------

    except FileNotFoundError:
        llt_logger.log_error(f"Tool specification file not found: {tools_path}", {"path": tools_path})
        print(f"{Colors.RED}Error: Tool specification file '{tools_path}' not found.{Colors.RESET}")
        return messages
    except json.JSONDecodeError:
        llt_logger.log_error(f"Error decoding JSON from tool specification file: {tools_path}", {"path": tools_path})
        print(f"{Colors.RED}Error: Could not decode JSON from '{tools_path}'. Is it valid?{Colors.RESET}")
        return messages
    except Exception as e:
        llt_logger.log_error(f"An unexpected error occurred while processing tools: {str(e)}", {"exception_type": type(e).__name__})
        print(f"{Colors.RED}Error processing tools: {str(e)}{Colors.RESET}")
        return messages

    # Construct optimized prompt (Example - adapt as needed)
    optimized_prompt = f"""# LLT Command Suggestion Task

## CONTEXT
- **Available Tools**: {', '.join(tool_names)}
- **Current Conversation**:
<conversation_context>
    {''.join([f"Message {i}: {msg['role']} - {msg['content'][:50]}..." for i, msg in enumerate(messages)])}
</conversation_context>

## OBJECTIVE
Analyze the conversation and suggest the most helpful LLT command that would assist the user right now.

## CONSTRAINTS
- Suggest only valid LLT tools from the available tools list
- Commands must follow format: <command> [arguments] [index]
- Index parameter defaults to -1 (most recent message) if not specified
- Focus on what would be most immediately useful given the conversation state

## REASONING PROCESS
1. Identify the current conversation topic or task
2. Consider what action would most logically help the user next:
   - Does the user need to save/load conversation? (load, write)
   - Would they benefit from editing content? (edit_content, remove)
   - Is code execution or file manipulation needed? (execute, write_file)
   - Would they benefit from copying content? (copy)
   - Is file inclusion helpful? (file_include)
3. Select the most appropriate command with relevant arguments

## EVALUATION CRITERIA
- **Utility**: How immediately useful is this command?
- **Relevance**: How well does it match the conversation context?
- **Appropriateness**: Is this the right tool for the current situation?
- **Impact**: How significantly will this improve the user's workflow?

## OUTPUT FORMAT
<command> [arguments] [index]
w

Examples:
- write --file conversation.ll
- execute --language python
- copy --blocks --lang python -1
- file_include

"""
    
    try:
        llt_logger.log_info("Requesting tool suggestion from Anthropic.", {"model": "claude-3-opus-20240229"}) # Or your preferred model
        response = anthropic_client.messages.create(
            model="claude-3-7-sonnet-20250219", # Replace with your desired model
            max_tokens=1024,
            messages=[{"role": "user", "content": optimized_prompt}],
            tools=list(tools), # Pass the constructed tools list
            tool_choice={"type": "auto"} # Let Anthropic decide
        )

        llt_logger.log_info("Received tool suggestion response from Anthropic.", {"response_stop_reason": response.stop_reason})

        # Process the response to extract tool use
        suggested_tool_use = None
        if response.content:
            # Track counts of each block type
            block_type_counts = {}
            
            for block in response.content:
                block_type = block.type
                # Increment count for this block type
                block_type_counts[block_type] = block_type_counts.get(block_type, 0) + 1
                
                # Log each block
                llt_logger.log_info(f"Processing response block of type: {block_type}", 
                                   {"block_index": block_type_counts[block_type]})
                
                # Still capture the first tool_use block for further processing
                if block.type == 'tool_use' and suggested_tool_use is None:
                    suggested_tool_use = block
                    llt_logger.log_info("Extracted tool use suggestion.", 
                                       {"tool_name": block.name, "tool_input": block.input})

        if suggested_tool_use:
            # TODO: Decide how to present this suggestion to the user
            # Maybe format it nicely and print it?
            # Maybe add it as a new message?
            tool_name = suggested_tool_use.name
            tool_input = suggested_tool_use.input
            suggestion_text = f"Suggested command: {tool_name}"
            
            # Format arguments nicely
            args_list = []
            if isinstance(tool_input, dict):
                 for k, v in tool_input.items():
                     # Skip default index if it's -1 maybe? Or always show?
                     # if k == 'index' and v == -1: continue 
                     if isinstance(v, str):
                         args_list.append(f'--{k} "{v}"') # Quote string args
                     elif isinstance(v, bool) and v:
                          args_list.append(f'--{k}') # Add boolean flag if true
                     elif not isinstance(v, bool):
                          args_list.append(f'--{k} {v}') # Add other args
            
            if args_list:
                suggestion_text += " " + " ".join(args_list)

            print(f"{Colors.CYAN}AI Suggestion: {suggestion_text}{Colors.RESET}")
            
            # Example: Add suggestion as an assistant message
            # messages.append({"role": "assistant", "content": f"Suggestion: Consider using the '{tool_name}' tool. Input: {tool_input}"})
            
        else:
            llt_logger.log_info("No specific tool use suggested by Anthropic.")
            print(f"{Colors.YELLOW}AI did not suggest a specific tool.{Colors.RESET}")

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
    new_value = input_handler.get_list_input(full_model_choices)
    if new_value:
        args['model'] = new_value
        Colors.print_colored(f"Changed model to: {new_value}", Colors.GREEN)
    return messages

@llt
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

@llt
def whisper(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    import pyaudio
    import wave
    import threading
    import openai
    import tempfile
    import os

    p = pyaudio.PyAudio()

    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 1024

    # global flag to control recording
    stop_recording = threading.Event()
    frames = []

    def record_audio():
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        print("Recording... Press Enter to stop.")
        while not stop_recording.is_set():
            data = stream.read(CHUNK)
            frames.append(data)

        stream.stop_stream()
        stream.close()

    def save_audio():
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            wf = wave.open(temp_audio.name, "wb")
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))
            wf.close()
            return temp_audio.name

    def transcribe_audio(audio_file):
        with open(audio_file, "rb") as file:
            transcript = openai.audio.transcriptions.create(
                model="whisper-1",
                file=file,
            )
        return transcript.text

    record_thread = threading.Thread(target=record_audio)
    record_thread.start()

    input()
    stop_recording.set()
    record_thread.join()

    audio_file = save_audio()
    transcription = transcribe_audio(audio_file)

    os.unlink(audio_file)

    messages.append(Message(role="user", content=transcription))

    print(f"Transcription: {transcription}")

    p.terminate()
    
    return messages
