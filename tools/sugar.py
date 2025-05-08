from typing import List, Dict
import os
import json
from tools import llt
from utils import get_valid_index, input_handler, language_extension_map, input_handler
from logger import llt_logger

def load_xml_tags() -> List[str]:
    """Load previously used XML tags."""
    try:
        with open(os.path.join(os.environ.get("LLT_DIR", "~/llt"), 'tools/xml_tags.json'), 'r') as f:
            data = json.load(f)
            return data.get('tags', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_xml_tags(tags: List[str]) -> None:
    """Save XML tags to file."""
    try:
        with open(os.path.join(os.environ.get("LLT_DIR", "~/llt"), 'tools/xml_tags.json'), 'w') as f:
            json.dump({'tags': list(set(tags))}, f, indent=2)
    except Exception as e:
        llt_logger.log_error(f"Error saving XML tags: {e}")

@llt()
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
            tag_name = input_handler.get_input(f"Select or enter new tag name (default is {args.get('xml_wrap')})", existing_tags)
        else:
            tag_name = input_handler.get_input("Enter tag name")
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

def parse_xml_content(content: str, tag_name: str) -> str:
    """
    Finds the inner content of a tag in content and returns it as a string 
    """
    import re
    pattern = f"<{tag_name}>(.*?)</{tag_name}>"
    # Use re.DOTALL to make . match newlines as well
    matches = re.findall(pattern, content, re.DOTALL)
    
    if not matches:
        return ""
    
    # If multiple matches found, join them with newlines
    if len(matches) > 1:
        return "\n\n".join(match.strip() for match in matches)
    
    # Return the single match
    return matches[0].strip()

@llt()
def parse_xml(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Parse XML content from a message.
    Type: string
    Default: None
    flag: parse_xml
    short: parse
    """
    tag_name = args.get('parse_xml')
    if not args.get('non_interactive') and not args.get('auto') or not tag_name:
        index = get_valid_index(messages, "parse XML content of", index)
        tag_name = input_handler.get_list_input(load_xml_tags(), "Select tag name to parse") or tag_name
    
    if tag_name:
        original_content = messages[index]["content"]
        messages[index]["content"] = parse_xml_content(original_content, tag_name)
    return messages

@llt()
def strip_trailing_newline(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Strip trailing newlines from message content."""
    if not args.get('non_interactive'):
        index = get_valid_index(messages, "strip trailing newline", index)
    messages[index]["content"] = messages[index]["content"].rstrip("\n")
    return messages

@llt()
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

@llt()
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
        language = input_handler.get_input(f"Select programming language (default is {language})", list(language_extension_map.keys()), language)

    language = language.lower()
    if language in language_extension_map:
        messages[index]["content"] = f"```{language}\n{messages[index]['content']}\n```"
    else:
        # Fallback to plain code block if language not found
        messages[index]["content"] = f"```\n{messages[index]['content']}\n```"

    return messages