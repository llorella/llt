from typing import List, Dict, Tuple, Optional
from plugins import plugin
from utils import get_valid_index, content_input
import json


class Buffer:
    def __init__(self, content: Optional[str] = ""):
        self.content = content
        self.lines = content.split("\n")
        self.line_count = len(self.lines)
        self.cursor = 0

    def get_line(self, line_number: int) -> str:
        return self.lines[line_number - 1]

    def get_line_count(self) -> int:
        return self.line_count

    def get_cursor(self) -> int:
        return self.cursor

    def set_cursor(self, cursor: int):
        self.cursor = cursor

    def get_content(self) -> str:
        return self.content

    def set_content(self, content: str):
        self.content = content
        self.lines = content.split("\n")
        self.line_count = len(self.lines)

    def insert_line(self, line_number: int, line: str):
        self.lines.insert(line_number - 1, line)
        self.line_count += 1

    def delete_line(self, line_number: int):
        self.lines.pop(line_number - 1)
        self.line_count -= 1
