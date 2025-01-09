# utils/md_parser.py

import re
from typing import List, Dict, Optional

language_extension_map = {
    "python": ".py",
    "shell": ".sh",
    "markdown": ".md",
    "html": ".html",
    "css": ".css",
    "javascript": ".js",
    "typescript": ".ts",
    "json": ".json",
    "yaml": ".yaml",
    "c": ".c",
    "cpp": ".cpp",
    "rust": ".rs",
    "go": ".go",
    "csv": ".csv",
    "cuda": ".cu",
    "jsx": ".jsx",
    "tsx": ".tsx"
}

language_comment_map = {
    'python': '#',
    'shell': '#',
    'text': '#',
    'markdown': '#',
    'html': '<!--',
    'css': '/*',
    'javascript': '//',
    'typescript': '//',
    'json': '//',
    'yaml': '#',
    'c': '//',
    'cpp': '//',
    'rust': '//',
    'csv': '#',
    'jsx': '//',
    'tsx': '//'
}

def detect_language_from_content(content: str) -> Optional[str]:
    """Try to detect language from code content."""
    # Simple heuristics - could be expanded
    indicators = {
        'python': ['def ', 'import ', 'class ', 'if __name__'],
        'javascript': ['function ', 'const ', 'let ', 'var '],
        'typescript': ['interface ', 'type ', '<T>', ': string'],
        'html': ['<!DOCTYPE', '<html', '<div', '<body'],
        'css': ['{', '@media', '#', '.class'],
        'shell': ['#!/bin/', 'echo ', 'export ', 'sudo '],
        'rust': ['fn ', 'impl ', 'pub ', 'use '],
        'go': ['func ', 'package ', 'import (', 'type '],
    }
    
    for lang, patterns in indicators.items():
        if any(pattern in content for pattern in patterns):
            return lang
    return None

def extract_code_blocks(markdown: str) -> List[Dict]:
    """Extract code blocks from markdown text."""
    code_pattern = re.compile(r"```(\w+)\n(.*?)\n```", re.DOTALL)
    matches = code_pattern.findall(markdown)
    blocks = []
    for language, code in matches:
        blocks.append({
            "language": language,
            "content": code.strip(),
            "filename": None
        })
    return blocks

def fuzzy_find_filename(line: str) -> str:
    """Find something that looks like a path or filename."""
    filename_pattern = re.compile(r'([^\s"\':]+(\.[^\s"\':]+)+)')
    matches = filename_pattern.findall(line)
    for full_match, _ in matches:
        return full_match
    return ""

def extract_filename_from_codeblock(code: str, language: str) -> Optional[str]:
    """Try to find filename in code block comments."""
    comment_prefix = language_comment_map.get(language, "#")
    lines = code.split('\n')
    max_lines_to_check = min(5, len(lines))

    for i in range(max_lines_to_check):
        line = lines[i].strip()
        if not line:
            continue

        if language == "css":
            if line.startswith("/*") and line.endswith("*/"):
                content = line[2:-2].strip()
                if filename := fuzzy_find_filename(content):
                    return filename
        else:
            if line.startswith(comment_prefix):
                content = line[len(comment_prefix):].strip()
                if filename := fuzzy_find_filename(content):
                    return filename
    return None

def parse_markdown_for_codeblocks(markdown: str) -> List[Dict]:
    """Parse markdown and extract code blocks with metadata."""
    blocks = extract_code_blocks(markdown)
    for i, block in enumerate(blocks):
        block["index"] = i
        if not block["filename"]:
            block["filename"] = extract_filename_from_codeblock(
                block["content"],
                block["language"]
            )
    return blocks