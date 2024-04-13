import os, sys
import pprint
import readline
import base64
import tiktoken
from PIL import Image
from math import ceil

def quit_program(messages: list, args: dict) -> None:
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
    def pretty_print_dict(message: dict):
        formatted_message = pprint.pformat(message, indent=4)
        Colors.print_colored(formatted_message, Colors.WHITE)

    @staticmethod
    def print_header():
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("***** Welcome to llt, the little language terminal. *****", Colors.WHITE)
        Colors.print_colored("*********************************************************", Colors.YELLOW)
        Colors.print_colored("*********************************************************\n", Colors.YELLOW)

def input_role(role: str) -> str:
    return input(f"Enter role(default is {role}): ") or role

def content_input() -> str:
    print("Enter content below.")
    Colors.print_colored("*********************************************************", Colors.YELLOW)
    content = input("> ") or ""
    Colors.print_colored("\n*********************************************************\n", Colors.YELLOW)
    return content

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
    
def path_input(default_file: str = None, root_dir: str = None) -> str:
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(directory_completer(root_dir) if root_dir else path_completer)
    file_path = input(f"Enter file path (default is {default_file}): ")
    return os.path.join(root_dir if root_dir else os.getcwd(), os.path.expanduser(file_path) if file_path else default_file)

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
    
supported_images = ['.png', '.jpg', '.jpeg']

def is_base64(text):
    try:
        base64.b64decode(text)
        return True
    except:
        return False
    
def tokenize(messages: list[dict[str, any]], args: dict) -> int:
    num_tokens, content = 0, ""
    for message in messages:
        if type(message['content']) == list:
            for i in range(len(message['content'])):
                if message['content'][i]['type'] == 'text':
                    text = message['content'][i]['text']
                    content+=text
                elif message['content'][i]['type'] == 'image_url':
                    if (os.path.splitext(args.file_include)[1] in supported_images)\
                    and is_base64(message['content'][i]['image_url']['url']):
                        num_tokens += count_image_tokens(os.path.expanduser(args.file_include))
                        print(f"Image tokens: {num_tokens}")
        else:
            content+=message['content']
    encoding = tiktoken.encoding_for_model("gpt-4")
    num_tokens += 4 + len(encoding.encode(content))
    print(f"Tokens: {num_tokens}")
    return num_tokens
     

def count_tokens(message: dict, args: dict) -> int:
    num_tokens, content = 0, ""
    if type(message['content']) == list:
        for i in range(len(message['content'])):
            if message['content'][i]['type'] == 'text':
                text = message['content'][i]['text']
                content+=text
            elif message['content'][i]['type'] == 'image_url':
                if (os.path.splitext(args.file_include)[1] in supported_images)\
                and is_base64(message['content'][i]['image_url']['url']):
                    num_tokens += count_image_tokens(os.path.expanduser(args.file_include))
                    print(f"Image tokens: {num_tokens}")
    else:
        content+=message['content']

    encoding = tiktoken.encoding_for_model("gpt-4")
    num_tokens += 4 + len(encoding.encode(content))
    print(f"Tokens: {num_tokens}")
    return num_tokens

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

language_extension_map = {
    'python': '.py',
    'shell': '.sh',
    'text': '.txt',
    'markdown': '.md',
    'html': '.html',
    'css': '.css',
    'javascript': '.js',
    'json': '.json',
    'yaml': '.yaml',
    'c': '.c',
    'cpp': '.cpp',
    'rust': '.rs',
}

inverse_kv_map = lambda d: {v: k for k, v in d.items()}