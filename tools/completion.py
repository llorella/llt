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
    # 1) If use_tool mode AND using Anthropic → let Claude call our tools   #
    # ------------------------------------------------------------------ #
    if use_tool_mode and auto_mode:
        try:
            from tools import build_anthropic_catalogue, make_scheduled_from_tool_use
            anthropic_client = anthropic.Client()
        except Exception as e:
            Colors.print_colored("use_tool mode requires the anthropic package.", Colors.RED)
            llt_logger.log_error("use_tool mode initialization failed: Missing anthropic package.", {"error": str(e)})
            return messages

        llt_logger.log_info("use_tool mode enabled. Building tool catalogue.")
        catalogue = build_anthropic_catalogue()

        if messages and messages[0].get("role") == "system":
            system_prompt = messages[0]["content"]
            payload_msgs = messages[1:]
        else:
            system_prompt = (
                "You are a helpful assistant. You can use tools to assist the user."
            )
            payload_msgs = messages

        llt_logger.log_info("Sending request to Anthropic API.", {
            "model": "claude-3-7-sonnet-20250219",
            "system_prompt": system_prompt,
            "message_count": len(payload_msgs),
            "max_tokens": args.get("max_tokens") or 1024,
            "temperature": args.get("temperature", 0.7),
        })

        try:
            response = anthropic_client.messages.create(
                model="claude-3-7-sonnet-20250219",
                system=system_prompt,
                messages=payload_msgs,
                max_tokens=args.get("max_tokens") or 1024,
                temperature=args.get("temperature", 0.7),
                tools=catalogue,
                tool_choice={"type": "auto"},
            )
        except Exception as e:
            Colors.print_colored(f"Error during Anthropic API call: {str(e)}", Colors.RED)
            llt_logger.log_error("Anthropic API call failed.", {"error": str(e)})
            return messages

        # Collect assistant plain text
        plain = "".join(b.text for b in response.content if b.type == "text")
        if plain.strip():
            llt_logger.log_info("Received plain text response from assistant.", {"content": plain.strip()})
            messages.append(Message(role="assistant", content=plain.strip()))

        # Turn tool_use blocks into ScheduledCommand objects
        from tools import ScheduledCommand  # late import to avoid cycles
        try:
            for block in response.content:
                llt_logger.log_info("Response content block:", {"block": str(block)})
            scheduled: List[ScheduledCommand] = [
                make_scheduled_from_tool_use(b)
                for b in response.content if b.type == "tool_use"
            ]
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

        return (messages, scheduled) if scheduled else messages

    # ------------------------------------------------------------------ #
    # 2) NORMAL (non-use_tool) completion path                              #
    # ------------------------------------------------------------------ #
    provider, api_key, completion_url = get_provider_details(
        args.get("model", "deepseek-chat")
    )

    messages_with_images = encode_images(messages.copy(), args)

    if provider == "anthropic":
        completion = get_anthropic_completion(messages_with_images, args)
    elif provider == "local":
        completion = get_local_completion(messages_with_images, args)
    else:
        completion = send_request(completion_url, api_key,
                                  messages_with_images, args)

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
    Description: Suggest a tool to use (auto-executes in auto mode)
    Type: bool
    Default: false
    flag: suggest_tool
    """
    # Get tool specifications directly from registry_to_json_schema
    # instead of parsing a JSON file
    from tools import registry_to_json_schema
    tool_specs = registry_to_json_schema()
    tool_names = [tool['name'] for tool in tool_specs]
    
    # Check if Anthropic is available
    try:
        anthropic_client = anthropic.Client()
    except (ImportError, NameError):
        print(f"{Colors.RED}Error: Anthropic package not available. Please install with 'pip install anthropic'.{Colors.RESET}")
        return messages
        
    # Create conversation context for the prompt
    last_messages = messages[-3:] if len(messages) > 3 else messages
    conversation_snippets = []
    for i, msg in enumerate(messages):
        content = msg.get('content', '')
        if isinstance(content, str):
            snippet = content[:50] + ('...' if len(content) > 50 else '')
        else:
            snippet = '[Complex content]'
        conversation_snippets.append(f"Message {i}: {msg.get('role')} - {snippet}")
        
    # Construct optimized prompt
    optimized_prompt = f"""# LLT Command Suggestion Task

## CONTEXT
- **Available Tools**: {', '.join(tool_names)}
- **Current Conversation**:
<conversation_context>
{''.join(conversation_snippets)}
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

Examples:
- write --file conversation.ll
- execute --language python
- copy --blocks --lang python -1
- file_include
"""
    
    # Create a returned value container
    result = []
    auto_mode = args.get('auto', False)
    
    try:
        # Log the request
        llt_logger.log_info("Requesting tool suggestion from Anthropic.", 
                           {"model": args.get('model', "claude-3-sonnet-20240229"), 
                            "auto_mode": auto_mode})
        
        # Call Anthropic API with tools
        response = anthropic_client.messages.create(
            model=args.get('model', "claude-3-sonnet-20240229"),
            max_tokens=1024,
            messages=[{"role": "user", "content": optimized_prompt}],
            tools=tool_specs,
            tool_choice={"type": "auto"}
        )

        # Process the response to extract tool use
        suggested_tool_use = None
        if response.content:
            for block in response.content:
                if block.type == 'tool_use' and suggested_tool_use is None:
                    suggested_tool_use = block
                    break

        if suggested_tool_use:
            tool_name = suggested_tool_use.name
            tool_input = suggested_tool_use.input
            
            # Extract index if present, defaults to -1
            index = tool_input.get('index', -1) if isinstance(tool_input, dict) else -1
            
            # Format arguments for display
            args_text = ""
            if isinstance(tool_input, dict):
                for k, v in tool_input.items():
                    if k == 'index':
                        continue  # Already handled separately
                    if isinstance(v, str):
                        args_text += f' --{k} "{v}"'
                    elif isinstance(v, bool) and v:
                        args_text += f' --{k}'
                    elif not isinstance(v, bool):
                        args_text += f' --{k} {v}'
            
            # Create formatted suggestion
            suggestion = f"{tool_name}{args_text}{' ' + str(index) if index != -1 else ''}"
            
            # Display suggestion
            print(f"{Colors.CYAN}AI Suggestion: {suggestion}{Colors.RESET}")
            
            # In auto mode, automatically enqueue the command
            if auto_mode:
                from tools import ScheduledCommand
                
                # Create scheduled command with appropriate parameters
                cmd = ScheduledCommand(
                    name=tool_name,
                    index=index,
                    value=None  # Value passed via context
                )
                
                # Update context with the tool's parameters
                if isinstance(tool_input, dict):
                    for k, v in tool_input.items():
                        if k != 'index':  # Skip index parameter which is handled separately
                            if args.get(tool_name) is None:
                                args[tool_name] = {}
                            if not isinstance(args[tool_name], dict):
                                args[tool_name] = {}
                            args[tool_name][k] = v
                
                # Return messages and command to execute
                print(f"{Colors.GREEN}Auto-executing suggested command: {suggestion}{Colors.RESET}")
                result = (messages, [cmd])
            else:
                result = messages
                
        else:
            print(f"{Colors.YELLOW}AI did not suggest a specific tool.{Colors.RESET}")
            result = messages

    except Exception as e:
        print(f"{Colors.RED}Error during tool suggestion: {str(e)}{Colors.RESET}")
        llt_logger.log_error(f"Tool suggestion error: {str(e)}", {"traceback": traceback.format_exc()})
        result = messages

    return result



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
