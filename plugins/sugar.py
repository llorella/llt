from typing import List, Dict
from plugins import llt
from utils import get_valid_index, content_input

@llt
def xml_wrap(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Wrap message content in XML tags."""
    tag_name = getattr(args, 'xml_wrap', None)
    if not tag_name:
        tag_name = content_input("Enter tag name")
        index = get_valid_index(messages, "xml_wrap content of", index)
                
    
    messages[index]["content"] = f"<{tag_name}>\n{messages[index]['content']}\n</{tag_name}>"
    return messages

@llt
def strip_trailing_newline(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Strip trailing newlines from message content."""
    if not args.non_interactive:
        index = get_valid_index(messages, "strip trailing newline", index)
    messages[index]["content"] = messages[index]["content"].rstrip("\n")
    return messages

@llt
def indent(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Indent message content by specified amount."""
    if not args.non_interactive:
        index = get_valid_index(messages, "indent content of", index)
    spaces = getattr(args, 'spaces', 4)
    prefix = ' ' * spaces
    
    messages[index]["content"] = '\n'.join(
        prefix + line for line in messages[index]["content"].splitlines()
    )
    return messages