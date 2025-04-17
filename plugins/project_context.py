#!/usr/bin/env python3
"""
project_context.py - LLT plugin for project context analysis and manipulation.

Combines file inclusion, code block application/execution, and Git functionalities.
"""

import os
import sys
import fnmatch
import subprocess
import re
import json
from typing import List, Dict, Optional, Callable, Iterator, Set, Tuple, Any
from pathlib import Path
import traceback
import pathspec

# LLT imports
from plugins import llt
from message import Message
from utils import (
    Colors,
    get_project_dir, temp_file, iter_blocks,
)

# --- Constants ---
# Language mappings
LANGUAGE_EXTENSION_MAP = {
    'python': '.py', 'shell': '.sh', 'text': '.txt', 'markdown': '.md',
    'html': '.html', 'css': '.css', 'javascript': '.js', 'typescript': '.ts',
    'json': '.json', 'yaml': '.yaml', 'c': '.c', 'cpp': '.cpp',
    'rust': '.rs', 'csv': '.csv', 'jsx': '.jsx', 'go': '.go', 'java': '.java',
    'php': '.php', 'ruby': '.rb', 'perl': '.pl', 'sql': '.sql', 'xml': '.xml'
}
EXTENSION_TO_LANGUAGE = {v.lstrip('.'): k for k, v in LANGUAGE_EXTENSION_MAP.items()}

# Common ignored patterns (can be overridden by args)
DEFAULT_IGNORED_PATTERNS = {
    ".git", ".hg", ".svn", ".tox", ".venv", "venv", "__pycache__",
    "node_modules", "build", "dist", "target", "docs", ".vscode", ".idea",
    "*.pyc", "*.log", "*.tmp", "*.swp", "*.swo", "*.bak", "*.out",
    "*.class", "*.jar", "*.war", "*.ear", "*.DS_Store"
}


def _is_binary_file(filepath: str, chunk_size: int = 1024) -> bool:
    """Check if a file is binary by looking for null bytes in the first chunk."""
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(chunk_size)
        return b'\\0' in chunk
    except (PermissionError, OSError):
        Colors.print_colored(f"Warning: Permission denied or OS error reading {filepath}", Colors.YELLOW)
        return True # Assume binary if unreadable

def _detect_language(file_path: str) -> str:
    """Detect the programming language based on file extension."""
    _, ext = os.path.splitext(file_path)
    if not ext:
        return 'text'
    ext = ext.lstrip('.')
    return EXTENSION_TO_LANGUAGE.get(ext, 'text')

def _format_file_content(content: str, language: str, file_path: str) -> str:
    """Format file content into a markdown code block."""
    if not content:
        return ''
   # lang_identifier = language.split()[0].lower() if language else 'text'
    display_path = Path(file_path).as_posix()
    #return f"--- File: {display_path} ---\n```{lang_identifier}\n{content.strip()}\n```\n"
    return f"```{display_path}\n{content.strip()}\n```"



def _run_git_command(directory: str, command: List[str]) -> Tuple[int, str, str]:
    """Runs a Git command in the specified directory, returning exit code, stdout, stderr."""
    try:
        abs_dir = os.path.abspath(directory)
        cmd = ["git", "-C", abs_dir] + command
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore'
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        Colors.print_colored("Error: Git command not found. Is Git installed and in PATH?", Colors.RED)
        return -1, "", "Git command not found"
    except Exception as e:
        Colors.print_colored(f"Error running git command {' '.join(command)}: {e}", Colors.RED)
        return -1, "", str(e)


def _get_git_files_ls(directory: str, ignored_patterns: Set[str]) -> Optional[List[str]]:
    """Attempt to get file list using 'git ls-files -co --exclude-standard'."""
    abs_dir = os.path.abspath(directory)
    returncode, stdout, stderr = _run_git_command(abs_dir, ["ls-files", "-co", "--exclude-standard"])

    if returncode != 0:
        if "not a git repository" not in stderr.lower():
            Colors.print_colored(f"Git ls-files failed in '{directory}': {stderr}", Colors.YELLOW)
        return None

    files = stdout.splitlines()
    filtered_files = []
    for f_rel in files:
        full_path = os.path.join(abs_dir, f_rel)
        path_parts = set(Path(f_rel).parts)
        if not any(ignored in path_parts for ignored in ignored_patterns):
            filtered_files.append(full_path)
    return filtered_files

def _walk_files(directory: str, ignored_patterns: Set[str], use_gitignore: bool) -> List[str]:
    """Get file list using os.walk and pathspec for gitignore."""
    files_list = []
    abs_dir = os.path.abspath(directory)
    gitignore_spec = None
    gitignore_path = os.path.join(abs_dir, '.gitignore')

    if use_gitignore and os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, 'r', encoding='utf-8', errors='replace') as f:
                gitignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', f)
        except Exception as e:
            Colors.print_colored(f"Warning: Failed to load or parse .gitignore '{gitignore_path}': {e}", Colors.YELLOW)
            gitignore_spec = None

    for root, dirs, files in os.walk(abs_dir, topdown=True):
        rel_root = os.path.relpath(root, abs_dir)
        if rel_root == '.': rel_root = ''

        # Filter ignored directories based on name patterns and hidden status
        original_dirs = list(dirs)
        dirs[:] = [d for d in original_dirs if d not in ignored_patterns and not (d.startswith('.') and d != '.')]

        # Filter dirs based on gitignore spec
        if gitignore_spec:
             current_dirs = list(dirs)
             dirs[:] = []
             for d in current_dirs:
                 dir_path_for_match = Path(rel_root) / d
                 if not gitignore_spec.match_file(dir_path_for_match.as_posix()):
                     dirs.append(d)

        for filename in files:
            if (filename.startswith('.') and filename != '.') or filename in ignored_patterns:
                continue

            full_path = os.path.join(root, filename)
            rel_path_for_match = Path(os.path.relpath(full_path, abs_dir))

            is_ignored_by_git = False
            if gitignore_spec and gitignore_spec.match_file(rel_path_for_match.as_posix()):
                 is_ignored_by_git = True

            if is_ignored_by_git:
                 continue

            if any(ignored in rel_path_for_match.parts for ignored in ignored_patterns):
                continue

            files_list.append(full_path)

    return files_list


def _get_project_files(
    directory: str,
    ignored_patterns: Set[str],
    globs: List[str],
    use_gitignore: bool,
    use_git_ls: bool
) -> List[str]:
    """
    Internal helper to get project files, using git ls-files or os.walk.
    Returns absolute paths.
    """
    candidate_files = []
    abs_dir = os.path.abspath(directory)
    is_git_repo = use_git_ls and os.path.isdir(os.path.join(abs_dir, '.git'))

    if is_git_repo:
        git_files = _get_git_files_ls(abs_dir, ignored_patterns)
        if git_files is not None:
            candidate_files = git_files
        else:
            is_git_repo = False # Fallback

    if not is_git_repo:
        candidate_files = _walk_files(abs_dir, ignored_patterns, use_gitignore)

    # Apply glob filtering
    filtered_files = []
    match_all = not globs
    for f_path in candidate_files:
         filename = os.path.basename(f_path)
         if match_all or any(fnmatch.fnmatch(filename, g) for g in globs):
             filtered_files.append(f_path)

    return [os.path.abspath(p) for p in filtered_files]


# --- Code Block Processing Functions (Adapted from editor.py) ---


def execute_code(code: str, language: str, timeout: int = 30, project_dir: Optional[str] = None) -> tuple[str, str]:
    """
    Execute code in a subprocess, capturing stdout/stderr.
    Runs in the specified project_dir if provided.
    Returns tuple of (output, command string that was run)
    """
    runners = {
        "python": ["python3", "-c"], "bash": ["bash", "-c"], "javascript": ["node", "-e"],
        "typescript": ["bun", "run"],
        "ruby": ["ruby", "-e"], "shell": ["bash", "-c"]
    }
    cmd_str = "(command not determined)"
    cmd: List[str] = []
    cwd = project_dir if project_dir and os.path.isdir(project_dir) else get_project_dir({}) # Use helper

    try:
        needs_file = language not in ["python", "bash", "shell", "javascript", "ruby"]
        # Ensure LANGUAGE_EXTENSION_MAP is accessible
        ext = LANGUAGE_EXTENSION_MAP.get(language, 'txt')

        with temp_file(suffix=f".{ext}", content=code) as temp_path:
            if language in runners and not needs_file:
                cmd = [*runners[language], code]
            elif language in runners and needs_file:
                 cmd = [*runners[language], temp_path]
            elif language == "file":
                 return f"File path: {temp_path}", "echo"
            else:
                cmd = [language, temp_path]

            if not cmd:
                 raise ValueError(f"Could not determine execution command for language: {language}")

            cmd_str = " ".join(map(str, cmd))
            Colors.print_colored(f"Executing ({language} in {cwd}): {cmd_str}", Colors.YELLOW)

            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                check=False, encoding='utf-8', errors='ignore',
                cwd=cwd
            )
            output = proc.stdout.strip() if proc.stdout else ""
            stderr = proc.stderr.strip() if proc.stderr else ""
            if stderr:
                output += f"\\n---\\nStderr:\\n{stderr}"

            output += f"\\n---\\nExit Code: {proc.returncode}"
            return output, cmd_str

    except subprocess.TimeoutExpired:
        error_msg = f"Execution timed out after {timeout} seconds"
        return f"Error: Timeout\\nCommand: {cmd_str}\\nDetails: {error_msg}", cmd_str
    except FileNotFoundError:
         interpreter = cmd[0] if cmd else language
         error_msg = f"Interpreter/command '{interpreter}' not found in PATH or not executable."
         return f"Error: FileNotFoundError\\nCommand: {cmd_str}\\nDetails: {error_msg}", cmd_str
    except Exception as e:
        error_type = type(e).__name__
        return f"Error: {error_type}\\nCommand: {cmd_str}\\nDetails: {str(e)}\\nTraceback:\\n{traceback.format_exc()}", cmd_str


# --- LLT Plugin Functions ---

@llt
def include_project_context(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Include content of project files based on filters.
    Type: bool
    Default: false
    flag: include_project_context
    short: ipc
    """
    project_dir = get_project_dir(args)
    print(f"Project directory: {project_dir}")
    directory = args.get('directory', project_dir)
    abs_dir = os.path.abspath(directory)
    print(f"Absolute directory: {abs_dir}")

    # Combine default ignores with user-provided ones
    ignored_patterns = set(DEFAULT_IGNORED_PATTERNS)
    if args.get('ignore'):
        ignored_patterns.update(p.strip() for p in args['ignore'].split(','))

    globs = [g.strip() for g in args['glob'].split(',')] if args.get('glob') else []
    use_gitignore = not args.get('no-gitignore', False)
    use_git_ls = not args.get('no-git-ls', False) and os.path.isdir(os.path.join(abs_dir, '.git'))
    max_total_size = args.get('max-size')
    if max_total_size is not None:
        try:
            max_total_size = int(max_total_size)
        except ValueError:
            Colors.print_colored("Error: max-size must be an integer (bytes).", Colors.RED)
            return messages

    Colors.print_colored(f"Building context for: {abs_dir}", Colors.BLUE)
    Colors.print_colored(f"Ignoring patterns: {', '.join(ignored_patterns)}", Colors.BLUE)
    if globs: Colors.print_colored(f"Filtering with globs: {', '.join(globs)}", Colors.BLUE)
    Colors.print_colored(f"Using .gitignore: {use_gitignore}", Colors.BLUE)
    Colors.print_colored(f"Using git ls-files: {use_git_ls}", Colors.BLUE)
    if max_total_size: Colors.print_colored(f"Max total size: {max_total_size} bytes", Colors.BLUE)

    files_to_include = _get_project_files(
        abs_dir, ignored_patterns, globs, use_gitignore, use_git_ls
    )

    output_parts = []
    total_size = 0
    included_count = 0
    skipped_binary = 0
    skipped_empty = 0
    skipped_size = 0

    files_to_include.sort(key=lambda p: os.path.relpath(p, abs_dir))

    for full_path in files_to_include:
        rel_path = os.path.relpath(full_path, abs_dir)

        if _is_binary_file(full_path):
            skipped_binary += 1
            continue

        try:
            file_size = os.path.getsize(full_path)
            if file_size == 0:
                skipped_empty += 1
                continue

            if max_total_size is not None and (total_size + file_size) > max_total_size:
                 skipped_size += 1
                 continue # Skip this file and check others

            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            language = _detect_language(full_path)
            formatted_content = _format_file_content(content, language, rel_path)

            output_parts.append(formatted_content)
            total_size += file_size
            included_count += 1

        except Exception as e:
            Colors.print_colored(f"Error reading or processing {rel_path}: {e}", Colors.RED)

    context_string = '\n\n'.join(output_parts)
    summary = f"Included {included_count} files ({total_size / 1024:.1f} KB total)."
    if skipped_binary: summary += f" Skipped {skipped_binary} binary files."
    if skipped_empty: summary += f" Skipped {skipped_empty} empty files."
    if skipped_size: summary += f" Skipped {skipped_size} files due to size limit."

    Colors.print_colored(summary, Colors.GREEN)

    if not context_string:
        Colors.print_colored("No content included.", Colors.YELLOW)
        return messages

    # Add as a user message? Or tool message? User seems appropriate for context.
    messages.append(Message(role="user", content=context_string))
    Colors.print_colored("Project context added to messages.", Colors.GREEN)

    return messages


@llt
def git_ls_files(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: List files tracked by Git in the project directory.
    flag: git_ls_files
    short: gls
    Args:
        directory:
            Type: str
            Description: Directory to run 'git ls-files' in (defaults to project root).
            Required: False
        others:
            Type: bool
            Description: Include untracked files (-o).
            Default: False
            Required: False
        cached:
            Type: bool
            Description: Include cached files (-c, default).
            Default: True # Implicitly true unless overridden? Let's make it explicit.
            Required: False
        ignored:
            Type: bool
            Description: Show ignored files that are normally excluded (-i).
            Default: False
            Required: False
        exclude-standard:
            Type: bool
            Description: Use standard exclude rules (--exclude-standard).
            Default: True
            Required: False
    """
    project_dir = get_project_dir(args)
    directory = args.get('directory', project_dir)
    abs_dir = os.path.abspath(directory)



    command = ["ls-files"]
    # Build flags based on args
    if args.get('cached', True): command.append("-c") # Default? Maybe not needed if default
    if args.get('others', False): command.append("-o")
    if args.get('ignored', False): command.append("-i")
    if args.get('exclude-standard', True): command.append("--exclude-standard")
    # Remove duplicates just in case
    command = list(dict.fromkeys(command))

    Colors.print_colored(f"Running: git -C {abs_dir} {' '.join(command)}", Colors.YELLOW)
    returncode, stdout, stderr = _run_git_command(abs_dir, command)

    if returncode != 0:
        Colors.print_colored(f"Error running git ls-files: {stderr}", Colors.RED)
    elif stdout:
        Colors.print_colored("--- Git LS Files Output ---", Colors.CYAN)
        print(stdout) # Print raw output
        Colors.print_colored("--- End Git LS Files ---", Colors.CYAN)
    else:
        Colors.print_colored("No files listed by git ls-files with the given options.", Colors.YELLOW)

    # This command typically just prints output, doesn't modify messages
    return messages


@llt
def git_status(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Show the Git status of the project directory.
    flag: git_status
    short: gs
    Args:
        directory:
            Type: str
            Description: Directory to run 'git status' in (defaults to project root).
            Required: False
        short:
            Type: bool
            Description: Use short format (-s).
            Default: True
            Required: False
        long:
            Type: bool
            Description: Use long format (overrides short).
            Default: False
            Required: False
    """
    project_dir = get_project_dir(args)
    directory = args.get('directory', project_dir)
    abs_dir = os.path.abspath(directory)

    command = ["status"]
    use_short = args.get('short', True)
    if args.get('long', False):
        use_short = False # Long overrides short

    if use_short:
        command.append("-s")

    Colors.print_colored(f"Running: git -C {abs_dir} {' '.join(command)}", Colors.YELLOW)
    returncode, stdout, stderr = _run_git_command(abs_dir, command)

    if returncode != 0:
        Colors.print_colored(f"Error running git status: {stderr}", Colors.RED)
    elif stdout:
        Colors.print_colored("--- Git Status Output ---", Colors.CYAN)
        print(stdout) # Print raw output
        Colors.print_colored("--- End Git Status ---", Colors.CYAN)
    else:
        Colors.print_colored("Git status clean or no changes detected.", Colors.GREEN)

    return messages


@llt
def git_diff(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Show Git diff for the project directory.
    flag: git_diff
    short: gd
    Args:
        directory:
            Type: str
            Description: Directory to run 'git diff' in (defaults to project root).
            Required: False
        cached:
            Type: bool
            Description: Show diff of staged changes (--cached).
            Default: False
            Required: False
        commit:
            Type: str
            Description: Diff against a specific commit or range (e.g., 'HEAD~1', 'main..feature').
            Required: False
        file:
            Type: str
            Description: Show diff for a specific file path relative to the directory.
            Required: False
        unified:
            Type: int
            Description: Set number of context lines (-U<n>).
            Required: False
    """
    project_dir = get_project_dir(args)
    directory = args.get('directory', project_dir)
    abs_dir = os.path.abspath(directory)

    command = ["diff"]
    if args.get('cached', False):
        command.append("--cached")
    if args.get('commit'):
        command.append(args['commit'])
    if args.get('unified') is not None:
        try:
            context_lines = int(args['unified'])
            command.append(f"-U{context_lines}")
        except ValueError:
             Colors.print_colored("Warning: 'unified' argument must be an integer. Ignoring.", Colors.YELLOW)

    # Add file path at the end if specified
    file_path = args.get('file')
    if file_path:
         command.append("--") # Separator recommended before pathspec
         command.append(file_path)


    Colors.print_colored(f"Running: git -C {abs_dir} {' '.join(command)}", Colors.YELLOW)
    returncode, stdout, stderr = _run_git_command(abs_dir, command)

    if returncode != 0:
        Colors.print_colored(f"Error running git diff: {stderr}", Colors.RED)
    elif stdout:
        Colors.print_colored("--- Git Diff Output ---", Colors.CYAN)
        # Format diff output within a code block for better readability
        diff_output = f"```diff\n{stdout}\n```"
        print(diff_output)
        Colors.print_colored("--- End Git Diff ---", Colors.CYAN)
    else:
        Colors.print_colored("No differences found.", Colors.GREEN)

    return messages

# --- End LLT Plugin Functions ---