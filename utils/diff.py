import difflib
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum
from utils.colors import Colors

class DiffType(Enum):
    ADDED = '+'
    REMOVED = '-'
    CHANGED = '~'
    UNCHANGED = ' '

@dataclass
class DiffLine:
    type: DiffType
    content: str
    line_number_old: Optional[int] = None
    line_number_new: Optional[int] = None

    def colorize(self) -> str:
        """Return colorized version of the line content."""
        color_map = {
            DiffType.ADDED: Colors.GREEN,
            DiffType.REMOVED: Colors.RED,
            DiffType.CHANGED: Colors.YELLOW,
            DiffType.UNCHANGED: ''
        }
        return f"{color_map[self.type]}{self.content}{Colors.RESET}"

def generate_diff(old_content: str, new_content: str, context_lines: int = 3) -> List[DiffLine]:
    """Generate detailed diff with line numbers and change types."""
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    
    differ = difflib.SequenceMatcher(None, old_lines, new_lines)
    diff_lines = []
    
    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag == 'equal':
            start = max(i1, i1 + (i2 - i1 - context_lines))
            end = min(i2, i1 + context_lines)
            for i, line in enumerate(old_lines[start:end], start):
                diff_lines.append(DiffLine(
                    type=DiffType.UNCHANGED,
                    content=line,
                    line_number_old=i + 1,
                    line_number_new=j1 + (i - i1) + 1
                ))
        elif tag == 'replace':
            for i, line in enumerate(old_lines[i1:i2], i1):
                diff_lines.append(DiffLine(
                    type=DiffType.REMOVED,
                    content=line,
                    line_number_old=i + 1
                ))
            for j, line in enumerate(new_lines[j1:j2], j1):
                diff_lines.append(DiffLine(
                    type=DiffType.ADDED,
                    content=line,
                    line_number_new=j + 1
                ))
        elif tag == 'delete':
            for i, line in enumerate(old_lines[i1:i2], i1):
                diff_lines.append(DiffLine(
                    type=DiffType.REMOVED,
                    content=line,
                    line_number_old=i + 1
                ))
        elif tag == 'insert':
            for j, line in enumerate(new_lines[j1:j2], j1):
                diff_lines.append(DiffLine(
                    type=DiffType.ADDED,
                    content=line,
                    line_number_new=j + 1
                ))
    
    return diff_lines

def format_diff(diff_lines: List[DiffLine], show_line_numbers: bool = True) -> str:
    """Format diff lines for display."""
    output = []
    max_line_num_width = 5
    
    for line in diff_lines:
        if show_line_numbers:
            old_num = str(line.line_number_old or '').rjust(max_line_num_width)
            new_num = str(line.line_number_new or '').rjust(max_line_num_width)
            line_info = f"{old_num}│{new_num}│"
        else:
            line_info = f"{line.type.value} "
            
        output.append(f"{line_info} {line.colorize()}")
        
    return "\n".join(output) 