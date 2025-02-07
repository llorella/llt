# plugins/editor.py
import os
import subprocess
import pyperclip  # type: ignore
import json
from typing import List, Dict, Optional, Callable, Iterator, Union
from pathlib import Path

from plugins import llt
from utils import path_input, get_valid_index, confirm_action
from utils import Colors
from utils import (
    parse_markdown_for_codeblocks,
    language_extension_map,
    detect_language_from_content
)
from utils import generate_diff, format_diff
from utils import TempFileManager
from utils import BackupManager
from utils import encode_image_to_base64, content_input, list_input
from utils import get_project_dir

temp_manager = TempFileManager()
backup_manager = BackupManager()


def iter_blocks(
    message: Dict,
    predicate: Optional[Callable] = None,
    transform: Optional[Callable] = None
) -> Iterator[Dict]:
    """
    Iterate through code blocks in a given message with optional filtering/transform.
    """
    blocks = parse_markdown_for_codeblocks(message["content"])
    for block in blocks:
        if not predicate or predicate(block):
            yield transform(block) if transform else block


def execute_code(code: str, language: str, timeout: int = 30) -> str:
    """
    Execute code in a subprocess, capturing stdout/stderr.
    """
    runners = {
        "python": ["python3", "-c"],
        "bash": ["bash", "-c"],
        "javascript": ["node", "-e"],
        "typescript": ["bun"],
        "ruby": ["ruby", "-e"],
        "shell": ["bash", "-c"]
    }
    if language not in runners:
        raise ValueError(f"Unsupported language: {language}")

    with temp_manager.temp_file(suffix=f".{language}", content=code) as temp_path:
        try:
            proc = subprocess.run(
                [*runners[language], code],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            output = proc.stdout
            if proc.stderr:
                output += f"\nErrors:\n{proc.stderr}"
            return output.strip()
        except subprocess.TimeoutExpired:
            return f"Execution timed out after {timeout} seconds"


@llt
def execute(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Execute code blocks by language
    Type: bool
    Default: false
    flag: execute
    short:
    """
    msg_index = get_valid_index(messages, "execute code blocks from", index)
    target_lang = getattr(args, 'lang', None) or list_input(language_extension_map.keys(), "Enter a language: ").strip()
    timeout = int(getattr(args, 'timeout', 30))

    results = []
    blocks = iter_blocks(
        messages[msg_index],
        predicate=lambda b: b["language"] == target_lang
    )

    for block in blocks:
        print(f"\nCode block {block['index'] + 1}:")
        Colors.print_colored(block["content"], Colors.CYAN)

        if getattr(args, 'all', False) or confirm_action("Execute this block?"):
            try:
                output = execute_code(block["content"], target_lang, timeout)
                if output:
                    results.append(f"Output of block {block['index'] + 1}:\n{output}")
            except Exception as e:
                results.append(f"Error in block {block['index'] + 1}: {str(e)}")

    if results:
        messages.append({
            "role": args.role,
            "content": "\n\n".join(results)
        })
    return messages


@llt
def edit(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Edit code blocks in messages at project root path
    Type: bool
    Default: false
    flag: edit
    short:
    """
    msg_index = get_valid_index(messages, "write code blocks from", index)
    lang_filter = getattr(args, 'lang', None)
    create_backups = getattr(args, 'backup', True)
    show_diff = not getattr(args, 'no_diff', False)
    force = getattr(args, 'force', False)

    modified = []
    skipped = []

    for block in iter_blocks(
        messages[msg_index],
        predicate=lambda b: not lang_filter or b["language"] == lang_filter
    ):
        print(f"\n{block['language']} block:")
        Colors.print_colored(block["content"], Colors.CYAN)

        suggested_ext = language_extension_map.get(block["language"], ".txt")
        default_name = block["filename"] or f"block_{block['index']}{suggested_ext}"

        filename = path_input(default_name, get_project_dir(args))
        filepath = Path(filename)

        if filepath.exists():
            if create_backups:
                backup_manager.create_backup(str(filepath))

            if show_diff:
                old_content = filepath.read_text()
                diff = generate_diff(old_content, block["content"])
                print("\nChanges to be applied:")
                print(format_diff(diff))

            if force or confirm_action("Write changes?"):
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(block["content"])
                modified.append(str(filepath))
            else:
                skipped.append(str(filepath))
        else:
            if force or confirm_action(f"Create new file {filepath}?"):
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(block["content"])
                modified.append(str(filepath))
            else:
                skipped.append(str(filepath))

    summary = ["File operations complete."]
    if modified:
        summary.append("Modified/Created:")
        summary.extend(f"  - {f}" for f in modified)
    if skipped:
        summary.append("Skipped:")
        summary.extend(f"  - {f}" for f in skipped)

    messages.append({
        "role": args.role,
        "content": "\n".join(summary)
    })
    return messages


@llt
def extract_blocks(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Extract and manipulate code blocks
    Type: bool
    Default: false
    flag: extract_blocks
    short:
    """
    msg_index = get_valid_index(messages, "extract blocks from", index)
    lang_filter = getattr(args, 'lang', None)
    should_detect = getattr(args, 'detect', True)

    def process_block(block: Dict) -> Dict:
        if should_detect and not block["language"]:
            block["language"] = detect_language_from_content(block["content"]) or "text"
        return block

    blocks = list(iter_blocks(
        messages[msg_index],
        predicate=lambda b: not lang_filter or b["language"] == lang_filter,
        transform=process_block
    ))

    if not blocks:
        messages.append({
            "role": args.role,
            "content": "No matching blocks found."
        })
        return messages

    output_format = getattr(args, 'format', 'markdown')
    if getattr(args, 'merge', False):
        merged = "\n\n".join(b["content"] for b in blocks)
        if output_format == 'json':
            content = json.dumps({"content": merged}, indent=2)
        elif output_format == 'markdown':
            content = f"```{blocks[0]['language']}\n{merged}\n```"
        else:
            content = merged
    else:
        if output_format == 'json':
            content = json.dumps([{
                "language": b["language"],
                "content": b["content"],
                "filename": b["filename"],
                "index": b["index"]
            } for b in blocks], indent=2)
        elif output_format == 'markdown':
            content = "\n\n".join(
                f"```{b['language']}\n{b['content']}\n```"
                for b in blocks
            )
        else:
            content = "\n\n".join(b["content"] for b in blocks)

    messages.append({
        "role": args.role,
        "content": content
    })
    return messages


@llt
def content(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Edit message content in external editor
    Type: bool
    Default: false
    flag: content
    short:
    """
    if not messages:
        print("No messages to edit.")
        return messages

    msg_index = get_valid_index(messages, "edit content of", index)
    editor = getattr(args, 'editor', None) or os.environ.get("EDITOR", "vim")

    with temp_manager.temp_file(suffix=".md", content=messages[msg_index]["content"]) as temp_path:
        try:
            subprocess.run([editor, temp_path], check=True)
            with open(temp_path) as f:
                new_content = f.read()

            if new_content != messages[msg_index]["content"]:
                if getattr(args, 'backup', True):
                    backup_manager.create_backup(temp_path)
                messages[msg_index]["content"] = new_content

        except Exception as e:
            Colors.print_colored(f"Error editing content: {e}", Colors.RED)

    return messages


@llt
def paste(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Paste clipboard content as new user message
    Type: bool
    Default: false
    flag: paste
    short:
    """
    messages.append({
        "role": "user",
        "content": pyperclip.paste()
    })
    return messages


@llt
def copy(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Copy message content to clipboard
    Type: bool
    Default: false
    flag: copy
    short:
    """
    if not messages:
        print("No messages to copy.")
        return messages

    if not args.non_interactive:
        index = get_valid_index(messages, "copy", index)

    if getattr(args, 'blocks', False):
        lang_filter = getattr(args, 'lang', None)
        blocks = list(iter_blocks(
            messages[index],
            predicate=lambda b: not lang_filter or b["language"] == lang_filter
        ))
        if blocks:
            content = "\n\n".join(b["content"] for b in blocks)
            pyperclip.copy(content)
            print(f"Copied {len(blocks)} code blocks to clipboard.")
        else:
            print("No matching code blocks found.")
    else:
        pyperclip.copy(messages[index]["content"])
        print("Copied message to clipboard.")

    return messages


@llt
def file_include(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Include file content (including images) into the conversation
    Type: string
    Default: None
    flag: file
    short: f
    """
    if not args.file or not args.non_interactive:
        file_path = path_input(args.file, os.getcwd())
    else:
        file_path = args.file

    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return messages

    _, ext = os.path.splitext(file_path)
    if ext.lower() in [".png", ".jpeg", ".jpg", ".gif", ".webp"]:
        prompt = args.prompt if args.non_interactive else content_input()
        try:
            encoded_image = encode_image_to_base64(file_path)
        except Exception as e:
            print(f"Failed to encode image: {e}")
            return messages

        if args.model.startswith("claude"):
            messages.append({
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
                    {"type": "text", "text": prompt},
                ],
            })
        elif args.model.startswith("gpt-4"):
            messages.append({
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
            })
        else:
            print("Unsupported model for image inclusion.")
            return messages
    else:
        with open(file_path, "r") as file:
            data = file.read()
        if ext.lower() in language_extension_map:
            data = f"# {os.path.basename(file_path)}\n```{language_extension_map[ext.lower()]}\n{data}\n```"
        messages.append({"role": args.role, "content": data})

    setattr(args, 'file', None)
    return messages
