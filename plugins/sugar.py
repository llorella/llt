from typing import List, Dict
import os
import json
from plugins import llt
from utils import get_valid_index, content_input, list_input, language_extension_map
from logger import llt_logger

def load_xml_tags() -> List[str]:
    """Load previously used XML tags."""
    try:
        with open(os.path.join(os.environ.get("LLT_DIR", "~/llt"), 'plugins/xml_tags.json'), 'r') as f:
            data = json.load(f)
            return data.get('tags', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_xml_tags(tags: List[str]) -> None:
    """Save XML tags to file."""
    try:
        with open('plugins/xml_tags.json', 'w') as f:
            json.dump({'tags': list(set(tags))}, f, indent=2)
    except Exception as e:
        llt_logger.log_error(f"Error saving XML tags: {e}")

@llt
def xml_wrap(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Wrap messages in xml tags.
    Type: string
    Default: None
    flag: xml_wrap
    short: xml
    """
    # Load existing tags
    existing_tags = load_xml_tags()
    
    tag_name = args.get('xml_wrap')
    if not args.get('non_interactive') and not args.get('auto'):
        # If there are existing tags, offer them as options
        if existing_tags:
            tag_name = list_input(existing_tags, f"Select or enter new tag name (default is {args.get('xml_wrap')})")
        else:
            tag_name = content_input("Enter tag name")
        index = get_valid_index(messages, "xml_wrap content of", index)
    tag_name = tag_name or args.get('xml_wrap')
    # Add new tag to list and save
    if tag_name:
        messages[index]["content"] = f"<{tag_name}>\n{messages[index]['content']}\n</{tag_name}>"
        if tag_name not in existing_tags:
            existing_tags.append(tag_name)
            save_xml_tags(existing_tags)
            llt_logger.log_info(f"New XML tag added: {tag_name}")

    return messages

def parse_xml_content(content: str) -> str:
    """
    Parse XML content from a message.

    This function attempts to interpret the provided string as XML and extracts all textual content
    found within its elements. If the input is not valid XML, the original content is returned unchanged.
    """
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(content.strip())
        return ''.join(root.itertext()).strip()
    except ET.ParseError:
        return content

@llt
def parse_xml(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Parse XML content from message."""
    if not args.get('non_interactive'):
        index = get_valid_index(messages, "parse XML content of", index)
    messages[index]["content"] = parse_xml_content(messages[index]["content"])
    return messages

@llt
def strip_trailing_newline(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Strip trailing newlines from message content."""
    if not args.get('non_interactive'):
        index = get_valid_index(messages, "strip trailing newline", index)
    messages[index]["content"] = messages[index]["content"].rstrip("\n")
    return messages

@llt
def indent(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Indent message content by specified amount."""
    if not args.get('non_interactive'):
        index = get_valid_index(messages, "indent content of", index)
    spaces = args.get('spaces', 4)
    prefix = ' ' * spaces
    
    messages[index]["content"] = '\n'.join(
        prefix + line for line in messages[index]["content"].splitlines()
    )
    return messages

@llt
def code_block(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Wrap message in a code block with language syntax highlighting
    Type: string
    Default: bash
    flag: code_block
    short: cb
    """
    language = args.get('code_block', 'bash')
    if not args.get('non_interactive') and not args.get('auto'):
        index = get_valid_index(messages, "wrap in code block", index)
        language = list_input(list(language_extension_map.keys()), f"Select programming language (default is {language})") or language

    language = language.lower()
    if language in language_extension_map:
        messages[index]["content"] = f"```{language}\n{messages[index]['content']}\n```"
    else:
        # Fallback to plain code block if language not found
        messages[index]["content"] = f"```\n{messages[index]['content']}\n```"

    return messages