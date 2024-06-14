import os
import subprocess
import time
import base64
from typing import List, Dict
import pyperclip
import json

from utils import path_input, content_input, get_valid_index, encode_image, language_extension_map
from plugins import plugin

input_action_string = lambda actions: 'Choose an action: ' + ', '.join([("or " if i == len(actions)-1 else "") + f"{action} ({action[0]})" for i, action in enumerate(actions)]) + '?'
default_editor = 'vim'
temp_file = 'tmp.txt'
image_exts = ['.png', '.jpg', '.jpeg']

def copy_to_clipboard(text: str) -> None:
    try:
        pyperclip.copy(text)
    except ImportError:
        print("pyperclip module not found. Skipping clipboard functionality.")

def list_files(dir_path):
    return [    
        f for f in os.listdir(dir_path) if os.path.isfile(
            os.path.join(
                dir_path,
                f))]

def save_code_block(filename: str, code: str, mode: str = 'w') -> str:
    if mode == 'e':
        if code: copy_to_clipboard(code)
        subprocess.run([default_editor, filename], check=True)
        # todo: some kind of diff tool to show changes and return to code block handler for logging
        return f'{filename} edited.'
    elif mode in ['a', 'w']:
        with open(filename, mode) as file:
            file.write(code.strip())
        return f'Code block written to {filename}'
    else: return 'No changes made.'

def handle_code_block(code_block: Dict, dir_path: str) -> str:
    action = input(f"Language: {code_block['language']}\nCode: \n{code_block['code']}\n{input_action_string(['write', 'edit', 'append', 'copy'])}\n").strip().lower()
    if action in ('w', 'e', 'a'):
        filename = os.path.join(dir_path, path_input("", dir_path))  
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        return save_code_block(filename, code_block['code'], action)
    elif action == 'c':
        copy_to_clipboard(code_block['code'])
        return 'Copied code block to clipboard.'
    return "Skipped."

code_block = lambda code, language: f"```{language}\n{code}\n```"

@plugin
def wrap_in_code_block(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    message_index = get_valid_index(messages, "wrap in code block", index)
    file_path = path_input(args.file, os.getcwd())
    base, ext = os.path.splitext(file_path)
    if ext in language_extension_map: language = language_extension_map[ext]
    else: language = None
    with open(file_path, 'r') as file:
        data = file.read()
        messages.append({'role': 'user', 'content': code_block(data, language)})
    return messages

import re
code_block_pattern = re.compile(r'```(\w+)\n(.*?)\n```', re.DOTALL)  

def extract_code_blocks(content: str) -> List[Dict]:
    matches = code_block_pattern.findall(content)
    code_blocks = []
    for language, code in matches: code_blocks.append({'language': language, 'code': code})
    return code_blocks

def run_code_block(code_block: Dict) -> str:
    language, code = code_block['language'], code_block['code']
    result = None
    args = [], shell = False
    try:
        if language in ['bash', 'shell']: args = [code], shell = True
        elif language == 'python': args = ['python3', '-c', code]
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
    return result

@plugin
def edit(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    ll_file = args.load if args.load else os.path.join(args.ll_dir, "default.ll")
    default_exec_dir = os.path.join(args.exec_dir, os.path.splitext(args.ll)[0])
    os.makedirs(default_exec_dir, exist_ok=True)
    exec_dir = path_input(default_exec_dir) if not args.non_interactive else default_exec_dir
    message_index = get_valid_index(messages, "edit code block of", index)
    messages.append({'role': 'user', 'content': '\n'.join([
        handle_code_block(code_block, exec_dir)
        for code_block in extract_code_blocks(messages[message_index]['content'])
    ])})
    return messages

@plugin 
def paste(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    paste = pyperclip.paste()
    messages.append({'role': 'user', 'content': paste})
    return messages

@plugin
def copy(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    copy_to_clipboard(messages[-1]['content'])
    return messages

@plugin
def content(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    message_index = get_valid_index(messages, "edit content of", index) if not args.non_interactive else index # prompt is any valid verb that precedes the preposition
    action = input(f"{input_action_string(['edit', 'append', 'copy'])}").strip().lower()
    if action in ('e', 'a'):
        with open(temp_file, 'w') as f:
            f.write(messages[message_index]['content'])
        save_code_block(temp_file, None, 'e')
        messages[message_index]['content'] = open(temp_file).read()
        os.remove(temp_file)
    elif action == 'c':
        copy_to_clipboard(messages[message_index]['content'])
    return messages

@plugin
def file_include(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    if args.non_interactive: file_path = args.file # don't ask user, just use the file path
    else: file_path = path_input(args.file, os.getcwd()) # ask user for file path, in interactive mode
    (_, ext) = os.path.splitext(file_path)
    if ext in image_exts:
        messages.append({'role': 'user', 'content': [{'type': "text", 'text': args.prompt or content_input()}, 
                                                     {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(file_path)}"}}]})
    else:
        with open(file_path, 'r') as file:
            data = file.read()
        messages.append({'role': 'user', 'content': data})
    return messages
                
@plugin
def execute_command(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    message_index = get_valid_index(messages, "execute command of", index) if not args.non_interactive else -1
    code_blocks = extract_code_blocks(messages[message_index]['content'])
    results = []
    for code_block in code_blocks:
        output = run_code_block(code_block)
        result = { 'language': code_block['language'], 'code': code_block['code'], 'output': output }
        results.append(json.dumps(result), indent=2)
    messages.append({'role': 'user', 'content': '\n'.join(results)})