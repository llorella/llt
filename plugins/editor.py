# plugins/editor.py
import os
import subprocess
import difflib
import pyperclip
from typing import List, Dict

from plugins import plugin
from utils.helpers import path_input, get_valid_index
from utils.md_parser import parse_markdown_for_codeblocks, language_extension_map
from utils.file_diff import generate_diff, prompt_and_write_file


DEFAULT_EDITOR = "vim"

@plugin
def edit(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    1. Determine a project_exec_dir (based on args.load).
    2. Parse code blocks from the selected message.
    3. For each code block, guess the filename, show a diff with what's on disk, ask user if they want to write.
    4. Summarize in a final message.
    """
    if not args.load:
        # If no session loaded, put them in exec_dir/untitled
        project_exec_dir = path_input(os.path.join(args.exec_dir, "untitled"), os.getcwd())
    else:
        # Derive subpath from the ll path basename
        ll_dir_abs = os.path.abspath(args.ll_dir)
        load_abs = os.path.abspath(args.load)
        rel = os.path.relpath(load_abs, ll_dir_abs)  # e.g. "project/subdir.ll"

        base, ext = os.path.splitext(rel)
        if ext == ".ll":
            rel = base
        project_exec_dir = path_input(os.path.join(args.exec_dir, rel), os.getcwd())

    os.makedirs(project_exec_dir, exist_ok=True)

    msg_index = get_valid_index(messages, "edit code block of", index)
    content = messages[msg_index]["content"]

    code_blocks = parse_markdown_for_codeblocks(content)

    modified_files = []
    skipped_files = []

    for block in code_blocks:
        language = block["language"]
        block_content = block["content"]
        filename = block["filename"] or f"untitled.{language_extension_map.get(language,'txt')}"

        final_path = os.path.join(project_exec_dir, filename)
        old_content = ""
        if os.path.isfile(final_path):
            try:
                with open(final_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            except Exception as e:
                print(f"Failed to read existing file {final_path}: {e}")
                skipped_files.append(final_path)
                continue

        diff_text = generate_diff(old_content, block_content, filename)
        did_write = prompt_and_write_file(final_path, block_content, diff_text)
        if did_write:
            modified_files.append(filename)
        else:
            skipped_files.append(filename)

    summary = []
    if modified_files:
        summary.append(f"Modified/Created: {modified_files}")
    if skipped_files:
        summary.append(f"Skipped: {skipped_files}")
    if not summary:
        summary.append("No changes were applied.")

    summary_msg = "Edit operation complete.\n" + "\n".join(summary)
    messages.append({"role": "assistant", "content": summary_msg})

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
