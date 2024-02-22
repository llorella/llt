import argparse
import json
import os
import subprocess
import sys
from typing import List, Optional
from message import Message
from typing import List, Optional, Dict
from utils import file_input

def copy_to_clipboard(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
        print("Code block copied to clipboard. You can paste it in the editor.")
    except ImportError:
        print("pyperclip module not found. Skipping clipboard functionality.")

def save_or_edit_code_block(filename: str, code: str, editor: Optional[str]) -> None:
    if editor:
        copy_to_clipboard(code)
        subprocess.run([editor, filename], check=True)
    else:
        with open(filename, 'w') as file:
            file.write(code.strip())

def handle_code_block(code_block: dict, dir_path: str, editor: Optional[str]) -> str:
    print(f"File: {code_block['filename']}")
    print(f"Type: {code_block['language']}")
    print(f"Code: \n{code_block['code']}")

    action = input("Write to file (w), skip (s), or edit (e)? ").strip().lower()

    if action in ('w', 'e'):
        filename = os.path.join(dir_path, code_block['filename'] or file_input())
        save_or_edit_code_block(filename, code_block['code'], editor if action == 'e' else None)
        return f"{filename} changed."
    elif action == 's':
        return "Skipped."
    
def extract_code_blocks(markdown_text: str) -> List[dict]:
    code_blocks = []
    inside_code_block = False
    current_code_block = {"filename": "", "code": "", "language": ""}
    
    for line in markdown_text.split('\n'):
        if line.startswith("```"):
            if not inside_code_block:
                inside_code_block = True
                _, _, language = line.partition('```')
                current_code_block["language"] = language.strip()
            else:
                inside_code_block = False
                code_blocks.append(current_code_block)
                current_code_block = {"filename": "", "code": "", "language": ""}
        elif inside_code_block:
            current_code_block["code"] += line + '\n'
    
    return [block for block in code_blocks if block["code"].strip()]

def edit_message(messages: List[Message], args: Optional[str]) -> List[Message]:
    print(f"Message directory: {args.message_dir}")
    args.message_dir = file_input(args.message_dir) or args.message_dir
    code_blocks = extract_code_blocks(messages[-1]['content'])
    results = [handle_code_block(code_block, args.exec_dir, "vim") for code_block in code_blocks]
    print(results)
    return messages

def include_file(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    file_path = os.path.expanduser(file_input())
    with open(file_path, 'r') as file:
        data = file.read()
    messages.append({'role' : 'user', 'content' : data})
    return messages

def attach_image(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    image_input = input(args.file + " is your current file. Change? (enter for no, any string for yes): ")
    if image_input:
        args.file = image_input
    import base64
    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    base64_image = encode_image(args.file)   

    msg_len = len(messages)
    last_message = messages[msg_len-1]
    
    messages[msg_len-1] =  {
        "role": last_message['role'],
        "content": [
            {
            "type": "text",
            "text": last_message['content']
            },
            {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
            }
        ]
        }
        
        

    return messages

    
