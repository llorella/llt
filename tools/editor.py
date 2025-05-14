import os
import subprocess
import pyperclip  # type: ignore
import json
from typing import List, Dict, Any, Optional, Union, Literal
from pathlib import Path
import traceback
import re
import base64

from pydantic import BaseModel, Field
from message import Message
from tools import llt
from utils import (
    Colors, get_project_dir, get_valid_index,
    confirm_action, language_extension_map,
    iter_blocks,
    temp_file, backup_manager,
    file_handler, input_handler, diff_handler,
)

# Pydantic models for file content parsing and validation
class FileBase(BaseModel):
    """Base model for file operations."""
    path: str
    exists: bool = False

class ImageFile(FileBase):
    """Model for image file data."""
    media_type: str
    data: Optional[str] = None  # Base64 encoded data
    
    @classmethod
    def from_path(cls, path: str) -> "ImageFile":
        """Create an ImageFile instance from a file path."""
        _, ext = os.path.splitext(path)
        media_type = f"image/{ext[1:].lower()}"
        exists = os.path.exists(path)
        
        data = None
        if exists:
            try:
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                Colors.print_colored(f"Error reading image file: {e}", Colors.RED)
        
        return cls(path=path, exists=exists, media_type=media_type, data=data)

class TextFile(FileBase):
    """Model for text file data."""
    content: Optional[str] = None
    language: Optional[str] = None
    
    @classmethod
    def from_path(cls, path: str) -> "TextFile":
        """Create a TextFile instance from a file path."""
        _, ext = os.path.splitext(path)
        exists = os.path.exists(path)
        
        # Try to determine language from extension
        language = None
        for lang, ext_list in language_extension_map.items():
            if ext in ext_list:
                language = lang
                break
        
        content = None
        if exists:
            content = file_handler.read(path)
        
        return cls(path=path, exists=exists, content=content, language=language)

class ImageContent(BaseModel):
    """Model for image content in messages."""
    type: Literal["image"]
    source: Dict[str, str]

class ImageUrlContent(BaseModel):
    """Model for image URL content in messages."""
    type: Literal["image_url"]
    image_url: Union[str, Dict[str, str]]

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
    short: ex
    param: language string bash
    param: timeout int 30
    param: content string None
    """
    print("CONTEXT: ", context)
    print(f"CONTEXT KEYS: {list(context.keys())}")
    execute_value = context.get("execute", {})
    print(f"EXECUTE VALUE TYPE: {type(execute_value)}")
    print(f"EXECUTE VALUE: {execute_value}")
    plugin_args = {}
    if isinstance(execute_value, dict):
        plugin_args = execute_value
    print(f"PLUGIN ARGS: {plugin_args}")
    direct_content = None
    if 'content' in plugin_args:
        direct_content = plugin_args.get('content')
        print(f"FOUND DIRECT CONTENT: {direct_content}")
    else:
        print("NO DIRECT CONTENT FOUND IN PLUGIN ARGS")
    target_lang = plugin_args.get('language', 'bash')
    timeout = plugin_args.get('timeout', 30)

    if not context.get('non_interactive') and not context.get('auto'):
        index = get_valid_index(messages, "execute code blocks from", index)
        target_lang = input_handler.get_list_input(list(language_extension_map.keys()), f"Enter a language (default is {target_lang})")

    if direct_content and direct_content != 'None':
        print(f"Executing direct content: {direct_content}")
        print(f"Language: {target_lang}")
        output, cmd = execute_code(direct_content, target_lang, timeout)
        print(f"\nExecuted command: {cmd}")
        print("\nOutput:")
        Colors.print_colored(output, Colors.GREEN)
        xml_content = f"<cmd><![CDATA[{cmd}]]></cmd>\n<output><![CDATA[{output}]]></output>"
        messages.append(Message(role='assistant', content=xml_content))
        return messages

    try:
        content: str = messages[index]['content']
        if not isinstance(content, str):
            print(f"Warning: Message content is not a string: {type(content)}")
            return messages
    except (IndexError, KeyError):
        llt(f"Error: Cannot access message at index {index}")
        return messages

    pattern = r"```(\S+)\n(.*?)\n```"
    code_blocks = list(re.finditer(pattern, content, re.DOTALL))

    if not code_blocks:
        print("No code blocks found in the message.")
        return messages

    for match in code_blocks:
        language = match.group(1)
        code = match.group(2).strip()
        if target_lang and language != target_lang:
            continue
        print(f"\nCode block ({language}):")
        Colors.print_colored(code, Colors.CYAN)
        if context.get('auto') or (context.get('non_interactive') or confirm_action("Execute this block?")):
            try:
                output, cmd = execute_code(code, language, timeout)
             
            except Exception as e:
                output, cmd = f"Error executing block: {str(e)}", ""     
            xml_content = f"<cmd><![CDATA[{cmd}]]></cmd>\n<output><![CDATA[{output}]]></output>"
            messages.append(Message(role='user', content=xml_content))
    return messages

@llt()
def encode_images(messages: List[Message], args: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Description: Encode image URLs into the proper format for different LLM providers.
    Type: bool
    Default: false
    flag: encode_images
    short: ei
    """
    encoded_messages = None
    provider_format = args.get('format', 'auto')
    
    for i, message in enumerate(messages):
        if message.get("role") == "user" and message.get("content") and isinstance(message["content"], list):
            for j, content_item in enumerate(message["content"]):
                if content_item.get("type") == "image_url":
                    image_url = content_item["image_url"]
                    if isinstance(image_url, dict) and "url" in image_url:
                        image_url = image_url["url"]
                        
                    if image_url.startswith("file://") or os.path.exists(image_url):
                        if encoded_messages is None:
                            encoded_messages = json.loads(json.dumps(messages))
                        try:
                            # Create an ImageFile instance and ensure it's valid
                            path = image_url.replace("file://", "")
                            image = ImageFile.from_path(path)
                            
                            if not image.exists or not image.data:
                                Colors.print_colored(f"Failed to encode image: {path}", Colors.RED)
                                continue
                            
                            _, ext = os.path.splitext(path)
                            if provider_format == 'claude':
                                encoded_messages[i]["content"][j] = {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": image.media_type,
                                        "data": image.data
                                    }
                                }
                            else:  # OpenAI format
                                encoded_messages[i]["content"][j] = {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{image.media_type};base64,{image.data}"
                                    }
                                }
                            Colors.print_colored(f"Encoded image: {path} for {provider_format} format", Colors.GREEN)
                        except Exception as e:
                            Colors.print_colored(f"Error encoding image: {e}", Colors.RED)
                            return messages
                        
    return encoded_messages or messages
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

    with temp_file(suffix=".md", content=messages[msg_index]["content"]) as temp_path:
        try:
            subprocess.run([editor, temp_path], check=True)
            new_content = file_handler.read(temp_path)
            if new_content is not None and new_content != messages[msg_index]["content"]:
                if create_backup:
                    backup_manager.create_backup(temp_path)
                messages[msg_index]["content"] = new_content

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
    short: yy
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
            content = "\n\n".join(b.content for b in blocks)
            pyperclip.copy(content)
            print(f"Copied {len(blocks)} code blocks to clipboard.")
        else:
            print("No matching code blocks found.")
    else:
        pyperclip.copy(messages[index]["content"])
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
            # Use the ImageFile model for validation and encoding
            image = ImageFile.from_path(file_path)
            if not image.data:
                Colors.print_colored(f"Failed to encode image: {file_path}", Colors.RED)
                return messages
                
            messages.append(Message(
                role="user", 
                content=[
                    {"type": "image_url", "image_url": {"url": f"data:{image.media_type};base64,{image.data}"}},
                    {"type": "text", "text": prompt or ""},
                ],
            ))
        except Exception as e:
            Colors.print_colored(f"Failed to encode image: {e}", Colors.RED)
            return messages
    else:
        # Use the TextFile model for validation and content reading
        text_file = TextFile.from_path(file_path)
        if text_file.content is not None:
            if text_file.language:
                content = f"```{os.path.basename(file_path)}\n{text_file.content}\n```"
            else:
                content = text_file.content
            messages.append(Message(role=context.get('role', 'user'), content=content))
        else:
            Colors.print_colored(f"Failed to read file: {file_path}", Colors.RED)
    return messages
