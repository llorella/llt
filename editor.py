import os
import subprocess
import base64

from message import Message
from utils import path_input, content_input, language_extension_map, inverse_kv_map, encode_image, supported_images

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
    action = input(
        "Write to file (w), skip (s), or edit (e)? ").strip().lower()
    if action in ('w', 'e'):
        filename = os.path.join(
            dir_path,
            path_input(
                code_block['filename'],
                dir_path))
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        save_or_edit_code_block(
            filename,
            code_block['code'],
            editor if action == 'e' else '')
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

temp_file = "tmp.txt"

def previous_message_content_edit(messages: list[Message], args: dict):
    if (os.path.exists(temp_file)):
        os.truncate(temp_file, 0)
    if not messages:
        msg = Message(role="user", content="# This message should be edited.")
        messages.append(msg)
    save_or_edit_code_block(temp_file, messages[-1]['content'], "vim")
    with open(temp_file, "r") as content:
        messages[-1]['content'] = content.read()
    os.close(content)  
    return messages

def edit_message(messages: list[Message], args: dict) -> list[Message]:
    default_exec_dir = os.path.join(args.exec_dir, os.path.splitext(args.ll_file)[0])
    os.makedirs(default_exec_dir, exist_ok=True)
    exec_dir = path_input(default_exec_dir, args.exec_dir) if not args.non_interactive\
        else default_exec_dir
    print(f"Using exec directory: {os.path.basename(exec_dir)}")
    code_blocks = extract_code_blocks(messages[-1]['content'])
    new_results = [
        handle_code_block(
            code_block,
            exec_dir,
            "vim") for code_block in code_blocks]
    messages.append({'role': 'user', 'content': '\n'.join(new_results)})
    return messages

def include_file(messages: list[Message], args: dict) -> list[Message]:
    file_path = os.path.expanduser(path_input(args.file_include, os.getcwd())) if not args.non_interactive\
        else args.file_include
    (root, ext) = os.path.splitext(file_path)
    if ext == '.png' or ext == '.jpg' or ext == '.jpeg':
        print(f"Attaching image: {file_path}")
        messages.append({"role": "user", "content": [{"type": "text", "text": args.prompt or content_input()}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(file_path)}"}}]})
        return messages
    else:
        with open(file_path, 'r') as file:
            data = file.read()
        messages.append({'role': 'user', 'content': f"```{inverse_kv_map(language_extension_map)[ext.lower()] if ext else ''}\n{data}\n```"})
        return messages