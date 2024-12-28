import requests
import os
import subprocess
import yaml
import json
from typing import List, Dict, Any

from message import Message
from utils.helpers import list_input, get_valid_index, content_input, encode_image_to_base64, Colors
from plugins import plugin

import anthropic

def load_config(path: str):
    with open(path, 'r') as config_file:
        return yaml.safe_load(config_file)
    
def list_model_names(providers):
    return [f"{model}-{version}"
            for _, details in providers.items()
            for model, versions in details.get('models', {}).items()
            for version in versions]

api_config = load_config(os.path.join(os.getenv("LLT_PATH"), "config.yaml"))
full_model_choices = list_model_names(api_config["providers"])


def get_provider_details(model_name: str):
    for provider, details in api_config["providers"].items():
        for model, versions in details.get("models", {}).items():
            if model_name in [f"{model}-{version}" for version in versions]:
                api_key_string, completion_url = None, None
                if details.__contains__("api_key"):
                    api_key_string = details.__getitem__("api_key")
                if details.__contains__("completion_url"):
                    completion_url = details.__getitem__("completion_url")
                return provider, api_key_string, completion_url
    raise ValueError(f"Model {model_name} not found in configuration.")

@plugin
def format_args(args) -> str:
    """Format args into a readable string with color coding."""
    args_dict = vars(args)
    max_key_length = max(len(str(key)) for key in args_dict.keys())
    formatted_str = f"\n{Colors.BOLD}Current Configuration:{Colors.RESET}\n"
    formatted_str += "=" * (max_key_length + 30) + "\n"
    
    # Group arguments by category
    categories = {
        "Model Settings": ["model", "temperature", "max_tokens", "top_p", "logprobs"],
        "Input/Output": ["load", "file", "write", "prompt"],
        "Role Settings": ["role"],
        "Directories": ["cmd_dir", "exec_dir", "ll_dir"],
        "Mode Settings": ["non_interactive"],
        "Plugin Settings": ["complete", "detach", "fold", "execute", "view", "email", "url", "tags", "xml", "embeddings"]
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

@plugin
def get_args(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    """Display current arguments in a formatted way."""
    print(format_args(args))
    return messages

@plugin
def modify_args(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    """
    Enhanced interface for modifying arguments with categorization and better UX.
    """
    args_dict = vars(args)
    
    # Print current configuration
    print(format_args(args))
    
    # Categorized fields for better organization
    categories = {
        "1. Model Settings": ["model", "temperature", "max_tokens", "top_p", "logprobs"],
        "2. Input/Output": ["load", "file", "write", "prompt"],
        "3. Role Settings": ["role"],
        "4. Directories": ["cmd_dir", "exec_dir", "ll_dir"],
        "5. Mode Settings": ["non_interactive"],
        "6. Plugin Settings": ["complete", "detach", "fold", "execute", "view", "email", "url", "tags", "xml", "embeddings"]
    }
    
    # Let user select category first
    print(f"\n{Colors.BOLD}Select a category to modify:{Colors.RESET}")
    category = list_input(list(categories.keys()))
    
    if not category:
        print("No category selected. Args remain unchanged.")
        return messages
    
    # Let user select field from category
    fields_in_category = categories[category]
    print(f"\n{Colors.BOLD}Select field to modify:{Colors.RESET}")
    field_to_modify = list_input(fields_in_category)
    
    if not field_to_modify:
        print("No field selected. Args remain unchanged.")
        return messages

    current_value = args_dict[field_to_modify]
    print(f"\nCurrent value of {Colors.BOLD}{field_to_modify}{Colors.RESET}: {Colors.YELLOW}{current_value}{Colors.RESET}")

    # Type-specific input handling with validation
    try:
        if isinstance(current_value, bool):
            new_value = list_input(["True", "False"]) == "True"
        elif field_to_modify == "model":
            new_value = list_input(full_model_choices)
        elif field_to_modify == "role":
            new_value = list_input(["user", "assistant", "system", "tool"])
        elif isinstance(current_value, int):
            while True:
                try:
                    new_value = int(content_input(f"Enter new integer value for {field_to_modify}: "))
                    break
                except ValueError:
                    print(f"{Colors.RED}Please enter a valid integer.{Colors.RESET}")
        elif isinstance(current_value, float):
            while True:
                try:
                    new_value = float(content_input(f"Enter new float value for {field_to_modify}: "))
                    break
                except ValueError:
                    print(f"{Colors.RED}Please enter a valid float.{Colors.RESET}")
        else:
            new_value = content_input(f"Enter new value for {field_to_modify}: ")
    
        if new_value is not None:  # Allow empty string but not None
            setattr(args, field_to_modify, new_value)
            print(f"\n{Colors.GREEN}Successfully updated {field_to_modify}:{Colors.RESET}")
            print(f"  {Colors.BOLD}Old value:{Colors.RESET} {current_value}")
            print(f"  {Colors.BOLD}New value:{Colors.RESET} {new_value}")
        else:
            print(f"{Colors.YELLOW}Value unchanged.{Colors.RESET}")
            
    except Exception as e:
        print(f"{Colors.RED}Error updating value: {str(e)}{Colors.RESET}")
        
    return messages

def send_request(completion_url: str, api_key_string: str, messages: List[Dict[str, Any]], args: Dict[str, Any]) -> Dict[str, Any]:
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
                    if decoded_chunk.startswith("data: "):
                        if decoded_chunk.startswith("data: [DONE]"):
                            break
                        json_data = json.loads(decoded_chunk[6:])
                        choice = json_data["choices"][0]
                        delta = choice["delta"]
                        finish_reason = choice["finish_reason"]
                        if finish_reason is None:
                            print(delta["content"] or "\n", end="", flush=True)
                            full_response_content += delta["content"]
                        if finish_reason == "stop":
                            print("\r")
                            break
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        print(f"Error details:\n{e.response.status_code}\n{e.response.text}")
    return {"role": "assistant", "content": full_response_content}

def get_anthropic_completion(messages: List[Dict[str, Any]], args: Dict, index: int = -1) -> Dict[str, Any]:
    """
    Sends a completion request to Anthropic's API with proper image encoding.
    """
    anthropic_client = anthropic.Client()
    if messages and messages[0].get("role") == "system":
        system_prompt = messages[0]["content"]
        messages = messages[1:]
    else:
        system_prompt = "You are a helpful programming assistant."
    
    # Encode images in messages
    for message in messages:
        if isinstance(message.get("content"), list):
            for content_item in message["content"]:
                if content_item.get("type") == "image" and content_item["source"].get("data").startswith("file://"):
                    image_path = content_item["source"]["data"][7:]  # Remove 'file://'
                    try:
                        encoded_image = encode_image_to_base64(image_path)
                        content_item["source"]["data"] = encoded_image
                        content_item["source"]["type"] = "base64"
                        content_item["source"]["media_type"] = f"image/{os.path.splitext(image_path)[1][1:].lower()}"
                    except Exception as e:
                        raise RuntimeError(f"Failed to encode image {image_path}: {e}")
    
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
        raise RuntimeError(f"Anthropic API request failed: {e}")
    
    return {"role": "assistant", "content": response_content}



def get_local_completion(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> Dict[str, any]:
    llamacpp_root_dir = os.getenv('LLAMACPP_DIR')
    llamacpp_log_dir = os.getenv('LLAMACPP_LOG_DIR')
    if not llamacpp_root_dir or not llamacpp_log_dir:
        raise EnvironmentError("LLAMACPP environment variables not set.")
    model_options = api_config["llamacpp"][args.model.split("-")[0].lower()]
    model_path = api_config["local_llms_dir"] + args.model + ".gguf"

    def format_message(messages: List[Dict[str, any]]) -> str:
        prompt_string = model_options["prompt-prefix"]
        for i, msg in enumerate(messages):
            prompt_string += model_options["format"].format(
                role=msg["role"], content=msg["content"]
            )
            if i == len(messages) - 1:
                prompt_string += model_options["in-suffix"]
        return prompt_string

    command = [
        llamacpp_root_dir + "llama-cli",
        "-m",
        str(model_path),
        "--color",
        "--temp",
        str(args.temperature),
        "-n",
        f"{str(args.max_tokens)}",
        "-p",
        format_message(messages),
        "-r",
        f"{model_options['stop']}",
        "-ld",
        llamacpp_log_dir,
    ]
    print(command)
    try:
        try: 
            subprocess.run(command, 
                        check=True, 
                        stderr=subprocess.PIPE,
                        universal_newlines=True, 
                        wd=os.getenv('HOME'))
            print("\n")
            log_files = [
                os.path.join(llamacpp_log_dir, f)
                for f in os.listdir(llamacpp_log_dir)
                if os.path.isfile(os.path.join(llamacpp_log_dir, f))
            ]
            return {
                "role": "assistant",
                "content": str(
                    load_config(max(log_files, key=os.path.getmtime))["output"]
                ),
            }
        except KeyboardInterrupt:
            print("KeyboardInterrupt")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error running local model {args.model}: {e.stderr}")

@plugin 
def complete(messages: List[Message], args: Dict, index: int = -1) -> Dict[str, any]: 
    provider, api_key_string, completion_url = get_provider_details(args.model)
    if provider == "anthropic":
        completion = get_anthropic_completion(messages, args)
    elif provider == "local":
        completion = get_local_completion(messages, args)
    else:
        completion = send_request(completion_url, api_key_string, messages, args)
    messages.append(completion)
    return messages

@plugin
def model(messages: List[Message], args: Dict, index: int = -1) -> Dict[str, any]:
    model = list_input(full_model_choices, "Select model to use")
    if model: args.model = model
    return messages

@plugin
def change_role(messages: List[Message], args: Dict, index: int = -1) -> Dict[str, any]:
    message_index = get_valid_index(messages, "modify role of", index)
    messages[message_index]['role'] = list_input(["user", "assistant", "system", "tool"], "Select role")
    return messages

@plugin
def temperature(messages: List[Message], args: Dict, index: int = -1) -> Dict[str, any]:
    temperature = input(f"Enter temperature (default is {args.temperature}): ")
    if temperature: args.temperature = float(temperature)
    return messages

@plugin
def max_tokens(messages: List[Message], args: Dict, index: int = -1) -> Dict[str, any]:
    max_tokens = input(f"Enter max tokens (default is {args.max_tokens}): ")
    if max_tokens: args.max_tokens = int(max_tokens)
    return messages

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
