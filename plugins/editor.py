# plugins/editor.py
import os
import subprocess
import pyperclip # type: ignore
import json
from typing import List, Dict, Optional, Callable, Iterator, Union, Tuple
from pathlib import Path

from plugins import plugin
from utils.input_utils import path_input, get_valid_index, confirm_action
from utils.colors import Colors
from utils.md_parser import (
    parse_markdown_for_codeblocks,
    language_extension_map,
    detect_language_from_content
)
from utils.diff import generate_diff, format_diff
from utils.tempfile_manager import TempFileManager
from utils.backup_manager import BackupManager
from utils.helpers import encode_image_to_base64, content_input
from utils.gitignore import get_gitignore_patterns, should_ignore


temp_manager = TempFileManager()
backup_manager = BackupManager()

def iter_blocks(
    message: Dict,
    predicate: Optional[Callable] = None,
    transform: Optional[Callable] = None
) -> Iterator[Dict]:
    """Iterate through code blocks with optional filtering and transformation."""
    blocks = parse_markdown_for_codeblocks(message["content"])
    for block in blocks:
        if predicate is None or predicate(block):
            yield transform(block) if transform else block

def execute_code(code: str, language: str, timeout: int = 30) -> str:
    """Execute code with safety measures."""
    runners = {
        "python": ["python3", "-c"],
        "bash": ["bash", "-c"],
        "node": ["node", "-e"],
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

@plugin
def execute_by_language(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Execute code blocks of specified language."""
    msg_index = get_valid_index(messages, "execute code blocks from", index)
    target_lang = getattr(args, 'lang', None) or input("Enter language to execute: ").strip()
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
                if output := execute_code(block["content"], target_lang, timeout):
                    results.append(f"Output of block {block['index'] + 1}:\n{output}")
            except Exception as e:
                results.append(f"Error in block {block['index'] + 1}: {str(e)}")

    if results:
        messages.append({
            "role": "assistant",
            "content": "\n\n".join(results)
        })
    return messages

@plugin
def apply_changes(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Write code blocks to files with smart handling."""
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
        
        if not force:
            filename = path_input(default_name)
        else:
            filename = default_name
            
        filepath = Path(filename)
        
        # Handle existing files
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
        "role": "assistant",
        "content": "\n".join(summary)
    })
    return messages

@plugin
def extract_blocks(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Extract and manipulate code blocks."""
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
            "role": "assistant",
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
        "role": "assistant",
        "content": content
    })
    return messages

@plugin
def content(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Edit message content in external editor."""
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

@plugin
def paste(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Paste clipboard content as new user message."""
    messages.append({
        "role": "user",
        "content": pyperclip.paste()
    })
    return messages

@plugin
def copy(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Copy message content to clipboard."""
    if not messages:
        print("No messages to copy.")
        return messages
        
    msg_index = get_valid_index(messages, "copy", index) if index != -1 else -1
    
    if getattr(args, 'blocks', False):
        lang_filter = getattr(args, 'lang', None)
        blocks = list(iter_blocks(
            messages[msg_index],
            predicate=lambda b: not lang_filter or b["language"] == lang_filter
        ))
        if blocks:
            content = "\n\n".join(b["content"] for b in blocks)
            pyperclip.copy(content)
            print(f"Copied {len(blocks)} code blocks to clipboard.")
        else:
            print("No matching code blocks found.")
    else:
        pyperclip.copy(messages[msg_index]["content"])
        print("Copied message to clipboard.")
        
    return messages

def process_file(
    file_path: Union[str, Path], 
    model: str,
    prompt: str = "",
    role: str = "user"
) -> Tuple[Dict, bool]:
    """
    Process a file and return appropriate message format based on file type.
    Returns (message_dict, success_bool)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return None, False

    ext = file_path.suffix.lower()
    
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        try:
            encoded_image = encode_image_to_base64(str(file_path))
            
            if model.startswith("claude"):
                return {
                    "role": role,
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": f"image/{ext[1:]}",
                                "data": encoded_image,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }, True
            elif model.startswith("gpt-4"):
                return {
                    "role": role,
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{ext[1:]};base64,{encoded_image}"
                            },
                        },
                    ],
                }, True
            else:
                return None, False
                
        except Exception as e:
            print(f"Failed to process image {file_path}: {e}")
            return None, False
    
    # Handle text files
    try:
        content = file_path.read_text()
        if ext in language_extension_map:
            content = f"# {file_path.name}\n```{language_extension_map[ext]}\n{content}\n```"
        return {"role": role, "content": content}, True
    except Exception as e:
        print(f"Failed to read file {file_path}: {e}")
        return None, False

@plugin
def file_include(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Enhanced file inclusion with support for:
    - Multiple files (glob patterns)
    - .gitignore respect
    - Image handling for specific models
    - Automatic language detection
    - Directory traversal
    """
    paths = []
    if getattr(args, 'file', None):
        paths = [Path(args.file)]
    elif getattr(args, 'glob', None):
        paths = list(Path().glob(args.glob))
    else:
        file_path = path_input(None, os.getcwd())
        paths = [Path(file_path)]

    if not paths:
        print("No files specified")
        return messages

    ignore_patterns = None
    if getattr(args, 'respect_gitignore', True):
        ignore_patterns = get_gitignore_patterns()

    role = getattr(args, 'role', 'user')
    # for image handling differences
    model = getattr(args, 'model', 'claude')
    prompt = getattr(args, 'prompt', '') if getattr(args, 'non_interactive', False) else content_input()
    
    successful = 0
    failed = 0

    for path in paths:
        if ignore_patterns and should_ignore(str(path), ignore_patterns):
            print(f"Skipping {path} (matches gitignore)")
            continue

        if path.is_dir() and getattr(args, 'recursive', False):
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    message, success = process_file(file_path, model, prompt, role)
                    if success:
                        messages.append(message)
                        successful += 1
                    else:
                        failed += 1
        elif path.is_file():
            message, success = process_file(path, model, prompt, role)
            if success:
                messages.append(message)
                successful += 1
            else:
                failed += 1

    print(f"Processed {successful} files successfully, {failed} failed")
    return messages