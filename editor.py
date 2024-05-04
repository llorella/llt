import os
import subprocess
import time
import base64
from typing import List, Dict

from message import Message, view_message
from utils import path_input, content_input, language_extension_map, inverse_kv_map, encode_image, get_valid_index

input_action_string = lambda actions: 'Choose an action: ' + ', '.join([("or " if i == len(actions)-1 else "") + f"{action} ({action[0]})" for i, action in enumerate(actions)]) + '?'

def list_files(dir_path):
    return [    
        f for f in os.listdir(dir_path) if os.path.isfile(
            os.path.join(
                dir_path,
                f))]

def copy_to_clipboard(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
    except ImportError:
        print("pyperclip module not found. Skipping clipboard functionality.")

def save_or_edit_code_block(filename: str, code: str, editor: str = None, mode: str = 'w') -> None:
    if editor:
        copy_to_clipboard(code)
        subprocess.run([editor, filename], check=True)
    else:
        with open(filename, mode) as file:
            file.write(code.strip())

def handle_code_block(code_block: dict, dir_path: str, editor: str) -> str:
    action = input(f"File: {code_block['filename']}\nCode: \n{code_block['code']}\n{input_action_string(['write', 'edit', 'append', 'copy'])}\n").strip().lower()
    if action in ('w', 'e', 'a'):
        filename = os.path.join(dir_path, path_input(code_block['filename'], dir_path))  
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        save_or_edit_code_block(
            filename,
            code_block['code'],
            editor if (action == 'e') else '',
            action)
        return f"{filename} changed."
    elif action == 'c':
        copy_to_clipboard(code_block['code'])
        return "Copied."
    return "Skipped."
  
def extract_code_blocks(markdown_text: str) -> list[dict]:
    code_blocks = []
    inside_code_block = False
    current_code_block = {"filename": "", "code": "", "language": ""}
    code_block_marker = '```'
    filename_marker = '##'
    lines = markdown_text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith(code_block_marker):
            if not inside_code_block:
                if i > 0 and lines[i - 1].startswith(filename_marker):
                    current_code_block["filename"] = lines[i - 
                                                           1].lstrip(filename_marker).strip()
                _, _, language = line.partition(code_block_marker)
                current_code_block["language"] = language.strip()
                inside_code_block = True
            else:
                inside_code_block = False
                code_blocks.append(current_code_block)
                current_code_block = {
                    "filename": "", "code": "", "language": ""}
        elif inside_code_block:
            current_code_block["code"] += line + '\n'

    return [block for block in code_blocks if block["code"].strip()]

def edit_content(messages: list[Message], args: dict, index: int = -1) -> List[Message]:
    message_index = get_valid_index(messages, "edit content of", index) # prompt is any valid verb that precedes the preposition
    action = input(f"{input_action_string(['edit', 'append', 'copy'])}").strip().lower()
    if action in ('e', 'a'):
        with open("tmp.txt", 'w') as f:
            f.write(messages[message_index]['content'])
        save_or_edit_code_block("tmp.txt", 
                                messages[message_index]['content'], 
                                "vim" if action == 'e' else None,
                                'a')
        messages[message_index]['content'] = open("tmp.txt").read()
        os.remove("tmp.txt")
    elif action == 'c':
        copy_to_clipboard(messages[message_index]['content'])
    return messages

def code_message(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    default_exec_dir = os.path.join(args.exec_dir, os.path.splitext(args.ll)[0])
    # We create a directory for execution files that corresspond to an ll thread. The kernel of some 'agent' space for navigating a file system.
    os.makedirs(default_exec_dir, exist_ok=True)
    exec_dir = path_input(default_exec_dir) if not args.non_interactive else default_exec_dir
    # use descriptive handlers for code blocks
    message_index = get_valid_index(messages, "edit code block of", index)
    messages.append(Message(role='user', content='\n'.join([
        handle_code_block(code_block, exec_dir, "vim")
        for code_block in extract_code_blocks(messages[message_index]['content'])
    ])))
    return messages

def include_file(messages: list[Message], args: dict) -> list[Message]:
    file_path = os.path.expanduser(path_input(args.file_include, os.getcwd())) if not args.non_interactive\
        else args.file_include
    (_, ext) = os.path.splitext(file_path)
    if ext in ['.png', '.jpg', '.jpeg']:
        print(f"Attaching image: {file_path}")
        messages.append({"role": "user", "content": [{"type": "text", "text": args.prompt or content_input()}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(file_path)}"}}]})
        return messages
    else:
        with open(file_path, 'r') as file:
            data = file.read()
        language = inverse_kv_map(language_extension_map)[ext.lower()] if ext else None
        messages.append(Message(role='user', content=f'```{language}\n{data}\n```' if language else f'{data}\n'))
        return messages
    
def convert_text_base64(messages: list[Message], args: dict, index: int = -1) -> list[Message]:
    message_index = get_valid_index(messages, "convert text to base64", index)
    messages[message_index]['content'] = base64.b64encode(messages[message_index]['content'].encode('utf-8')).decode('utf-8')
    return messages

def execute_command(messages: list[Message], args: dict, index: int = -1) -> list[Message]:
    message_index = get_valid_index(messages, "execute command of", index)
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