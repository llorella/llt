import os
import subprocess
from message import Message
from utils import file_input

def create_directory_for_file(exec_dir: str, ll_file: str) -> str:
    dir_name = os.path.splitext(ll_file)[0]  # Remove the .ll extension from the file name
    new_dir_path = os.path.join(exec_dir, dir_name)
    if not os.path.exists(new_dir_path):  # Create the directory only if it doesn't already exist
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
        filename = os.path.join(dir_path, code_block['filename'] or file_input())
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
                # Check if previous line contains the filename marker
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

def edit_message(messages: list[Message], args: dict) -> list[Message]:
    print(f"Exec directory: {args.exec_dir}")
    args.exec_dir = file_input(args.exec_dir) or args.exec_dir
    edit_directory = create_directory_for_file(args.exec_dir, args.context_file)
    code_blocks = extract_code_blocks(messages[-1]['content'])
    results = [handle_code_block(code_block, edit_directory, "vim") for code_block in code_blocks]
    print(results)
    return messages

def include_file(messages: list[Message], args: dict) -> list[Message]:
    file_path = os.path.expanduser(file_input())
    with open(file_path, 'r') as file:
        data = file.read()
    messages.append({'role': 'user', 'content': data})
    return messages

def encode_image(image_path: str) -> str:
    import base64
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def attach_image(messages: list[Message], args: dict) -> list[Message]:
    image_input = input(f"{args['file']} is your current file. Change? (Enter for no, Type to change): ")
    if image_input:
        args['file'] = image_input
    base64_image = encode_image(args['file'])
    messages[-1]['content'] = [
        {"type": "text", "text": messages[-1]['content']},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
    ]
    return messages