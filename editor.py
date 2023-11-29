import os
import re
import subprocess
import tempfile
from typing import List, Tuple, Optional, Dict
from message import Message

# Pre-compiled regex pattern for performance
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
    """Extract code blocks and their respective languages from the content."""
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
