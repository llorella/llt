# plugins/embeddings.py

import os
import json
import ast
import re
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import openai
import numpy as np
import fnmatch
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity

from plugins import plugin
from utils.helpers import Colors, path_input, get_valid_index
from utils.md_parser import language_extension_map

def get_gitignore_patterns(project_dir: str) -> List[str]:
    """Get patterns from .gitignore file and add default patterns."""
    patterns = [
        # Default patterns
        'node_modules/',
        '.*/',  # Hidden directories
        '.*',   # Hidden files
        '__pycache__/',
        '*.pyc',
        'venv/',
        '.env',
        'dist/',
        'build/',
        '*.egg-info/',
        '.git/',
        '*.log',
        '*.csv',
    ]
    
    gitignore_path = os.path.join(project_dir, '.gitignore')
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, 'r') as f:
                # Add patterns from .gitignore, filtering out comments and empty lines
                patterns.extend([
                    line.strip() 
                    for line in f.readlines() 
                    if line.strip() and not line.startswith('#')
                ])
        except Exception as e:
            Colors.print_colored(f"Warning: Error reading .gitignore: {e}", Colors.YELLOW)
    
    return patterns

def should_ignore(path: Path, patterns: List[str], project_dir: str) -> bool:
    """
    Check if a path should be ignored based on gitignore patterns.
    """
    # Convert path to relative path from project root
    rel_path = str(path.relative_to(project_dir))
    
    for pattern in patterns:
        # Normalize pattern
        pattern = pattern.rstrip('/')
        
        # Handle directory patterns
        if pattern.endswith('/'):
            if any(part.startswith('.') for part in path.parts):  # Check for hidden dirs in path
                return True
            if fnmatch.fnmatch(rel_path + '/', pattern + '/'):
                return True
        
        # Handle file patterns
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        
        # Handle patterns with wildcards
        if '*' in pattern or '?' in pattern:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
    
    return False

@plugin
def embeddings(messages: List[Dict], args: Dict, index: int=-1) -> List[Dict]:
    """
    Generic embeddings plugin that:
      1) Determines the project directory from args.load.
      2) Gathers code files for recognized languages (via language_extension_map).
      3) Extracts code "units" (functions, classes, interfaces, etc.) with improved logic.
      4) Embeds each snippet using a chosen model.
      5) Saves all results to a CSV.
      6) Appends a summary message to 'messages'.
    """
    
    # 1. Figure out project directory from 'args.load'
    if not args.load:
        Colors.print_colored("No 'load' path specified. Defaulting to 'untitled' under exec_dir.", Colors.YELLOW)
        project_rel = "untitled"
    else:
        ll_dir_abs = os.path.abspath(args.ll_dir)
        load_abs = os.path.abspath(args.load)
        rel = os.path.relpath(load_abs, ll_dir_abs)  # e.g. "project/subdir.ll"
        base, ext = os.path.splitext(rel)
        if ext == ".ll":
            rel = base
        project_rel = rel

    project_dir = os.path.join(args.exec_dir, project_rel)
    os.makedirs(project_dir, exist_ok=True)

    embeddings_file = args.embeddings or "embeddings.csv"

    if not os.path.isabs(embeddings_file):  
        embeddings_file = os.path.join(project_dir, embeddings_file)

    # gather recognized code files while respecting .gitignore
    recognized_exts = language_extension_map
    all_files = []
    
    ignore_patterns = get_gitignore_patterns(project_dir)
    
    for ext in recognized_exts.keys():
        for file_path in Path(project_dir).rglob(f"*{ext}"):
            if not should_ignore(file_path, ignore_patterns, project_dir):
                all_files.append(file_path)

    if not all_files:
        Colors.print_colored(f"No recognized code files found under {project_dir}.", Colors.RED)
        messages.append({"role": "assistant",
                         "content": f"No recognized code files found under {project_dir}."})
        return messages

    Colors.print_colored(f"Found {len(all_files)} code files to embed in {project_dir} (after ignore rules).", Colors.GREEN)
    # extract code units from each file
    code_units = []
    for fpath in all_files:
        code_ext = fpath.suffix.lower() 
        language = recognized_exts.get(code_ext, "unknown")
        print(f"Processing {fpath} with language {language} and code_ext {code_ext}")

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
        except Exception as e:
            Colors.print_colored(f"Failed to read {fpath}: {e}", Colors.RED)
            continue

        units = parse_code_units(language, source)
        
        for u in units:
            code_units.append({
                "language": language,
                "file": str(fpath.relative_to(project_dir)),
                "name": u["name"],
                "content": u["content"]
            })

    if not code_units:
        Colors.print_colored("No code units discovered in the recognized files.", Colors.YELLOW)
        return messages

    # embed each code unit
    embedded_records = []
    for unit in code_units:
        content = unit["content"]
        embedding_vector = get_embedding(content, model="text-embedding-ada-002")  
        embedded_records.append({
            "language": unit["language"],
            "file": unit["file"],
            "name": unit["name"],
            "content": unit["content"],
            "embedding": embedding_vector
        })

    df = pd.DataFrame(embedded_records)
    df.to_csv(embeddings_file, index=False)
    Colors.print_colored(f"Embeddings saved to {embeddings_file}", Colors.GREEN)

    summary_msg = (f"Embeddings plugin completed.\n"
                   f"Processed {len(embedded_records)} code units from {len(all_files)} files.\n"
                   f"Saved to {embeddings_file}.\n")
    messages.append({"role": "assistant", "content": summary_msg})
    return messages


def parse_code_units(language: str, source: str) -> List[Dict[str, str]]:
    """
    Return a list of code units for the given language:
      - Python: uses Python AST to find top-level def, async def, and classes (including methods).
      - JavaScript/TypeScript: improved regex/scan approach for functions, classes, interfaces, types, exports, etc.
      - Everything else: treat entire file as a single code unit.
    """
    if language == "python":
        return parse_python_units(source)
    elif language in ["javascript", "typescript"]:
        return parse_js_ts_units(source, language)
    else:
        # default: one code unit
        return [{"name": f"FullFile_{language}", "content": source}]


##############################
#  PYTHON PARSING via `ast`  #
##############################

def parse_python_units(source: str) -> List[Dict[str, str]]:
    """
    Use Python's built-in 'ast' to parse out top-level functions, async functions, and classes 
    (including method definitions).
    """
    units = []

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        # If file has syntax errors, fallback to single block
        return [{"name": "FullFile_python_syntax_error", "content": source}]

    # We'll keep a mapping from node => (start_line, end_line, code_snippet)
    # so we can extract the actual source lines.
    lines = source.splitlines(True)

    # We define a helper to extract the snippet from line x to line y (1-based indexing in AST).
    def get_code_snippet(node):
        start = node.lineno - 1  # ast is 1-based
        end = node.end_lineno    # end_lineno is inclusive
        return "".join(lines[start:end])

    # We'll do a simple AST walk for top-level items
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            snippet = get_code_snippet(node)
            units.append({"name": node.name, "content": snippet})
        elif isinstance(node, ast.AsyncFunctionDef):
            snippet = get_code_snippet(node)
            units.append({"name": f"(async) {node.name}", "content": snippet})
        elif isinstance(node, ast.ClassDef):
            # We might also want to gather method definitions within this class
            class_snippet = get_code_snippet(node)
            units.append({"name": node.name, "content": class_snippet})
            # optional: gather method-level code
            for subnode in node.body:
                if isinstance(subnode, ast.FunctionDef):
                    method_snippet = get_code_snippet(subnode)
                    method_name = f"{node.name}.{subnode.name}"
                    units.append({"name": method_name, "content": method_snippet})
                elif isinstance(subnode, ast.AsyncFunctionDef):
                    method_snippet = get_code_snippet(subnode)
                    method_name = f"{node.name}.(async){subnode.name}"
                    units.append({"name": method_name, "content": method_snippet})

    return units


###############################################
#  JAVASCRIPT / TYPESCRIPT ADVANCED PARSING   #
###############################################

def parse_js_ts_units(source: str, language: str) -> List[Dict[str, str]]:
    """
    Enhanced scanning for JS/TS:
      - Detect 'function ' <name> 
      - 'class ' <name>
      - 'interface ' <name>
      - 'type ' <name> = 
      - arrow functions assigned to a variable: const x = (...) => { ... }
      - 'export' in front of any of these
    We'll attempt to collect code from the start to next item or end-of-file.
    """
    # We'll build a list of (match_start, match_end, name, code) blocks
    # by scanning the file with regex for known "headers," then capturing the block until the next header.
    lines = source.splitlines(True)
    matches = []
    i = 0
    length = len(lines)

    # Regex patterns for JS/TS "headers"
    # We'll try to capture:
    #   - export optional
    #   - function name(...) {
    #   - class name ...
    #   - interface name ...
    #   - type name = ...
    #   - const name = (args) => ...
    # Possibly we store the matched line, name, kind, etc.
    pattern = re.compile(
        r'^(export\s+)?'
        r'(function\s+([A-Za-z0-9_$]+)|'        # function myFunc
        r'class\s+([A-Za-z0-9_$]+)|'           # class MyClass
        r'interface\s+([A-Za-z0-9_$]+)|'       # interface MyInterface
        r'type\s+([A-Za-z0-9_$]+)\s*=|'        # type MyType =
        r'(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*\(?.*\)?\s*=>)'  # const myFunc = (...) => ...
    )

    # We'll define a function to read from start until we hit the next "header."
    def read_block(start_idx: int) -> (int, str):
        block_lines = [lines[start_idx]]
        j = start_idx + 1
        while j < length:
            # check if lines[j] matches the pattern
            if pattern.match(lines[j].strip()):
                break
            block_lines.append(lines[j])
            j += 1
        return j, "".join(block_lines)

    code_units = []

    while i < length:
        match = pattern.match(lines[i].strip())
        if match:
            # figure out name
            # groups: (export, function .., funcName, class .., className, interface..., interfaceName, type..., typeName, arrowName)
            export_kw, func_kw, func_name, class_kw, class_name, iface_kw, iface_name, type_name, arrow_name = (None,)*9
            # match groups
            export_kw = match.group(1)  # e.g. 'export '
            func_kw   = match.group(2)  # e.g. 'function myFunc'
            func_name = match.group(3)  # actual function name
            class_kw  = match.group(4)  # actual class name
            iface_kw  = match.group(5)  # actual interface name
            type_name = match.group(6)  # actual type name
            # The last part: arrow_name is group(7) if present
            arrow_name = match.group(7)

            # Now read block
            next_i, snippet = read_block(i)
            i = next_i

            # Build a user-friendly name
            if arrow_name:
                name = arrow_name
                # check if it's exported
                if export_kw:
                    name = f"export {arrow_name} (arrow)"
            elif func_name:
                name = func_name
                if export_kw:
                    name = f"export function {func_name}"
            elif class_name:
                name = class_name
                if export_kw:
                    name = f"export class {class_name}"
            elif iface_name:
                name = iface_name
                if export_kw:
                    name = f"export interface {iface_name}"
                else:
                    name = f"interface {iface_name}"
            elif type_name:
                name = f"type {type_name}"
                if export_kw:
                    name = f"export type {type_name}"
            else:
                # fallback
                name = "unknown_export"

            code_units.append({"name": name, "content": snippet})
        else:
            i += 1

    if not code_units:
        # If we found no recognized structures, treat entire file as single block
        return [{"name": f"FullFile_{language}", "content": source}]

    return code_units


###########################################
#  EMBEDDING & LOOKUP UTILS (unchanged)   #
###########################################

def capture_block(lines: List[str], start: int) -> (List[str], int):
    """
    [No longer used in these improved versions, but kept for reference if needed]
    Basic approach to read from 'start' until we see a new function/class or end-of-file.
    """
    results = []
    results.append(lines[start])
    i = start + 1
    while i < len(lines):
        strip = lines[i].strip()
        # naive detection
        if (strip.startswith("def ") or
            strip.startswith("class ") or
            strip.startswith("function ") or
            strip.startswith("interface ") or
            strip.startswith("type ") or
            re.match(r'^(const|let|var)\s+[A-Za-z0-9_$]+\s*=\s*\(?.*\)?\s*=>', strip)):
            break
        results.append(lines[i])
        i += 1
    return results, (i - start)


def get_embedding(text, model="text-embedding-ada-002"):
    """
    Example call to OpenAI's embeddings (adjust to your usage).
    """
    response = openai.embeddings.create(input=[text], model=model)
    response_data = json.loads(response.json())
    return response_data.get("data")[0].get("embedding")

@plugin
def lookup_embeddings(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    embeddings_file = os.path.join(args.exec_dir, args.embeddings or "embeddings.csv")
    if not os.path.exists(embeddings_file):
        # fallback approach to find it relative to the loaded .ll
        ll_dir_abs = os.path.abspath(args.ll_dir)
        load_abs = os.path.abspath(args.load)
        rel = os.path.relpath(load_abs, ll_dir_abs)  # e.g. "project/subdir.ll"
        base, ext = os.path.splitext(rel)
        if ext == ".ll":
            rel = base
        project_rel = rel
        embeddings_file = os.path.join(args.exec_dir, project_rel, args.embeddings or "embeddings.csv")
        if not os.path.exists(embeddings_file):
            Colors.print_colored(f"Embeddings file {embeddings_file} not found.", Colors.RED)
            return messages
    
    # let user pick which message has the query
    msg_index = get_valid_index(messages, f"message containing search query for {embeddings_file}", index) 
    query_string = messages[msg_index]['content'] if msg_index >= 0 else "No query provided"

    df = search_embeddings_with_df(embeddings_file, query_string)
    if df is None or df.empty:
        Colors.print_colored("No embeddings found or empty DataFrame.", Colors.RED)
        return messages

    # sort by descending similarity
    df_sorted = df.sort_values("similarities", ascending=False)

    top_3 = df_sorted.head(3)

    results = []
    results_str = "Top 3 matching code units:\n"
    for i, row in top_3.iterrows():
        full_snippet = row["content"]
        display_snippet = (full_snippet[:197] + "...") if len(full_snippet) > 200 else full_snippet
        
        results.append({
            "file": row['file'],
            "name": row['name'],
            "similarity": row['similarities'],
            "content": full_snippet  
        })
        
        results_str += f"({i+1}) File: {row['file']}\n"
        results_str += f"    Name: {row['name']}\n"
        results_str += f"    Similarity: {row['similarities']:.4f}\n"
        results_str += f"    Preview: {display_snippet}\n"
    
    print(results_str)

    messages.append({
        "role": "lookup_embeddings", 
        "content": "\n".join(f"({i+1}) File: {r['file']}\n    Name: {r['name']}\n    Similarity: {r['similarity']:.4f}\n    Content: {r['content'] + '...'}" for i, r in enumerate(results)),
    })
    return messages

def search_embeddings_with_df(embeddings_file: str, query: str):
    """
    A variation of 'search_embeddings' that returns the full DataFrame
    with a 'similarities' column, instead of just a string. 
    """

    def cosine_similarity(a, b):
        return sklearn_cosine_similarity(
            np.array(a).reshape(1, -1), np.array(b).reshape(1, -1)
        )[0][0]

    # Load CSV
    df = pd.read_csv(embeddings_file)
    if df.empty:
        return None
    
    # convert embedding column to actual lists
    df["embedding"] = df["embedding"].apply(lambda x: np.array(ast.literal_eval(x)))

    # embed the query using the *same model* as used for code (be sure to match dimension!)
    query_vec = get_embedding(query, model="text-embedding-ada-002")  # or the same model used for code

    # Compute similarity for each row
    df["similarities"] = df["embedding"].apply(lambda x: cosine_similarity(x, query_vec))
    return df