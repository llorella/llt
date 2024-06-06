import os
import subprocess
import time
import base64
from typing import List, Dict
import pyperclip

from message import Message
from utils import path_input, content_input, language_extension_map, inverse_kv_map, get_valid_index, encode_image

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

import re
code_block_pattern = re.compile(r'```(\w+)\n(.*?)\n```', re.DOTALL)  

def extract_code_blocks(content: str) -> List[Dict]:
    matches = code_block_pattern.findall(content)
    code_blocks = []
    for language, code in matches: code_blocks.append({'language': language, 'code': code})
    return code_blocks

from plugins import plugin

@plugin
def paste_content(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    paste = pyperclip.paste()
    messages.append(Message(role='user', content=paste))
    return messages

@plugin
def copy_content(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    copy_to_clipboard(messages[-1]['content'])
    return messages

@plugin
def edit_content(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
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
def code_message(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    default_exec_dir = os.path.join(args.exec_dir, os.path.splitext(args.ll)[0])
    # We create a directory for execution files that corresspond to an ll thread. The kernel of some 'agent' space for navigating a file system.
    os.makedirs(default_exec_dir, exist_ok=True)
    exec_dir = path_input(default_exec_dir) if not args.non_interactive else default_exec_dir
    # use descriptive handlers for code blocks
    message_index = get_valid_index(messages, "edit code block of", index)
    code_blocks = extract_code_blocks(messages[message_index]['content'])
    messages.append(Message(role='user', content='\n'.join([
        handle_code_block(code_block, exec_dir)
        for code_block in code_blocks
    ])))
    return messages


@plugin
def include_file(messages: List[Message], args: Dict) -> List[Message]:
    if args.non_interactive: file_path = args.file # don't ask user, just use the file path
    else: file_path = path_input(args.file, os.getcwd()) # ask user for file path, in interactive mode
    (_, ext) = os.path.splitext(file_path)
    if ext in image_exts:
        messages.append(Message(role='user', content=[{"type": "text", "text": args.prompt or content_input()}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(file_path)}"}}]))
    else:
        with open(file_path, 'r') as file:
            data = file.read()
        messages.append(Message(role='user', content=data))
    return messages

@plugin
def execute_command(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "execute command of", index) if not args.non_interactive else -1
    code_blocks = extract_code_blocks(messages[message_index]['content'])
    for code_block in code_blocks:
        if code_block['language'] == 'bash' or code_block['language'] == 'shell' or not code_block['language']:
            user_action = input(f"Code:\n{code_block['code']}\nExecute (x), edit (e), or skip (any) {code_block['language'] or 'text'} block? (y/n): ").lower() 
            if user_action == 'x':
                try:
                    result = subprocess.run(code_block['code'], 
                                            shell=True, 
                                            check=True, 
                                            stdout=subprocess.PIPE, 
                                            stderr=subprocess.PIPE,
                                            universal_newlines=True)
                    messages.append(Message(role='user', content=f"{result.stdout}"))
                except subprocess.CalledProcessError as e:
                    messages.append(Message(role='user', content=f"Error executing command: {e}\nError details:\n{e.stderr}"))
            elif user_action == 'e':    
                messages.append(Message(role=args.role, content=code_block['code']+"\nCode block edited. Re-trigger command to execute."))   
                edit_content(messages, args, message_index)
    return messages