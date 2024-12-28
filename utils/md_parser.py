# utils/md_parser.py

import re
from typing import List, Dict, Optional

language_extension_map = {
    ".py": "python",
    ".sh": "shell",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
    ".js": "javascript",
    ".ts": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".c": "c",
    ".cpp": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".csv": "csv",
    ".cu": "cuda",
    ".jsx": "javascript",
    ".tsx": "typescript"
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

def extract_code_blocks(markdown: str) -> List[Dict]:
    """
    Generic code-fence parser: captures 
      ```<lang>\n<content>\n```
    Returns a list of { "language": str, "content": str }
    
    (We do not handle triple-backtick nesting or edge cases.)
    """
    code_pattern = re.compile(r"```(\w+)\n(.*?)\n```", re.DOTALL)
    matches = code_pattern.findall(markdown)
    blocks = []
    for language, code in matches:
        blocks.append({"language": language, "content": code})
    return blocks

def fuzzy_find_filename(line: str) -> str:
    """
    Use a regex to find something that looks like a path or filename.
    E.g. "src/components/NodeControls.tsx", "index.html", "main.py"...
    """
    filename_pattern = re.compile(r'([^\s"\':]+(\.[^\s"\':]+)+)')
    matches = filename_pattern.findall(line)
    # each match is a tuple, e.g. ("main.py", ".py")
    for full_match, _ in matches:
        return full_match
    return ""

def extract_filename_from_codeblock(code: str, language: str) -> Optional[str]:
    """
    Inspect the first few lines of 'code' for a filename comment.
    If found, return it; else None.
    For CSS, we'll look for /* comment */. For others, we look for # or // prefix.
    """
    comment_prefix = language_comment_map.get(language, "#")
    lines = code.split('\n')
    max_lines_to_check = min(5, len(lines))

    for i in range(max_lines_to_check):
        line = lines[i].strip()
        if not line:
            continue

        if language == "css":
            # We might see something like: /* filename.css */
            if line.startswith("/*") and line.endswith("*/"):
                # remove the /* and */ 
                content = line[2:-2].strip()
                guessed = fuzzy_find_filename(content)
                if guessed:
                    return guessed
        else:
            # We might see a line with '#' or '//' as prefix
            if line.startswith(comment_prefix):
                # remove just that prefix
                cmt = line[len(comment_prefix):].strip()
                guessed = fuzzy_find_filename(cmt)
                if guessed:
                    return guessed
    return None

def parse_markdown_for_codeblocks(markdown: str) -> List[Dict]:
    """
    High-level utility: for each code block, we also attempt to guess a filename.
    Returns a list of { language, content, filename }
    """
    blocks = extract_code_blocks(markdown)
    for b in blocks:
        lang = b["language"]
        code = b["content"]
        filename = extract_filename_from_codeblock(code, lang)
        b["filename"] = filename
    return blocks
