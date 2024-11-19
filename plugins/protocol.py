# plugins/protocol.py
from typing import Dict, List, Optional
import re
import os
import json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class ProtocolTag:
    name: str
    content: str
    attributes: Dict[str, str]

class ProtocolContext:
    """Maintains context for the protocol session."""
    def __init__(self):
        self.working_directory: Path = Path.cwd()
        self.active_files: List[Path] = []
        self.recent_changes: List[Dict] = []
        
    def add_change(self, change: Dict):
        self.recent_changes.append(change)
        
    def add_file(self, file: Path):
        if file not in self.active_files:
            self.active_files.append(file)

# Global context instance
context = ProtocolContext()

def parse_protocol_tag(content: str, tag_name: str) -> Optional[ProtocolTag]:
    """Parse a protocol tag and its contents."""
    pattern = f"<{tag_name}[^>]*>(.*?)</{tag_name}>"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None
        
    # Parse attributes if any
    attr_pattern = r'(\w+)="([^"]*)"'
    attr_match = re.findall(attr_pattern, content)
    attributes = dict(attr_match)
    
    return ProtocolTag(
        name=tag_name,
        content=match.group(1).strip(),
        attributes=attributes
    )

def parse_file_reference(ref: str) -> Dict[str, any]:
    print(f"ref: {ref}")
    """Parse @file:location references."""
    if not ref.startswith('@'):
        return None
        
    parts = ref[1:].split(':')
    if len(parts) != 2:
        return None
        
    file, location = parts
    
    # Handle different location formats
    if location.startswith('line_range'):
        range_match = re.match(r'line_range\((\d+)-(\d+)\)', location)
        if range_match:
            return {
                'file': file,
                'type': 'range',
                'start': int(range_match.group(1)),
                'end': int(range_match.group(2))
            }
    elif location.isdigit():
        return {
            'file': file,
            'type': 'line',
            'line': int(location)
        }
    else:
        return {
            'file': file,
            'type': 'function',
            'function': location
        }


def change(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Handle change protocol tags."""
    message = messages[index]
    change_tag = parse_protocol_tag(message['content'], 'change')
    if not change_tag:
        messages.append({
            'role': 'assistant',
            'content': 'No valid change tag found in message.'
        })
        return messages
    
    print(f"Change tag: {change_tag}")
   # Parse file reference
    file_ref = parse_file_reference(change_tag.content.split('\n')[0])
    print(file_ref)
    if not file_ref:
        messages.append({
            'role': 'assistant',
            'content': 'Invalid file reference in change tag.'
        })
        return messages
        
    # Extract old and new code
    lines = change_tag.content.split('\n')[1:]
    old_code = '\n'.join(l[2:] for l in lines if l.startswith('- '))
    new_code = '\n'.join(l[2:] for l in lines if l.startswith('+ '))
    
    # Add to context
    context.add_change({
        'file': file_ref,
        'old': old_code,
        'new': new_code
    })
    
    messages.append({
        'role': 'assistant',
        'content': f'Change recorded for {file_ref["file"]}'
    })
    return messages


def query(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Handle context query protocol tags."""
    message = messages[index]
    query_tag = parse_protocol_tag(message['content'], 'query')
    if not query_tag:
        return messages
        
    query_type = query_tag.attributes.get('type')
    query_path = query_tag.attributes.get('path')
    
    # Handle different query types
    if query_type == 'file':
        try:
            with open(query_path) as f:
                content = f.read()
            messages.append({
                'role': 'assistant',
                'content': f'Content of {query_path}:\n{content}'
            })
        except Exception as e:
            messages.append({
                'role': 'assistant',
                'content': f'Error reading file: {str(e)}'
            })
            
    return messages


def docs(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Handle documentation protocol tags."""
    message = messages[index]
    docs_tag = parse_protocol_tag(message['content'], 'docs')
    if not docs_tag:
        return messages

    file_ref = parse_file_reference(docs_tag.content.split('\n')[0])
    if not file_ref:
        messages.append({
            'role': 'assistant',
            'content': 'Invalid file reference in docs tag.'
        })
        return messages

    # Parse documentation components
    doc_lines = docs_tag.content.split('\n')[1:]
    doc_sections = {}
    current_section = None
    
    for line in doc_lines:
        if ':' in line:
            section, content = line.split(':', 1)
            current_section = section.strip()
            doc_sections[current_section] = content.strip()
        elif current_section and line.strip():
            doc_sections[current_section] += '\n' + line.strip()

    context.add_file(Path(file_ref['file']))
    messages.append({
        'role': 'assistant',
        'content': f'Documentation added for {file_ref["file"]}'
    })
    return messages


def error(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Handle error protocol tags."""
    message = messages[index]
    error_tag = parse_protocol_tag(message['content'], 'error')
    if not error_tag:
        return messages

    error_info = {}
    for line in error_tag.content.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            error_info[key.strip()] = value.strip()

    if 'file' in error_info:
        context.add_file(Path(error_info['file']))

    messages.append({
        'role': 'assistant',
        'content': f'Error recorded: {error_info.get("message", "Unknown error")}'
    })
    return messages


def test(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Handle test case protocol tags."""
    message = messages[index]
    test_tag = parse_protocol_tag(message['content'], 'test')
    if not test_tag:
        return messages

    file_ref = parse_file_reference(test_tag.content.split('\n')[0])
    if not file_ref:
        messages.append({
            'role': 'assistant',
            'content': 'Invalid file reference in test tag.'
        })
        return messages

    # Parse test case components
    test_lines = test_tag.content.split('\n')[1:]
    test_info = {}
    current_section = None
    
    for line in test_lines:
        if ':' in line:
            section, content = line.split(':', 1)
            current_section = section.strip()
            test_info[current_section] = content.strip()
        elif current_section and line.strip():
            test_info[current_section] += '\n' + line.strip()

    context.add_file(Path(file_ref['file']))
    messages.append({
        'role': 'assistant',
        'content': f'Test case added for {file_ref["file"]}'
    })
    return messages


def context_status(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Show current protocol context status."""
    status = {
        'working_directory': str(context.working_directory),
        'active_files': [str(f) for f in context.active_files],
        'recent_changes': len(context.recent_changes)
    }
    
    messages.append({
        'role': 'tool',
        'content': json.dumps(status)
    })
    return messages


test_file = "/home/luciano/.llt/ll/llt-system-prompt-sonnet-1118"


if __name__ == "__main__":
    with open(test_file, "r") as f:
        messages = json.loads(f.read())
    
    messages = change(messages, {})
    
    print(context.recent_changes)