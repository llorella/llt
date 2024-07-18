# utils.py
import os
import sys
import readline
import base64
import tiktoken
from PIL import Image
from math import ceil
import tempfile
from io import BytesIO
import pprint
from typing import List, Dict
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

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def encoded_img_to_pil_img(data_str):
    base64_str = data_str.replace("data:image/png;base64,", "")
    image_data = base64.b64decode(base64_str)
    return Image.open(BytesIO(image_data))

def save_to_tmp_img_file(data_str):
    image = encoded_img_to_pil_img(data_str)
    tmp_img_path = os.path.join(tempfile.mkdtemp(), "tmp_img.png")
    image.save(tmp_img_path)
    return tmp_img_path

# Message utilities
def tokenize(messages: List[Dict[str, any]], args: Dict) -> int:
    num_tokens, content = 0, ""
    for msg in messages:
        msg_content = msg['content']
        if isinstance(msg_content, list):
            for item in msg_content:
                if item['type'] == 'text':
                    content += item['text']
                # elif item['type'] == 'image_url':
                #     num_tokens += count_image_tokens(item['image_url']['url'])
        else:
            content += msg_content
    encoding = tiktoken.encoding_for_model("gpt-4")
    num_tokens += 4 + len(encoding.encode(content))
    print(f"Tokens: {num_tokens}")
    return num_tokens

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

# Miscellaneous utilities
language_extension_map = {
    '.py': 'python', '.sh': 'shell', '.md': 'markdown', '.html': 'html',
    '.css': 'css', '.js': 'javascript', '.ts': 'typescript', '.json': 'json',
    '.yaml': 'yaml', '.c': 'c', '.cpp': 'cpp', '.rs': 'rust', '.go': 'go',
    '.csv': 'csv', '.cu': 'cuda',
}

def inverse_kv_map(d):
    return {v: k for k, v in d.items()}

def is_base64(text):
    try:
        base64.b64decode(text)
        return True
    except Exception as e:
        print(f"Error decoding base64: {e}")
        return False

def quit_program(messages: List, args: Dict) -> None:
    sys.exit(0)