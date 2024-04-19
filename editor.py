import os
import subprocess
import time
import base64

from message import Message, view_message
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

def save_or_edit_code_block(filename: str, code: str, editor: str, mode: str = 'w') -> None:
    if editor:
        copy_to_clipboard(code)
        subprocess.run([editor, filename], check=True)
    else:
        with open(filename, mode) as file:
            file.write(code.strip())

def handle_code_block(code_block: dict, dir_path: str, editor: str) -> str:
    print(f"File: {code_block['filename']}")
    print(f"Code: \n{code_block['code']}")
    action = input(
        "Write to file (w), edit (e), append (a), or skip (s)? ").strip().lower()
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
    elif action == 'a':
        filename = os.path.join(
            dir_path,
            path_input(
                code_block['filename'],
                dir_path))
        save_or_edit_code_block(
            filename,
            code_block['code'],
            None,
            'a')
        return f"{filename} appended."
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

def edit_content_message(messages: list[Message], args: dict, index: int = -1) -> list[Message]:
    if not messages:
        print("No messages to edit.")
        return messages
    message_index = int(input(f"Enter index of previous message to edit (default is {index}, -2 for last message): ") or index)
    message = messages[message_index]
    print(f"Messages[{message_index}] content: {message['content']}")
    action = input("Choose an action: (o)verwrite, (a)ppend, or (e)dit previous message? ").strip().lower()
    if action == 'o':
        new_content = content_input()
        message['content'] = new_content
    elif action == 'a':
        print("Appending to previous message content...")
        new_content = content_input()
        message['content'] += ' ' + new_content
    elif action == 'e':
        temp_file = "tmp.txt"
        with open(temp_file, 'w') as f:
            f.write(message['content'])

        subprocess.run(['vim', temp_file], check=True)

        with open(temp_file, 'r') as f:
            message['content'] = f.read()

        os.remove(temp_file)
    else:
        print("Invalid action. Skipping edit.")
        return messages
    messages[message_index] = message
    view_message(messages, args, index=len(messages) - 2)
    return messages

def edit_role_message(messages: list[dict[str, any]], args: dict, index: int = -1) -> list[dict[str, any]]:
    if messages:
        index = int(input(f"Enter index of message to change role (default is {index}): ") or index)
        messages[index]['role'] = input("Enter new role: ") or args.role
    return messages

def edit_message(messages: list[Message], args: dict, index: int = -1) -> list[Message]:
    if not messages or abs(index) > len(messages)-1: return messages.append({'role': 'user', 'content': "Message edit error. Either index is out of range or no messages to edit."})
    message_index = int(input(f"Enter index of previous message to edit (default is {index}, -2 for last message): ") or index)
    message = messages[message_index]
    default_exec_dir = os.path.join(args.exec_dir, os.path.splitext(args.ll_file)[0])
    os.makedirs(default_exec_dir, exist_ok=True)
    exec_dir = path_input(default_exec_dir) if not args.non_interactive else default_exec_dir
    print(f"Extracting code from messages[{message_index}] using exec directory: {exec_dir}")
    code_blocks = extract_code_blocks(message['content'])
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
        language = inverse_kv_map(language_extension_map)[ext.lower()] if ext else None
        messages.append({'role': 'user', 'content': f'```{language}\n{data}\n```' if language else f'{data}\n'})
        return messages
    
def convert_text_base64(messages: list[Message], args: dict) -> list[Message]:
    # convert all user messages into base64 encoded text
    for message in messages:
        if message['role'] == 'user':
            message['content'] = base64.b64encode(message['content'].encode('utf-8')).decode('utf-8')
    return messages

def execute_command(messages: list[Message], args: dict, index: int = -1) -> list[Message]:
    message_index = int(input(f"Enter index of previous message to execute (default is {index}, -2 for last message): ") or index)
    code_blocks = extract_code_blocks(messages[message_index]['content'])
    for code_block in code_blocks:
        if code_block['language'] == 'bash' or code_block['language'] == 'shell' or not code_block['language']:
            print(f"Code:\n{code_block['code']}")
            if input(f"Execute {code_block['language'] or 'text'} block? (y/n): ").lower() == 'y':
                try:
                    print(f"Executing bash command from message {message_index}:")
                    result = subprocess.run(code_block['code'], 
                                            shell=True, 
                                            check=True, 
                                            stdout=subprocess.PIPE, 
                                            stderr=subprocess.PIPE,
                                            universal_newlines=True)
                    print("Command output:")
                    print(result.stdout)
                except subprocess.CalledProcessError as e:
                    print(f"Error executing command: {e}")
                    print("Error details:")
                    print(e.stderr)
            else:
                print("Skipping code block execution.")
        else:
            print(f"Skipping code block with language: {code_block['language']}. Only 'bash' or 'shell' code blocks are executed.")
            
    return messages