# completion.py
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
from plugins import llt


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
        "max_tokens": args.get('max_tokens'),
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
                            text = delta.get("content") or delta.get("reasoning_content") or " "
                            print(text, end="", flush=True)
                            full_response_content += text
                        if finish_reason == "stop":
                            print("\r")
                            break
    except requests.RequestException as e:
        Colors.print_colored(f"Request failed: {e}", Colors.RED)
        if e.response is not None:
            Colors.print_colored(f"Error details: {e.response.status_code}\n{e.response.text}", Colors.RED)

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
    
    
        
    with anthropic_client.messages.stream(**params) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_content += text
        print("\r")
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

    # Load and process tools
    try:
        tools_path = os.path.join(os.getenv("LLT_DIR", ""), "tools.json")
        with open(tools_path, 'r') as f:
            tools_data = json.load(f)
            tools: Iterable[anthropic.types.ToolParam] = []
            tool_names = []
            
            for func_name, func_data in tools_data.get("functions", {}).items():
                tool_names.append(func_name)
                schema: anthropic.types.ToolParam = {
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
                }
                tools = [schema]
    except Exception as e:
        print(f"{Colors.RED}Error loading tools: {str(e)}{Colors.RESET}")
        return messages

    # Construct optimized prompt
    optimized_prompt = f"""Given the conversation context and available tools, determine the most appropriate next action:

1. CONTEXT:
- Current model: {args.get('model')}
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
    tool_choice: anthropic.types.ToolChoiceParam = {"type": "auto"}
    try:
        completion = anthropic_client.messages.create(
            model=args.get('model', "claude-3-sonnet-20241022"),
            system=system_prompt,
            messages=[{"role": "user", "content": optimized_prompt}],
            temperature=0.3,  # Lower temperature for more focused tool selection
            max_tokens=50,    # Minimal tokens needed for command + index
            tools=tools,
            tool_choice=tool_choice # Let the model decide if a tool is needed
        )

        for content in completion.content:
            print(f"{Colors.CYAN}Processing content type: {content.type}{Colors.RESET}")
            if content.type == "text":
                # Parse the response into command and index
                response = content.text.strip().split()
                if len(response) == 2 and response[0] in tool_names:
                    command, idx = response
                    messages.append(Message(role="tool", content=f"{command} {idx}"))
                    print(f"{Colors.GREEN}Tool selected: {command} at {str(index)}{Colors.RESET}")
                else:
                    print(f"{Colors.RED}Invalid tool selection format{Colors.RESET}")
            elif content.type == "tool_use":
                messages.append(Message(role="tool", content=f"Tool use: {content.name} with args {content.input}"))
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
