# editor.py
import os
import re
import base64
import subprocess
import pyperclip
from typing import List, Dict, Tuple
from pathlib import Path
import fnmatch
import difflib

from utils import (
    path_input,
    content_input,
    get_valid_index,
    encode_image_to_base64,
    language_extension_map,
    language_comment_map,
    list_input,
)
from plugins import plugin

DEFAULT_EDITOR = "vim"
TEMP_FILE = "tmp.txt"
IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]

def is_valid_filename(filename: str) -> bool:
    """
    Decide how strict to be about what's a "valid" filename. 
    Below is a simple check that it doesn't contain forbidden characters, etc.
    """
    if not filename:
        return False

    # Disallow patterns that directly match the extension map, if that’s undesired:
    if any(fnmatch.fnmatch(filename, pattern) for pattern in language_extension_map.values()):
        return False

    # Common forbidden characters on many filesystems:
    forbidden_chars = ['\0', ':', '*', '?', '"', '<', '>', '|', '\\']
    if any(char in filename for char in forbidden_chars):
        return False

    return True


def fuzzy_find_filename(line: str) -> str:
    """
    Use a regex to find something that looks like a path or filename:
        e.g., src/components/NodeControls.tsx, index.html, main.py, etc.
    This pattern looks for a string that:
      - Doesn’t have spaces or colons
      - Has at least one dot that presumably indicates an extension
    """
    filename_pattern = re.compile(r'([^\s"\':]+(\.[^\s"\':]+)+)')
    matches = filename_pattern.findall(line)
    # `matches` will be a list of tuples because of the second capturing group.
    # Example: [("src/components/NodeControls.tsx", ".tsx")]
    for full_match, _ in matches:
        if is_valid_filename(full_match):
            return full_match
    return ""


def extract_filename(code: str, language: str) -> str:
    """
    Extracts a filename from the first few lines of the code (e.g. up to 5 lines),
    assuming there's a filename inside a comment or a mention of a file path.
    """
    comment_syntax = language_comment_map.get(language, '#')
    lines = code.split('\n')

    # Check the first few lines of the code block
    max_lines_to_check = min(5, len(lines))
    for i in range(max_lines_to_check):
        line = lines[i].strip()
        
        # 1) For CSS, the comment is usually wrapped in `/* ... */`
        #    We'll handle that specifically.
        if language == 'css':
            # If it starts with /* and ends with */, strip them
            if line.startswith('/*') and line.endswith('*/'):
                # Everything between /* and */ is comment content
                comment_content = line[2:-2].strip()
                filename = fuzzy_find_filename(comment_content)
                if filename:
                    return filename

        # 2) For many others (typescript, javascript, c, etc.), single-line comments often start with `//`
        #    or the user might have chosen to place the path after the comment symbol for python (#).
        else:
            # If the line starts with the known comment syntax, remove just that syntax
            # e.g., if line is `// src/components/NodeControls.tsx`
            # we strip off `//` => `src/components/NodeControls.tsx`.
            if line.startswith(comment_syntax):
                comment_content = line[len(comment_syntax) :].strip()
                filename = fuzzy_find_filename(comment_content)
                if filename:
                    return filename

    # Fallback if no line matched
    return None


def extract_code_blocks(content: str):
    """
    Example code block extraction that uses our improved fuzzy filename detection.
    """
    code_block_pattern = re.compile(r"```(\w+)\n(.*?)\n```", re.DOTALL)
    matches = code_block_pattern.findall(content)

    blocks = []
    for language, code in matches:
        filename = extract_filename(code, language)
        blocks.append({
            "language": language,
            "content": code,
            "filename": filename
        })
    return blocks

@plugin
def edit(
    messages: List[Dict[str, any]], args: Dict, index: int = -1
) -> List[Dict[str, any]]:
    if not args.load:
        project_exec_dir = path_input(os.getcwd(), args.exec_dir)
    else:
        ll_dir_abs = os.path.abspath(args.ll_dir)
        load_abs = os.path.abspath(args.load)
        rel = os.path.relpath(load_abs, ll_dir_abs)  # e.g. "project/subdir.ll"

        base, ext = os.path.splitext(rel)
        if ext == ".ll":
            rel = base

        project_exec_dir = os.path.join(args.exec_dir, rel)
        
    os.makedirs(project_exec_dir, exist_ok=True)
    
    message_index = get_valid_index(messages, "edit code block of", index)
    code_blocks = extract_code_blocks(messages[message_index]["content"])   
    
    modified_files = []
    skipped_files = []

    # --------------------------------------------------------------------------------
    # 4. Process each item, show a diff, and ask user to overwrite/create
    # --------------------------------------------------------------------------------
    for i, item in enumerate(code_blocks):
        if not isinstance(item, dict):
            print(f"Warning: data[{i}] is not an object (dict). Skipping.")
            skipped_files.append(f"data[{i}] non-dict")
            continue

        if "filename" not in item or "content" not in item:
            print(f"Warning: data[{i}] missing required 'filename' or 'content' fields. Skipping.")
            skipped_files.append(f"data[{i}] missing fields")
            continue

        rel_filename = item["filename"]
        new_content = item["content"]
        final_path = os.path.join(project_exec_dir, rel_filename)

        # 4a. Read old content if file exists
        file_exists = os.path.exists(final_path) and os.path.isfile(final_path)
        old_content = ""
        if file_exists:
            try:
                with open(final_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            except Exception as e:
                print(f"Error reading {final_path}: {e}")
                skipped_files.append(final_path)
                continue

        # 4b. Generate unified diff (if file doesn't exist, old_content is empty string)
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=rel_filename + (" (old)" if file_exists else " (nonexistent)"),
            tofile=rel_filename + " (new)",
            lineterm=""
        )
        diff_list = list(diff)

        if not diff_list:
            # No difference
            msg = f"No changes for {rel_filename}. Skipping overwrite/creation."
            print(msg)
            skipped_files.append(rel_filename)
            continue

        # 4c. Display diff
        print(f"\n--- Diff for {rel_filename} ---")
        for line in diff_list:
            print(line, end='')
        print("\n--- End of diff ---")

        # 4d. Prompt the user
        if not file_exists:
            user_input = input(f"\nFile '{rel_filename}' does not exist in {project_exec_dir}. Create it? (y/N) ").strip().lower()
        else:
            user_input = input(f"\nOverwrite file '{rel_filename}' in {project_exec_dir}? (y/N) ").strip().lower()

        if user_input == 'y':
            try:
                os.makedirs(os.path.dirname(final_path), exist_ok=True)
                with open(final_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                msg = f"File '{rel_filename}' " + ("created" if not file_exists else "overwritten") + " successfully."
                print(msg + "\n")
                modified_files.append(rel_filename)
            except Exception as e:
                print(f"Error writing to {rel_filename}: {e}")
                skipped_files.append(rel_filename)
        else:
            action = "creation" if not file_exists else "overwrite"
            print(f"Skipped {action} of '{rel_filename}'.\n")
            skipped_files.append(rel_filename)

    # --------------------------------------------------------------------------------
    # 5. Summarize
    # --------------------------------------------------------------------------------
    summary_parts = []
    if modified_files:
        summary_parts.append(f"Modified files: {modified_files}")
    if skipped_files:
        summary_parts.append(f"Skipped files: {skipped_files}")
    if not summary_parts:
        summary_parts.append("No changes were applied.")

    summary_msg = "Apply changes operation complete.\n" + "\n".join(summary_parts)
    messages.append({"role": "assistant", "content": summary_msg})

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
    subprocess.run([DEFAULT_EDITOR, TEMP_FILE], check=True)
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
