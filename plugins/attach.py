# plugins/attach.py

import os
import fnmatch
from pathlib import Path
from typing import List, Dict
from plugins import plugin
from utils.helpers import Colors
from utils.helpers import get_valid_index, content_input, encode_image_to_base64, path_input
from utils.md_parser import language_extension_map
# If you want .gitignore logic, you can import from e.g. embeddings.py or unify that code
from plugins.embeddings import get_gitignore_patterns, should_ignore

import pyperclip

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
    if ext.lower() in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
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
            print("Added image to messages.")
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
    save_code_block(TEMP_FILE, None, "e")
    messages[message_index]["content"] = open(TEMP_FILE).read()
    os.remove(TEMP_FILE)
    return messages

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
def strip_trailing_newline(messages: List[Dict[str, any]], args: Dict, index: int = -1)  -> List[Dict[str, any]]:
    index = get_valid_index(messages, "strip trailing newline", -1) if not args.non_interactive else -1
    messages[index]["content"] = messages[index]["content"].rstrip("\n")
    return messages