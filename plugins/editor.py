# editor.py
import os
import re
import json
import subprocess
import pyperclip
from typing import List, Dict
from utils import (
    path_input, content_input, get_valid_index, 
    encode_image, language_extension_map, list_input
)
from plugins import plugin

DEFAULT_EDITOR = 'vim'
TEMP_FILE = 'tmp.txt'
IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']

def save_code_block(filename: str, code: str, mode: str = 'w') -> str:
    if mode == 'e':
        subprocess.run([DEFAULT_EDITOR, filename], check=True)
        return f'{filename} edited.'
    elif mode in ['a', 'w']:
        with open(filename, mode) as file:
            file.write(code.strip())
        return f'Code block written to {filename}'
    else:
        return 'No changes made.'

def handle_code_block(code_block: Dict, dir_path: str) -> str:
    action = input(f"Language: {code_block['language']}\nCode: \n{code_block['code']}\n"
                   f"Choose an action: write (w), edit (e), append (a), copy (c)\n").strip().lower()
    if action in ('w', 'e', 'a'):
        filename = os.path.join(dir_path, path_input("", dir_path))  
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        return save_code_block(filename, code_block['code'], action)
    elif action == 'c':
        pyperclip.copy(code_block['code'])
        return 'Copied code block to clipboard.'
    return "Skipped."

def extract_code_blocks(content: str) -> List[Dict]:
    code_block_pattern = re.compile(r'```(\w+)\n(.*?)\n```', re.DOTALL)
    matches = code_block_pattern.findall(content)
    return [{'language': language, 'code': code} for language, code in matches]

@plugin
def file_include(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    file_path = args.file if args.non_interactive else path_input("Enter file path: ", os.getcwd())
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return messages

    _, ext = os.path.splitext(file_path)
    if ext.lower() in IMAGE_EXTS:
        prompt = args.prompt if args.non_interactive else content_input()
        messages.append({
            'role': 'user',
            'content': [
                {'type': "text", 'text': prompt},
                {"type": "image_url", "image_url": {"url": f"file://{os.path.abspath(file_path)}"}}
            ]
        })
    else:
        with open(file_path, 'r') as file:
            data = file.read()

        messages.append({'role': 'user', 'content': data})
    return messages

@plugin
def encode_images(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    for idx in range(len(messages)):
       message = messages[idx]
       if isinstance(message['content'], list) and len(message['content']) == 2:
           image_url = message['content'][1]['image_url']['url']
           if image_url.startswith('file://'):
               image_path = image_url[7:]
               encoded_string = encode_image(image_path)
               message['content'][1]['image_url']['url'] = f"data:image/{os.path.splitext(image_path)[1][1:]};base64,{encoded_string}"
               print(f"Image at index {idx+1} has been base64 encoded.")
    return messages

@plugin
def edit(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    ll_path = os.path.basename(args.load)if args.load else os.path.join(args.ll_dir, "default.ll")
    default_exec_dir = os.path.join(args.exec_dir, os.path.splitext(ll_path)[0])
    os.makedirs(default_exec_dir, exist_ok=True)
    exec_dir = path_input(default_exec_dir) if not args.non_interactive else default_exec_dir
    message_index = get_valid_index(messages, "edit code block of", index)
    messages.append({'role': 'user', 'content': '\n'.join([
        handle_code_block(code_block, exec_dir)
        for code_block in extract_code_blocks(messages[message_index]['content'])
    ])})
    return messages

@plugin
def code_block(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    idx = get_valid_index(messages, "wrap in code block", index)
    content = messages[idx]['content']
    
    if args.file:
        file_path = path_input(args.file, os.getcwd())
        _, ext = os.path.splitext(file_path)
        default_language = language_extension_map.get(ext)
        with open(file_path, 'r') as file:
            content = file.read()
    else:
        default_language = None
    
    language_input = list_input(list(language_extension_map.values()), f"Select language to use (default is {default_language})")
    language = language_input if language_input else default_language
    
    messages[idx]['content'] = f"```{language}\n{content}\n```"
    return messages

@plugin
def paste(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    paste = pyperclip.paste()
    messages.append({'role': 'user', 'content': paste})
    return messages

@plugin
def copy(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    pyperclip.copy(messages[-1]['content'])
    return messages

@plugin
def content(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    message_index = get_valid_index(messages, "edit content of", index) if not args.non_interactive else index
    action = input("Choose an action: edit (e), append (a), copy (c)\n").strip().lower()
    if action in ('e', 'a'):
        with open(TEMP_FILE, 'w') as f:
            f.write(messages[message_index]['content'])
        save_code_block(TEMP_FILE, None, 'e')
        messages[message_index]['content'] = open(TEMP_FILE).read()
        os.remove(TEMP_FILE)
    elif action == 'c':
        pyperclip.copy(messages[message_index]['content'])
    return messages

@plugin
def execute_command(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    message_index = get_valid_index(messages, "execute command of", index) if not args.non_interactive else -1
    code_blocks = extract_code_blocks(messages[message_index]['content'])
    results = [run_code_block(code_block) for code_block in code_blocks]
    messages.append({'role': 'user', 'content': '\n'.join(results)})
    return messages

def run_code_block(code_block: Dict) -> str:
    language, code = code_block['language'], code_block['code']
    result = None
    args, shell = [], False
    try:
        if language in ['bash', 'shell']:
            args, shell = [code], True
        elif language == 'python':
            args = ['python3', '-c', code]
        user_confirm = input(f"Code:\n{code}\nExecute (x) or skip (any) {language} block? ").lower()
        if user_confirm == 'x':
            result = subprocess.run(args, 
                                    shell=shell,
                                    check=True, 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
    except subprocess.CalledProcessError as e:
        result = f"Error executing command: {e}\nError details:\n{e.stderr}"
    return result.stdout