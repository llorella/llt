import os
import re
import subprocess
import tempfile
from typing import List, Tuple, Optional, Dict
from message import Message
from utils import user_input_file
#markdown format
code_block_pattern = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)

extension_map: Dict[str, str] = {
    'python': 'py',
    'bash': 'sh',
    'cpp': 'cpp',
    'javascript': 'js',
    'text': 'txt',
}

def get_language_extension(language: str) -> Optional[str]:
    return extension_map.get(language, 'txt')

def extract_code_blocks(content: str) -> List[Tuple[str, str]]:
    #extract code blocks and their respective languages from the content
    return code_block_pattern.findall(content)

def save_code_blocks(code_blocks: List[Tuple[str, str]], save_dir: str = '.llt') -> List[str]:
    filenames = []
    for idx, (language, code) in enumerate(code_blocks, 1):
        print(f"type: {language}")
        print(f"code: \n\n{code}\n\n")
        file = input("Enter filename (default is code_block_idx): ") or f"code_block_{idx}"
        filename = f"{save_dir}/{file}.{get_language_extension(language)}"
        print(f"filename: {filename}")
        with open(filename, 'w') as file:
            file.write(code.strip())
        filenames.append(filename)
    return filenames

def edit_source(filename: str, editor: str = 'vim') -> None:
    if not os.path.isfile(filename):
        print(f"Error: File '{filename}' does not exist.")
        return
    edit_command = f"{editor} {filename}"
    subprocess.run(edit_command, check=True, shell=True)

def edit_message(messages: List[Message], file: Optional[str]) -> List[Message]:
    if not messages:
        print("No messages available to edit.")
        return messages

    last_message = messages[-1]
    code_blocks = extract_code_blocks(last_message['content'])
    if not code_blocks:
        print("No code block found in the last message.")
        return messages

    save_dir = os.path.join(os.path.expanduser('~'), '.llt')
    filenames = save_code_blocks(code_blocks, save_dir)
    for filename in filenames:
        edit_source(filename)

    return messages

def include_file(messages: List[Message], args: Optional[Dict]) -> List[Message]:
    file_path = user_input_file() or args.content_file
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

    
