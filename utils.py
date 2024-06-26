import os, sys
import pprint
import readline
import base64
import tiktoken
from PIL import Image
from math import ceil
import json

from typing import List, Dict

def quit_program(Dicts: List, args: Dict) -> None:
    sys.exit(0)

colors = {  
    'system': '\033[34m',    # blue
    'user': '\033[32m',      # green
    'assistant': '\033[35m', # magenta
    'reset': '\033[0m'
}

class Colors:
    YELLOW = '\033[93m'
    WHITE = '\033[97m'
    RESET = '\033[0m'

    @staticmethod
    def print_colored(text, color):
        print(color + text + Colors.RESET)

    @staticmethod
    def pretty_print_dict(message: Dict):
        formatted_message = pprint.pformat(message, indent=4)
        Colors.print_colored(formatted_message, Colors.WHITE)

    @staticmethod
    def print_header():
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("***** Welcome to llt, the little language terminal. *****", Colors.WHITE)
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("*********************************************************\n", Colors.YELLOW)

def directory_completer(dir_path):
    def completer(text, state):
        files = os.listdir(dir_path)
        matches = [file for file in files if file.startswith(text)]
        return matches[state] if state < len(matches) else None
    return completer

def path_completer(text, state):
    readline.get_line_buffer().split()
    if '~' in text:
        text = os.path.expanduser('~') + text[1:]
    if os.path.isdir(text) and not text.endswith(os.path.sep):
        return [text + os.path.sep][state]
    return [x for x in os.listdir(os.path.dirname(text)) if x.startswith(os.path.basename(text))][state]

def list_completer(values):
    def completer(text, state):
        matches = [value for value in values if value.startswith(text)]
        return matches[state] if state < len(matches) else None
    return completer

def list_input(values: List[str], input_string: str = "Enter a value from list") -> str:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(list_completer(values))
    return input(input_string +  " (tab to autocomplete): ")

def content_input() -> str:
    print("Enter content below.")
    Colors.print_colored("*********************************************************", Colors.YELLOW)
    content = input("> ") or ""
    Colors.print_colored("\n*********************************************************\n", Colors.YELLOW)
    return content
    
def path_input(default_file: str = None, root_dir: str = None) -> str:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(directory_completer(root_dir) if root_dir else path_completer)
    file_path = input(f"Enter file path (default is {default_file}): ")
    return os.path.join(root_dir if root_dir else os.getcwd(), os.path.expanduser(file_path) if file_path else default_file)

def llt_input(plugin_keys: List[str]) -> str:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(list_completer(plugin_keys))
    return input("llt> ")

def count_image_tokens(file_path: str) -> int:
    def resize(width, height):
        if width > 1024 or height > 1024:
            if width > height:
                height = int(height * 1024 / width)
                width = 1024
            else:
                width = int(width * 1024 / height)
                height = 1024
        return width, height
    
    def count_image_tokens(width: int, height: int):
        width, height = resize(width, height)
        h = ceil(height / 512)
        w = ceil(width / 512)
        total = 85 + 170 * h * w
        return total
    
    with Image.open(file_path) as image:
        width, height = image.size
        return count_image_tokens(width, height)
    
def is_base64(text):
    try:
        base64.b64decode(text)
        return True
    except:
        return False
    
def tokenize(messages: List[Dict[str, any]], args: Dict) -> int:
    num_tokens, content = 0, ""
    for idx in range(len(messages)):
        msg_content = messages[idx]['content']
        if type(msg_content) == list:
            for i in range(len(msg_content)):
                msg_type = msg_content[i]['type']
                msg_value = msg_content[i][msg_type]
                if msg_type == 'text': content+=msg_value
                #elif msg_type== 'image_url': num_tokens += count_image_tokens(msg_value['url'])
        else: 
            content+=msg_content
    encoding = tiktoken.encoding_for_model("gpt-4")
    num_tokens += 4 + len(encoding.encode(content))
    print(f"Tokens: {num_tokens}")
    return num_tokens

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    

# Function to encode the image
def _encode_image(image_content):
    return base64.b64encode(image_content).decode('utf-8')

import tempfile 
from io import BytesIO

def encoded_img_to_pil_img(data_str):
    base64_str = data_str.replace("data:image/png;base64,", "")
    image_data = base64.b64decode(base64_str)
    image = Image.open(BytesIO(image_data))

    return image


def save_to_tmp_img_file(data_str):
    base64_str = data_str.replace("data:image/png;base64,", "")
    image_data = base64.b64decode(base64_str)
    image = Image.open(BytesIO(image_data))

    tmp_img_path = os.path.join(tempfile.mkdtemp(), "tmp_img.png")
    image.save(tmp_img_path)

    return tmp_img_path
    
def convert_text_base64(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    message_index = get_valid_index(messages, "convert text to base64", index) if not args.non_interactive else index
    content = messages[message_index]['content']
    messages[message_index]['content'] = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    return messages

language_extension_map = {
    '.py': 'python',
    '.sh': 'shell',
    '.md': 'markdown',
    '.html': 'html',
    '.css': 'css',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.json': 'json',
    '.yaml': 'yaml',
    '.c': 'c',
    '.cpp': 'cpp',
    '.rs': 'rust',
    '.go': 'go',
    '.csv': 'csv',
    '.cu': 'cuda',
}

inverse_kv_map = lambda d: {v: k for k, v in d.items()}
 
def get_valid_index(messages: List[Dict[str, any]], prompt: str, default=-1):
    try:
        idx = input(f"Enter index of message to {prompt} (default is {'all' if not default else default}): ") or default
        if not idx: return default
        idx = int(idx) % len(messages)  # support negative indexing
    except ValueError:
        print("Invalid input. Using default.")
        idx = default
    if not -len(messages) <= idx < len(messages):
        raise IndexError("Index out of range. No operation will be performed.")
    return idx  

def export_messages(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    fmt = input("Enter export format (json, txt): ").lower() or "json"
    output_path = path_input(f"exported_messages.{fmt}", os.getcwd())
    with open(output_path, 'w') as file:
        for message in messages:
            if fmt == "json":
                file.write(json.dumps(message, indent=4))
            elif fmt == "txt":
                file.write(f"role: {message['role']}\ncontent: {message['content']}\n\n")
            elif fmt == "md":
                print(f"md support coming soon via logcmd_llt_branch_1 (llt created branch for auto generated plugins)")
                """ from logcmd_llt_branch_1 import export_messages_to_markdown
                export_messages_to_markdown(messages, args) """
            else:   
                print("Invalid export format. Please choose from json, txt, or md.")
            
    print(f"Messages exported to text file at {output_path}")

def update_config(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    for arg in vars(args):
        print(f"{arg}: {getattr(args, arg)}")
    try:
        key = input("Enter the name of the config option to update: ")
        if not hasattr(args, key):
            print(f"Config {key} does not exist.")
            return messages
        current_value = getattr(args, key)
        new_value = input(f"Current value for {key}: {current_value}\nEnter new value for {key} (or 'exit' to cancel): ")
        if new_value.lower() == 'exit' or not new_value: return messages
        if isinstance(current_value, int):
            casted_value = int(new_value)
        elif isinstance(current_value, float):
            casted_value = float(new_value)
        elif isinstance(current_value, str):
            casted_value = str(new_value)
        else:
            casted_value = new_value
        setattr(args, key, casted_value)
        print(f"Config updated: {key} = {casted_value}")
    except ValueError as e:
        print(f"Invalid value provided. Error: {e}")
    except Exception as e:
        print(f"An error occurred while updating the configuration. Error: {e}")
    return messages