# plugins/editor.py
import os
import subprocess
import difflib
import pyperclip
from typing import List, Dict

from plugins import plugin
from utils.helpers import path_input, get_valid_index
from utils.md_parser import parse_markdown_for_codeblocks, language_extension_map
from utils.file_diff import generate_diff, prompt_and_write_file


DEFAULT_EDITOR = "vim"

inverse_map = lambda d: {v: k for k, v in d.items()}