import os
import subprocess
from message import Message
from utils import path_input, content_input

def list_files(dir_path):
    return [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]

def create_directory_for_file(exec_dir: str, ll_file: str) -> str:
    dir_name = os.path.splitext(ll_file)[0]  # dir name is the same as the file name without the .ll extension
    new_dir_path = os.path.join(exec_dir, dir_name)
    if not os.path.exists(new_dir_path):  
        os.makedirs(new_dir_path)
    return new_dir_path

def copy_to_clipboard(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
        print("Code block copied to clipboard. You can paste it in the editor.")
    except ImportError:
        print("pyperclip module not found. Skipping clipboard functionality.")

def save_or_edit_code_block(filename: str, code: str, editor: str) -> None:
    if editor:
        copy_to_clipboard(code)
        subprocess.run([editor, filename], check=True)
    else:
        with open(filename, 'w') as file:
            file.write(code.strip())

def handle_code_block(code_block: dict, dir_path: str, editor: str) -> str:
    print(f"File: {code_block['filename']}")
    print(f"Type: {code_block['language']}")
    print(f"Code: \n{code_block['code']}")
    action = input("Write to file (w), skip (s), or edit (e)? ").strip().lower()
    if action in ('w', 'e'):
        filename = os.path.join(dir_path, path_input(code_block['filename'], dir_path) or code_block['filename'])
        save_or_edit_code_block(filename, code_block['code'], editor if action == 'e' else '')
        return f"{filename} changed."
    elif action == 's':
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
                    current_code_block["filename"] = lines[i - 1].lstrip(filename_marker).strip()
                _, _, language = line.partition(code_block_marker)
                current_code_block["language"] = language.strip()
                inside_code_block = True
            else:
                inside_code_block = False
                code_blocks.append(current_code_block)
                current_code_block = {"filename": "", "code": "", "language": ""}
        elif inside_code_block:

            current_code_block["code"] += line + '\n'

    return [block for block in code_blocks if block["code"].strip()]

def edit_message(messages: list[Message], args: dict) -> list[Message]:    print(f"Exec directory: {args.code_dir}"):
    # None for default path means we are asking the user for a dir path
    edit_directory = path_input(None, args.code_dir) or create_directory_for_file(args.code_dir, args.ll_file)
    code_blocks = extract_code_blocks(messages[-1]['content'])
    new_results = [handle_code_block(code_block, edit_directory, "vim") for code_block in code_blocks]
    messages.append({'role': 'user', 'content': '\n'.join(new_results)})
    return messages

def include_file(messages: list[Message], args: dict) -> list[Message]:
    file_path = os.path.expanduser(path_input(args.file_include))
    with open(file_path, 'r') as file:
        data = file.read()
    messages.append({'role': 'user', 'content': data})
    return messages

def encode_image(image_path: str) -> str:
    import base64
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def attach_image(messages: list[Message], args: dict) -> list[Message]:
    base64_image = encode_image(path_input(args.image_path))
    messages.append({"role": "user", 
        "content": [
        {"type": "text", "text": content_input()},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
    ]})
    return messages