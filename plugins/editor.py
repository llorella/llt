# editor.py
import os
import re
import base64
import subprocess
import pyperclip
from typing import List, Dict, Tuple

from utils import (
    path_input,
    content_input,
    get_valid_index,
    encode_image_to_base64,
    language_extension_map,
    list_input,
)
from plugins import plugin

DEFAULT_EDITOR = "vim"
TEMP_FILE = "tmp.txt"
IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]


def save_code_block(filename: str, code: str, mode: str = "w") -> str:
    if mode == "e":
        subprocess.run([DEFAULT_EDITOR, filename], check=True)
        return f"{filename} edited."
    elif mode in ["a", "w"]:
        with open(filename, mode) as file:
            file.write(code.strip())
        return f"Code block written to {filename}"
    else:
        return "No changes made."


def handle_code_block(code_block: Dict, dir_path: str) -> str:
    action = (
        input(
            f"Language: {code_block['language']}\nCode: \n{code_block['code']}\n"
            f"Choose an action: write (w), edit (e), append (a), copy (c)\n"
        )
        .strip()
        .lower()
    )
    if action in ("w", "e", "a"):
        filename = os.path.join(dir_path, path_input("", dir_path))
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        return save_code_block(filename, code_block["code"], action)
    elif action == "c":
        pyperclip.copy(code_block["code"])
        return "Copied code block to clipboard."
    return "Skipped."


def extract_code_blocks(content: str) -> List[Dict]:
    code_block_pattern = re.compile(r"```(\w+)\n(.*?)\n```", re.DOTALL)
    matches = code_block_pattern.findall(content)
    return [{"language": language, "code": code} for language, code in matches]


@plugin
def file_include(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    """
    Includes a file's content into the messages. If the file is an image and the model supports it,
    the image is encoded in base64 and included appropriately.
    """
    if args.file:
        file_path = args.file
        args.file = None
    else:  
        file_path = path_input(args.file, os.getcwd())
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return messages
    
    _, ext = os.path.splitext(file_path)
    if ext.lower() in IMAGE_EXTS:
        prompt = args.prompt if args.non_interactive else content_input()
        encoded_image = ""
        try:
            encoded_image = encode_image_to_base64(file_path)
        except Exception as e:
            print(f"Failed to encode image: {e}")
            return messages
        
        if args.model.startswith("claude"):
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": f"image/{ext[1:].lower()}",
                                "data": encoded_image,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        }
                    ],
                }
            )
        elif args.model.startswith("gpt-4o"):
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{ext[1:].lower()};base64,{encoded_image}"
                            },
                        },
                    ],
                }
            )
        else:
            print("Unsupported model for image inclusion.")
            return messages
    else:
        with open(file_path, "r") as file:
            data = file.read()
        if ext.lower() in language_extension_map:
            data = f"# {os.path.basename(file_path)}\n```{language_extension_map[ext.lower()]}\n{data}\n```"
        messages.append({"role": args.role, "content": data})
    
    # Clear the file argument after processing
    setattr(args, 'file', None)
    return messages


def replace_function_in_messages(
    messages: List[Dict[str, any]], function: str, new_function: str
) -> List[Dict[str, any]]:
    pass


@plugin
def edit(
    messages: List[Dict[str, any]], args: Dict, index: int = -1
) -> List[Dict[str, any]]:
    ll_path = (
        os.path.basename(args.load)
        if args.load
        else (args.exec_dir if args.exec_dir else os.getcwd())
    )
    default_exec_dir = os.path.join(args.exec_dir, os.path.splitext(ll_path)[0])
    # default exec dir is the same as ll namespace if not specified. if ll namespace is not specified, default exec dir is the current directory
    os.makedirs(default_exec_dir, exist_ok=True)
    exec_dir = (
        path_input(default_exec_dir) if not args.non_interactive else default_exec_dir
    )
    message_index = get_valid_index(messages, "edit code block of", index)
    messages.append(
        {
            "role": "user",
            "content": "\n".join(
                [
                    handle_code_block(code_block, exec_dir)
                    for code_block in extract_code_blocks(
                        messages[message_index]["content"]
                    )
                ]
            ),
        }
    )
    return messages


@plugin
def code_block(
    messages: List[Dict[str, any]], args: Dict, index: int = -1
) -> List[Dict[str, any]]:
    idx = get_valid_index(messages, "wrap in code block", index)
    content = messages[idx]["content"]

    if args.file:
        file_path = path_input(args.file, os.getcwd())
        _, ext = os.path.splitext(file_path)
        default_language = language_extension_map.get(ext)
        with open(file_path, "r") as file:
            content = file.read()
    else:
        default_language = None

    language_input = list_input(
        list(language_extension_map.values()),
        f"Select language to use (default is {default_language})",
    )
    language = language_input if language_input else default_language

    messages[idx]["content"] = f"```{language}\n{content}\n```"
    return messages


@plugin
def paste(messages: List[Dict[str, any]], args: Dict, index: int = -1)  -> List[Dict[str, any]]:
    paste = pyperclip.paste()
    messages.append({"role": "user", "content": paste})
    return messages


@plugin
def copy(messages: List[Dict[str, any]], args: Dict, index: int = -1)  -> List[Dict[str, any]]:
    pyperclip.copy(messages[-1]['content'])
    return messages


@plugin
def content(
    messages: List[Dict[str, any]], args: Dict, index: int = -1
) -> List[Dict[str, any]]:
    message_index = get_valid_index(messages, "edit content of", index)
    with open(TEMP_FILE, "w") as f:
        f.write(messages[message_index]["content"])
    save_code_block(TEMP_FILE, None, "e")
    messages[message_index]["content"] = open(TEMP_FILE).read()
    os.remove(TEMP_FILE)
    return messages


@plugin
def execute_command(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    if args.execute:
        message_index = index
        args.execute = False
        skip_check = True
    else:
        message_index = get_valid_index(messages, "execute command of", index) if not args.non_interactive else -1
        skip_check = False
    code_blocks = extract_code_blocks(messages[message_index]['content'])
    results = [run_code_block(code_block, skip_check) for code_block in code_blocks]
    
    args.xml_wrap = "command"
    messages = xml_wrap(messages, args, message_index)
    
    block_output_string = ""
    for i, result in enumerate(results):
        if result is None:
            continue
        code_block = code_blocks[i]
        block_output_string += f"{result}\n"
    messages.append(
        {"role": messages[message_index]["role"], "content": block_output_string}
    )
    args.xml_wrap = "output"
    return xml_wrap(messages, args, -1)

@plugin
def xml_wrap(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    if args.xml_wrap:
        tag_name = args.xml_wrap
        args.xml_wrap = None
    else:
        tag_name = content_input("Enter tag name (or return to use most recent message)") or messages[get_valid_index(messages, "message containing tag name", index)]['content']
        
    if tag_name:
        messages[index][
            "content"
        ] = f"<{tag_name}>\n{messages[index]['content']}\n</{tag_name}>"
    return messages


@plugin
def lines(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    lines_index = input("input line range: ")
    messages_index = get_valid_index(messages, "select message to modify lines of", -1)
    input_ranges = messages[lines_index]["content"]
    if not input_ranges:
        # error handling stderr
        print("Invalid input. Please enter a comma-separated list of line numbers.")
        return messages
    ranges: List[Tuple[int, int]] = []
    if "," in input_ranges:
        input_ranges = input_ranges.split(",")
    else:
        input_ranges = [input_ranges]

    for range in input_ranges:
        if "-" in range:
            start, end = range.split("-")
            ranges.append((int(start), int(end)))
        else:
            ranges.append((int(range), int(range)))

    if not ranges:
        print("Invalid range. Please enter a dash-separated range of line numbers.")
        return messages

    messages.pop(lines_index)

    content = messages[messages_index]["content"]
    formatted_content = ""
    lines = content.split("\n")
    formatted_content = ""
    for start, end in ranges:
        print(f"Formatting lines {start} to {end}")
        print(f"type of start: {type(start)}, end: {type(end)}")
        if start > end:
            print("Invalid range. Please enter a dash-separated range of line numbers.")
            return messages
        while start <= end:
            formatted_content += lines[start - 1] + "\n"
            start += 1

    messages.append(
        {"role": messages[messages_index]["role"], "content": formatted_content}
    )
    return messages
    # modify buffer


def run_code_block(code_block: Dict, skip_check: bool = False) -> str:
    language, code = code_block["language"], code_block["code"]
    result = None
    args, shell = [], False
    try:
        if language in ["bash", "shell"]:
            args, shell = [code], True
        elif language == 'python':
            args = ['python3', '-c', code]
        user_confirm = input(f"Code:\n{code}\nExecute (x) or skip (any) {language} block? ").lower() if not skip_check else 'x'
        if user_confirm == 'x':
            result = subprocess.run(args, 
                                    shell=shell,
                                    check=True, 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
    except subprocess.CalledProcessError as e:
        result = f"Error executing command: {e}\nError details:\n{e.stderr}"
    return result.stdout

@plugin
def strip_trailing_newline(messages: List[Dict[str, any]], args: Dict, index: int = -1)  -> List[Dict[str, any]]:
    index = get_valid_index(messages, "strip trailing newline", -1) if not args.non_interactive else -1
    messages[index]["content"] = messages[index]["content"].rstrip("\n")
    return messages
