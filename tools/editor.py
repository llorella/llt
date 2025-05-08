import os
import subprocess
import pyperclip  # type: ignore
import json
from typing import List, Dict, Any
from pathlib import Path
import traceback
import re

from message import Message
from tools import llt
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


@llt()
def execute(messages: List[Message], context: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Description: Execute code blocks by language
    Type: bool
    Default: false
    flag: execute
    short: x
    param: language string bash
    param: timeout int 30
    param: content string None
    """
    # Debug the full context to diagnose parameter passing
    print("CONTEXT: ", context)
    print(f"CONTEXT KEYS: {list(context.keys())}")
    
    # Look for execute key which should now be properly set by process_command
    execute_value = context.get("execute", {})
    print(f"EXECUTE VALUE TYPE: {type(execute_value)}")
    print(f"EXECUTE VALUE: {execute_value}")
    
    # Handle both dictionary and non-dictionary cases for execute_value
    plugin_args = {}
    if isinstance(execute_value, dict):
        plugin_args = execute_value
    
    # Debug all plugin args
    print(f"PLUGIN ARGS: {plugin_args}")
    
    # Extract direct content parameter with detailed tracing
    direct_content = None
    if 'content' in plugin_args:
        direct_content = plugin_args.get('content')
        print(f"FOUND DIRECT CONTENT: {direct_content}")
    else:
        print("NO DIRECT CONTENT FOUND IN PLUGIN ARGS")
    
    target_lang = plugin_args.get('language', 'bash')  # Default to bash for direct execution
    timeout = plugin_args.get('timeout', 30)

    if not context.get('non_interactive') and not context.get('auto'):
        index = get_valid_index(messages, "execute code blocks from", index)
        target_lang = input_handler.get_list_input(list(language_extension_map.keys()), f"Enter a language (default is {target_lang})")

    # Direct content execution path
    # Check that direct_content exists and isn't the string 'None' (default from docstring)
    if direct_content and direct_content != 'None':
        print(f"Executing direct content: {direct_content}")
        print(f"Language: {target_lang}")
        output, cmd = execute_code(direct_content, target_lang, timeout)
        print(f"\nExecuted command: {cmd}")
        print("\nOutput:")
        Colors.print_colored(output, Colors.GREEN)
        messages.append(Message(role=context.get('role', 'user'), content=output))
        return messages
    
    # Initialize content variable before processing code blocks
    try:
        content: str = messages[index]['content']
        if not isinstance(content, str):
            print(f"Warning: Message content is not a string: {type(content)}")
            return messages
    except (IndexError, KeyError):
        print(f"Error: Cannot access message at index {index}")
        return messages
    
    # Regular expression to find code blocks - captures the entire block including ```
    pattern = r"```(\S+)\n(.*?)\n```"
    code_blocks = list(re.finditer(pattern, content, re.DOTALL))
    
    # Skip further processing if no code blocks found
    if not code_blocks:
        print("No code blocks found in the message.")
        return messages
    
    # Process blocks in reverse to avoid messing up positions
    modified_content = content  # Create a working copy of the content
    blocks_executed = False
    
    for match in reversed(code_blocks):
        block_start, block_end = match.span()
        language = match.group(1)
        code = match.group(2).strip()
        
        # Skip blocks that don't match target language
        if target_lang and language != target_lang:
            continue
            
        print(f"\nCode block ({language}):")
        Colors.print_colored(code, Colors.CYAN)

        if context.get('auto') or (context.get('non_interactive') or confirm_action("Execute this block?")):
            try:
                output, cmd = execute_code(code, language, timeout)
                print(f"\nExecuted command: {cmd}")
                print("\nOutput:")
                Colors.print_colored(output, Colors.GREEN)
                # Replace the block with its output
                modified_content = modified_content[:block_start] + output + modified_content[block_end:]
                blocks_executed = True
            except Exception as e:
                error_msg = f"Error executing block: {str(e)}"
                Colors.print_colored(error_msg, Colors.RED)
    
    # Only update the message if we actually executed blocks
    if blocks_executed:
        messages[index]['content'] = modified_content
        print(f"Updated message content at index {index}")
    return messages


@llt(needs_index=True)
def apply_blocks(messages: List[Message], context: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Description: Write code blocks to files at project root path
    Type: bool
    Default: false
    flag: apply_blocks
    short: apply
    param: lang string None
    param: target string None
    param: backup bool True
    param: no_diff bool False
    param: force bool False
    param: timeout int 30
    """
    plugin_args = context.get("apply_blocks", {})
    lang_filter = plugin_args.get('lang')
    target_file = plugin_args.get('target')
    create_backups = plugin_args.get('backup', True)
    show_diff = not plugin_args.get('no_diff', False)
    force = plugin_args.get('force', False)
    timeout = plugin_args.get('timeout', 30)

    msg_index = get_valid_index(messages, "write code blocks from", index)

    modified: List[str] = []
    skipped: List[str] = []
    executed: List[str] = []
    edited: List[str] = []
    
    project_dir = get_project_dir(context)
    editor = os.environ.get("EDITOR", "vim")

    for block in iter_blocks(
        messages[msg_index],
        predicate=lambda b: (not lang_filter or b["language"] == lang_filter) and 
                           (not target_file or b["filename"] == target_file)
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
                    messages.append(Message(role=context.get('role', 'user'), content=output))
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
                    print(f"Modified/Created file: {filepath}")
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

    messages.append(Message(
        role=context.get('role', 'user'),
        content="\n".join(summary)
    ))
    return messages


@llt(needs_index=True)
def edit_content(messages: List[Message], context: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Description: Edit message content in external editor
    Type: bool
    Default: false
    flag: content
    short: edit
    param: backup bool True
    """
    if not messages:
        print("No messages to edit.")
        return messages

    plugin_args = context.get("content", {})
    create_backup = plugin_args.get('backup', True)

    if not context.get('non_interactive'):
        msg_index = get_valid_index(messages, "edit content of", index)
    else:
        msg_index = index

    editor = os.environ.get("EDITOR", "vim")

    with temp_file(suffix=".md", content=messages[msg_index].content) as temp_path:
        try:
            subprocess.run([editor, temp_path], check=True)
            new_content = file_handler.read(temp_path)
            if new_content is not None and new_content != messages[msg_index].content:
                if create_backup:
                    backup_manager.create_backup(temp_path)
                messages[msg_index].content = new_content

        except Exception as e:
            Colors.print_colored(f"Error editing content: {e}", Colors.RED)

    return messages


@llt()
def paste(messages: List[Message], context: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Description: Paste clipboard content as new user message
    Type: bool
    Default: false
    flag: paste
    short: pa
    """
    messages.append(Message(role=context.get('role'), content=pyperclip.paste()))
    return messages


@llt(needs_index=True)
def copy(messages: List[Message], context: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Description: Copy message content to clipboard
    Type: bool
    Default: false
    flag: copy
    short: c
    param: blocks bool False
    param: lang string None
    """
    if not messages:
        print("No messages to copy.")
        return messages

    plugin_args = context.get("copy", {})
    copy_blocks = plugin_args.get('blocks', False)
    lang_filter = plugin_args.get('lang')

    if not context.get('non_interactive'):
        index = get_valid_index(messages, "copy", index)

    if copy_blocks:
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
        pyperclip.copy(messages[index].content)
        print("Copied message to clipboard.")

    return messages


@llt() # This one is already correct, no change needed here.
def file_include(messages: List[Message], context: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Description: Include file content (including images) into the conversation
    Type: string
    Default: base
    flag: file
    short: f
    """
    file_path = context.get("file", "")
    
    print(f"File path: {file_path}")

    if not context.get('non_interactive') and not context.get('auto'):
        file_path = input_handler.get_path_input("Enter file path to include", default=file_path, root_dir=os.getcwd())

    if not file_path or not os.path.exists(file_path):
        Colors.print_colored(f"Error: File not found at {file_path}", Colors.RED)
        return messages

    _, ext = os.path.splitext(file_path)
    if ext.lower() in [".png", ".jpeg", ".jpg", ".gif", ".webp"]:
        prompt = context.get('prompt')
        if not context.get('non_interactive'):
            prompt = input_handler.get_input("Enter prompt") or prompt
        
        try:
            encoded_image = file_handler.encode_image_to_base64(file_path)
            if not encoded_image:
                return messages
        except Exception as e:
            Colors.print_colored(f"Failed to encode image: {e}", Colors.RED)
            return messages
        
        messages.append(Message(
            role="user", 
            content=[
                {"type": "image_url", "image_url": {"url": f"data:image/{ext[1:]};base64,{encoded_image}"}},
                {"type": "text", "text": prompt or ""},
            ],
        ))
    else:
        content = file_handler.read(file_path)
        if content is not None:
            if ext.lower() in language_extension_map.values():
                content = f"```{os.path.basename(file_path)}\n{content}\n```"
            messages.append(Message(role=context.get('role', 'user'), content=content))
    return messages
