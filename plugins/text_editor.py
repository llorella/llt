# plugins/text_editor.py
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple
from plugins import plugin
from utils import path_input, content_input, get_valid_index
from collections import defaultdict
from difflib import unified_diff
import textwrap

class FileHistory:
    def __init__(self):
        self._history = defaultdict(list)
    
    def add(self, path: Path, content: str):
        self._history[path].append(content)
    
    def undo(self, path: Path) -> Optional[str]:
        if not self._history[path]:
            return None
        return self._history[path].pop()

    def clear(self, path: Path):
        if path in self._history:
            del self._history[path]

_file_history = FileHistory()

def validate_path(path: Path, command: str):
    """Validate path for editor operations."""
    if not path.is_absolute():
        suggested = Path.cwd() / path
        raise ValueError(f"Path {path} must be absolute. Did you mean {suggested}?")
    
    if not path.exists() and command != "create":
        raise FileNotFoundError(f"Path {path} does not exist.")
    
    if path.exists() and command == "create":
        raise FileExistsError(f"File {path} already exists. Cannot overwrite.")
    
    if path.is_dir() and command != "view":
        raise IsADirectoryError(f"Path {path} is a directory. Only 'view' allowed on directories.")

def make_output(content: str, descriptor: str, init_line: int = 1) -> str:
    """Format file content with line numbers."""
    content = content.expandtabs()
    numbered_lines = [f"{i+init_line:6}\t{line}" 
                     for i, line in enumerate(content.split('\n'))]
    return (f"Content of {descriptor}:\n" + 
            '\n'.join(numbered_lines) + "\n")

def show_diff(old: str, new: str, path: str) -> str:
    """Show unified diff between old and new content."""
    diff = unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"{path} (before)",
        tofile=f"{path} (after)",
        lineterm=""
    )
    return "".join(diff)

def apply_to_selection(content: str, start: int, end: int, 
                      func: Callable[[str], str]) -> Tuple[str, str]:
    """Apply a transformation function to selected lines."""
    lines = content.splitlines()
    if not (0 <= start <= end <= len(lines)):
        raise ValueError(f"Line range {start}-{end} out of bounds")
        
    selected = "\n".join(lines[start:end])
    transformed = func(selected)
    
    new_content = "\n".join(
        lines[:start] + 
        transformed.splitlines() +
        lines[end:]
    )
    return new_content, transformed

@plugin
def path_view(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """View file or directory content with optional line range."""
    path = Path(os.path.abspath(path_input("Enter path to view: ")) if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path", index)]['content'])
    try:
        validate_path(path, "view")
        
        if path.is_dir():
            import subprocess
            result = subprocess.run(
                ['find', str(path), '-maxdepth', '2', '-not', '-path', '*/\\.*'],
                capture_output=True, text=True
            )
            content = f"Files in {path}:\n{result.stdout}"
        else:
            content = path.read_text()
            view_range = input("Enter line range (start,end) or press enter for all: ")
            if view_range:
                start, end = map(int, view_range.split(','))
                lines = content.split('\n')
                if not (0 < start <= len(lines)):
                    raise ValueError(f"Start line {start} out of range")
                if end != -1 and (end < start or end > len(lines)):
                    raise ValueError(f"End line {end} out of range")
                content = '\n'.join(lines[start-1:end if end != -1 else None])
                
        messages.append({
            'role': 'assistant',
            'content': make_output(content, str(path))
        })
        
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error viewing {path}: {str(e)}"
        })
    
    return messages

@plugin
def create(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Create a new file with given content."""
    path = Path(path_input("Enter path for new file: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path to create", index)]['content'])
    try:
        validate_path(path, "create")
        content = content_input()
        path.write_text(content)
        _file_history.add(path, content)
        messages.append({
            'role': 'assistant',
            'content': f"File created successfully at {path}"
        })
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error creating file: {str(e)}"
        })
    return messages

@plugin
def str_replace(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Replace string in file with new string."""
    path = Path(path_input("Enter file path to str replace: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path to str replace", index)]['content'])
    try:
        validate_path(path, "replace")
        content = path.read_text().expandtabs()
        old_str = content_input()
        occurrences = content.count(old_str)
        
        if occurrences == 0:
            raise ValueError(f"String '{old_str}' not found in file")
        elif occurrences > 1:
            lines = [i+1 for i, line in enumerate(content.split('\n')) 
                    if old_str in line]
            raise ValueError(f"Multiple occurrences found in lines {lines}")
            
        new_str = content_input()
        new_content = content.replace(old_str, new_str)
        path.write_text(new_content)
        _file_history.add(path, content)
        
        messages.append({
            'role': 'assistant',
            'content': f"Successfully replaced text in {path}\n" +
                      show_diff(content, new_content, str(path))
        })
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error replacing text: {str(e)}"
        })
    return messages

@plugin
def insert(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Insert text at specified line."""
    path = Path(path_input("Enter file path to insert: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path to insert", index)]['content'])
    try:
        validate_path(path, "insert")
        content = path.read_text().expandtabs()
        lines = content.split('\n')
        
        line_num = int(input(f"Enter line number (1-{len(lines)}): "))
        if not (0 <= line_num <= len(lines)):
            raise ValueError(f"Line number {line_num} out of range")
            
        insert_text = content_input()
        new_lines = (lines[:line_num] + 
                    insert_text.split('\n') +
                    lines[line_num:])
        new_content = '\n'.join(new_lines)
        
        path.write_text(new_content)
        _file_history.add(path, content)
        
        messages.append({
            'role': 'assistant',
            'content': f"Successfully inserted text at line {line_num}\n" +
                      show_diff(content, new_content, str(path))
        })
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error inserting text: {str(e)}"
        })
    return messages

@plugin
def undo_edit(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Undo last edit to file."""
    path = Path(path_input("Enter file path to undo: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path to undo", index)]['content'])
    try:
        validate_path(path, "undo")
        prev_content = _file_history.undo(path)
        if not prev_content:
            raise ValueError("No edit history for this file")
            
        path.write_text(prev_content)
        messages.append({
            'role': 'assistant',
            'content': f"Successfully undid last edit to {path}\n" +
                      show_diff(path.read_text(), prev_content, str(path))
        })
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error undoing edit: {str(e)}"
        })
    return messages

@plugin 
def indent(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Add or remove indentation from selected lines."""
    path = Path(path_input("Enter file path to indent: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path", index)]['content'])
    try:
        validate_path(path, "indent")
        content = path.read_text()
        
        start = int(input("Start line: ")) - 1
        end = int(input("End line: "))
        spaces = int(input("Spaces to indent (negative to unindent): "))
        
        def indent_func(text: str) -> str:
            if spaces >= 0:
                return textwrap.indent(text, " " * spaces)
            else:
                return "\n".join(
                    line[min(len(line) - len(line.lstrip()), -spaces):]
                    for line in text.splitlines()
                )
        
        new_content, transformed = apply_to_selection(content, start, end, indent_func)
        path.write_text(new_content)
        _file_history.add(path, content)
        
        messages.append({
            'role': 'assistant',
            'content': f"Indentation modified:\n{show_diff(content, new_content, str(path))}"
        })
        
    except Exception as e:
        messages.append({
            'role': 'assistant', 
            'content': f"Error modifying indentation: {str(e)}"
        })
    return messages

@plugin
def wrap(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Wrap text to specified width."""
    path = Path(path_input("Enter file path to wrap: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path", index)]['content'])
    try:
        validate_path(path, "wrap")
        content = path.read_text()
        
        start = int(input("Start line: ")) - 1
        end = int(input("End line: "))
        width = int(input("Wrap width (default 80): ") or "80")
        
        def wrap_func(text: str) -> str:
            return "\n".join(
                textwrap.fill(line, width=width)
                for line in text.splitlines()
            )
            
        new_content, transformed = apply_to_selection(content, start, end, wrap_func)
        path.write_text(new_content)
        _file_history.add(path, content)
        
        messages.append({
            'role': 'assistant',
            'content': f"Text wrapped:\n{show_diff(content, new_content, str(path))}"
        })
        
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error wrapping text: {str(e)}"
        })
    return messages

@plugin
def regex_replace(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Replace text using regular expressions."""
    path = Path(path_input("Enter file path for regex replace: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path", index)]['content'])
    try:
        validate_path(path, "regex")
        content = path.read_text()
        
        pattern = content_input() if not args.non_interactive else input("Enter regex pattern: ")
        replacement = content_input() if not args.non_interactive else input("Enter replacement: ")
        
        # Compile and test pattern first
        try:
            regex = re.compile(pattern)
            match_count = len(regex.findall(content))
            if match_count == 0:
                raise ValueError(f"Pattern '{pattern}' not found in file")
            print(f"Found {match_count} matches")
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
            
        new_content = regex.sub(replacement, content)
        path.write_text(new_content)
        _file_history.add(path, content)
        
        messages.append({
            'role': 'assistant',
            'content': f"Regex replacement complete:\n{show_diff(content, new_content, str(path))}"
        })
        
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error in regex replace: {str(e)}"
        })
    return messages

@plugin
def format_block(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Format a block of text (align, justify, etc)."""
    path = Path(path_input("Enter file path to format: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path", index)]['content'])
    try:
        validate_path(path, "format")
        content = path.read_text()
        
        start = int(input("Start line: ")) - 1
        end = int(input("End line: "))
        align = input("Alignment (left/right/center/justify): ").lower()
        width = int(input("Width (default 80): ") or "80")
        
        def format_func(text: str) -> str:
            lines = text.splitlines()
            if align == "left":
                return "\n".join(line.ljust(width) for line in lines)
            elif align == "right":
                return "\n".join(line.rjust(width) for line in lines)
            elif align == "center":
                return "\n".join(line.center(width) for line in lines)
            elif align == "justify":
                result = []
                for line in lines:
                    if len(line.strip()) == 0 or line == lines[-1]:
                        result.append(line)
                        continue
                    words = line.split()
                    if len(words) == 1:
                        result.append(words[0].ljust(width))
                        continuespaces = width - sum(len(word) for word in words)
                    gaps = len(words) - 1
                    space_per_gap = spaces // gaps
                    extra_spaces = spaces % gaps
                    justified = ""
                    for i, word in enumerate(words[:-1]):
                        justified += word
                        gap_spaces = space_per_gap + (1 if i < extra_spaces else 0)
                        justified += " " * gap_spaces
                    justified += words[-1]
                    result.append(justified)
                return "\n".join(result)
            else:
                raise ValueError(f"Unknown alignment: {align}")
                
        new_content, transformed = apply_to_selection(content, start, end, format_func)
        path.write_text(new_content)
        _file_history.add(path, content)
        
        messages.append({
            'role': 'assistant',
            'content': f"Text formatted:\n{show_diff(content, new_content, str(path))}"
        })
        
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error formatting text: {str(e)}"
        })
    return messages

@plugin
def case_convert(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """Convert case of selected text."""
    path = Path(path_input("Enter file path for case conversion: ") if not args.non_interactive 
                else messages[get_valid_index(messages, "message containing path", index)]['content'])
    try:
        validate_path(path, "case")
        content = path.read_text()
        
        start = int(input("Start line: ")) - 1
        end = int(input("End line: "))
        case = input("Convert to (upper/lower/title/snake/camel): ").lower()
        
        def case_func(text: str) -> str:
            if case == "upper":
                return text.upper()
            elif case == "lower":
                return text.lower()
            elif case == "title":
                return text.title()
            elif case == "snake":
                words = re.findall(r'[A-Z][a-z]*|\d+|[A-Za-z]+', text)
                return "_".join(word.lower() for word in words)
            elif case == "camel":
                words = re.findall(r'[A-Z][a-z]*|\d+|[A-Za-z]+', text)
                return words[0].lower() + "".join(word.title() for word in words[1:])
            else:
                raise ValueError(f"Unknown case conversion: {case}")
                
        new_content, transformed = apply_to_selection(content, start, end, case_func)
        path.write_text(new_content)
        _file_history.add(path, content)
        
        messages.append({
            'role': 'assistant',
            'content': f"Case converted:\n{show_diff(content, new_content, str(path))}"
        })
        
    except Exception as e:
        messages.append({
            'role': 'assistant',
            'content': f"Error converting case: {str(e)}"
        })
    return messages