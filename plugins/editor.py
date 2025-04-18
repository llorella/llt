import os
import subprocess
import pyperclip  # type: ignore
import json
from typing import List, Dict
from pathlib import Path
import traceback
import re

from message import Message
from plugins import llt
from utils import (
    Colors, get_project_dir, get_valid_index,
    confirm_action, language_extension_map,
    iter_blocks,
    temp_file, backup_manager,
    file_handler, input_handler, diff_handler,
)


def execute_code(code: str, language: str, timeout: int = 30) -> tuple[str, str]:
    """
    Execute code in a subprocess, capturing stdout/stderr.
    Returns tuple of (output, command string that was run)
    """
    runners = {
        "python": ["python3", "-c"],
        "bash": ["bash", "-c"], 
        "javascript": ["node", "-e"],
        "typescript": ["bun"],
        "ruby": ["ruby", "-e"],
        "shell": ["bash", "-c"]
    }
    
    try:
        if language not in runners:
            raise ValueError(f"Unsupported language: {language}")
        
      #  if args.get('non_interactive') and not args.get('auto'):
            # ask to cd to project dir

        with temp_file(suffix=f".{language}", content=code) as temp_path:
            try:
                cmd = [*runners[language], code]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False
                )
                output = proc.stdout
                if proc.stderr:
                    output += f"\nErrors:\n{proc.stderr}"
                return output.strip(), " ".join(cmd)
            except subprocess.TimeoutExpired:
                error_msg = f"Execution timed out after {timeout} seconds"
                return f"""Error executing code:
Type: TimeoutError
Details: {error_msg}
Language: {language}
Code:
{code}
Timeout limit: {timeout} seconds
Suggestion: Consider optimizing the code or increasing the timeout limit.""", " ".join(runners[language])
    except Exception as e:
        error_msg = f"""Error executing code:
Type: {type(e).__name__}
Details: {str(e)}
Language: {language}
Code:
{code}
Stack trace:
{traceback.format_exc()}
Possible causes:
- Invalid syntax or code structure
- Missing dependencies or runtime environment
- Insufficient permissions
- Resource constraints
Suggestions:
- Verify code syntax and structure
- Check if all required dependencies are installed
- Ensure proper runtime environment setup
- Review system permissions and resources"""
        return error_msg, " ".join(runners[language]) if language in runners else ""


@llt
def execute(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Execute code blocks by language
    Type: bool
    Default: false
    flag: execute
    short: x
    """
    target_lang = args.get('code_block')
    if not args.get('non_interactive') and not args.get('auto'):
        index = get_valid_index(messages, "execute code blocks from", index)
        target_lang = input_handler.get_list_input(list(language_extension_map.keys()), f"Enter a language (default is {target_lang})")
    else:
        target_lang = args.get('language', target_lang)

    timeout = int(args.get('timeout', 30))

    # Get all blocks with their positions in the text
    content = messages[index]["content"]
    
    # Regular expression to find code blocks - captures the entire block including ```
    pattern = r"```(\S+)\n(.*?)\n```"
    code_blocks = list(re.finditer(pattern, content, re.DOTALL))
    
    # Process blocks in reverse to avoid messing up positions
    for match in reversed(code_blocks):
        block_start, block_end = match.span()
        language = match.group(1)
        code = match.group(2).strip()
        
        # Skip blocks that don't match target language
        if target_lang and language != target_lang:
            continue
            
        print(f"\nCode block ({language}):")
        Colors.print_colored(code, Colors.CYAN)

        if args.get('auto') or (args.get('non_interactive') or confirm_action("Execute this block?")):
            try:
                output, cmd = execute_code(code, language, timeout)
                # Replace the block with its output
                content = content[:block_start] + output + content[block_end:]
            except Exception as e:
                error_msg = f"Error executing block: {str(e)}"
                Colors.print_colored(error_msg, Colors.RED)
    
    messages[index]["content"] = content
    return messages


@llt
def apply_blocks(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Edit code blocks in messages at project root path
    Type: bool
    Default: false
    flag: apply
    short: edit
    """
    msg_index = get_valid_index(messages, "write code blocks from", index)
    lang_filter = args.get('lang')
    create_backups = args.get('backup', True)
    show_diff = not args.get('no_diff', False)
    force = args.get('force', False)
    timeout = int(args.get('timeout', 30))

    modified = []
    skipped = []
    executed = []
    edited = []
    
    project_dir = get_project_dir(args)
    editor = os.environ.get("EDITOR", "vim")

    for block in iter_blocks(
        messages[msg_index],
        predicate=lambda b: not lang_filter or b["language"] == lang_filter
    ):
        print(f"\n{block['language']} block:")
        Colors.print_colored(block["content"], Colors.CYAN)

        # Special handling for bash blocks if no filename
        if block["language"] in ["bash", "shell"] and not block["filename"]:
            if force or confirm_action("Execute this bash block?"):
                try:
                    output, cmd = execute_code(block["content"], block["language"], timeout)
                    print(f"\nExecuted command: {cmd}")
                    print("\nOutput:")
                    Colors.print_colored(output, Colors.GREEN)
                    executed.append(f"Command: {cmd}")
                except Exception as e:
                    error_msg = f"Error executing bash block: {str(e)}"
                    Colors.print_colored(error_msg, Colors.RED)
                    skipped.append(f"Bash execution: {block['content'][:20]}...")
                continue

        suggested_ext = language_extension_map.get(block["language"], ".txt")
        default_name = block["filename"] or f"block_{block['index']}{suggested_ext}"

        filepath = input_handler.get_path_input(
            f"Enter filename for {block['language']} block (default is {default_name})",
            default=default_name,
            root_dir=project_dir
        )
        
        if os.path.exists(filepath):
            if create_backups:
                backup_manager.create_backup(str(filepath))

            if show_diff:
                old_content = file_handler.read(str(filepath))
                if old_content is not None:
                    diff = diff_handler.generate(old_content, block["content"])
                    print("\nChanges to be applied:")
                    print(diff_handler.format(diff))

            if force or confirm_action("Write changes?"):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                if file_handler.write(str(filepath), block["content"]):
                    modified.append(str(filepath))
                else:
                    skipped.append(str(filepath))
            else:
                skipped.append(str(filepath))
        else:
            if force or confirm_action(f"Create new file {filepath}?"):
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                if file_handler.write(str(filepath), block["content"]):
                    modified.append(str(filepath))
                else:
                    skipped.append(str(filepath))
            else:
                skipped.append(str(filepath))

    summary = ["File operations complete."]
    if modified:
        summary.append("Modified/Created:")
        summary.extend(f"  - {f}" for f in modified)
    if executed:
        summary.append("Executed:")
        summary.extend(f"  - {f}" for f in executed)
    if edited:
        summary.append("Edited:")
        summary.extend(f"  - {f}" for f in edited)
    if skipped:
        summary.append("Skipped:")
        summary.extend(f"  - {f}" for f in skipped)

    messages.append({
        "role": args.get('role', 'user'),
        "content": "\n".join(summary)
    })
    return messages

@llt
def edit_content(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
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

    if not args.get('non_interactive'):
        msg_index = get_valid_index(messages, "edit content of", index)
    else:
        msg_index = index

    editor = os.environ.get("EDITOR", "vim")

    with temp_file(suffix=".md", content=messages[msg_index]["content"]) as temp_path:
        try:
            subprocess.run([editor, temp_path], check=True)
            new_content = file_handler.read(temp_path)
            if new_content is not None and new_content != messages[msg_index]["content"]:
                if args.get('backup', True):
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
    messages.append(Message(role=args.get('role'), content=pyperclip.paste()))
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

    if not args.get('non_interactive'):
        index = get_valid_index(messages, "copy", index)

    if args.get('blocks', False):
        lang_filter = args.get('lang')
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
    if not args.get('non_interactive') and not args.get('auto'):
        file_path = input_handler.get_path_input("Enter file path to include", default=args.get('file'), root_dir=os.getcwd())
    else:
        file_path = args.get('file', None)

    if not os.path.exists(file_path):
        Colors.print_colored(f"Error: File not found at {file_path}", Colors.RED)
        return messages

    _, ext = os.path.splitext(file_path)
    if ext.lower() in [".png", ".jpeg", ".jpg", ".gif", ".webp"]:
        prompt = (args.get('prompt') if args.get('non_interactive') else input_handler.get_input("Enter prompt")) or args.get('prompt')
        try:
            encoded_image = file_handler.encode_image_to_base64(file_path)
            if not encoded_image:
                return messages
        except Exception as e:
            Colors.print_colored(f"Failed to encode image: {e}", Colors.RED)
            return messages
        
        messages.append({
            "role": "user", 
            "content": [
                {"type": "image_url", "image_url": "file://" + file_path},
                {"type": "text", "text": prompt},
            ],
        })
    else:
        content = file_handler.read(file_path)
        if content is not None:
            if ext.lower() in language_extension_map:
                content = f"```{os.path.basename(file_path)}\n{content}\n```"
            messages.append({"role": args.get('role', 'user'), "content": content})
    return messages
