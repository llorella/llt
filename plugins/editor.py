# plugins/editor.py
import os
import subprocess
import pyperclip  # type: ignore
import json
from typing import List, Dict, Optional, Callable, Iterator
from pathlib import Path
import traceback
from plugins import llt
from utils import (
    path_input,
    get_project_dir,
    
    get_valid_index,
    confirm_action,
    content_input,
    list_input,
    
    parse_markdown_for_codeblocks,
    language_extension_map,
    detect_language_from_content,
    
    generate_diff,
    format_diff,
    
    TempFileManager,
    BackupManager,
    
    encode_image_to_base64,
    
    Colors
)

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

        with temp_manager.temp_file(suffix=f".{language}", content=code) as temp_path:
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
        target_lang = list_input(language_extension_map.keys(), f"Enter a language (default is {target_lang})").strip() or target_lang

    timeout = int(args.get('timeout', 30))

    results = []
    blocks = iter_blocks(
        messages[index],
        predicate=lambda b: not target_lang or b["language"] == target_lang
    )

    for block in blocks:
        print(f"\nCode block {block['index'] + 1} ({block['language']}):")
        Colors.print_colored(block["content"], Colors.CYAN)

        if args.get('auto') or (args.get('non_interactive') or confirm_action("Execute this block?")):
            try:
                output, cmd = execute_code(block["content"], block["language"], timeout)
                if cmd:
                    results.append(f"<command>\n{cmd}\n</command>")
                if output:
                    # Format the output with code block and language
                    formatted_output = f"<output>\n{output}\n</output>"
                    results.append(formatted_output)
            except Exception as e:
                error_msg = f"Error in block {block['index'] + 1}:\n```text\n{str(e)}\n```"
                results.append(error_msg)

    if results:
        """ messages.append({
            "role": args.role,
            "content": "\n\n".join(results)
        }) 
        or, replace message with results
        """
        messages[index]["content"] = "\n\n".join(results)


    return messages #, ["xml_wrap", "content", "complete"]


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

    msg_index = get_valid_index(messages, "edit content of", index)
    editor = args.get('editor') or os.environ.get("EDITOR", "vim")

    with temp_manager.temp_file(suffix=".md", content=messages[msg_index]["content"]) as temp_path:
        try:
            subprocess.run([editor, temp_path], check=True)
            with open(temp_path) as f:
                new_content = f.read()

            if new_content != messages[msg_index]["content"]:
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
    if not args.get('file') or not args.get('non_interactive'):
        file_path = path_input(args.get('file'), os.getcwd())
    else:
        file_path = args.get('file')

    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return messages

    _, ext = os.path.splitext(file_path)
    if ext.lower() in [".png", ".jpeg", ".jpg", ".gif", ".webp"]:
        prompt = (args.get('prompt') if args.get('non_interactive') else content_input()) or args.get('prompt')
        try:
            encoded_image = encode_image_to_base64(file_path)
        except Exception as e:
            print(f"Failed to encode image: {e}")
            return messages
        
        messages.append({
            "role": "user", 
            "content": [
                {"type": "image_url", "image_url": "file://" + file_path},
                {"type": "text", "text": prompt},
            ],
        })
    else:
        with open(file_path, "r") as file:
            data = file.read()
        if ext.lower() in language_extension_map:
            data = f"# {os.path.basename(file_path)}\n```{language_extension_map[ext.lower()]}\n{data}\n```"
        messages.append({"role": args.get('role', 'user'), "content": data})

    return messages
