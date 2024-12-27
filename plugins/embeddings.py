# embeddings.py

import os
import sys
import pandas as pd
from pathlib import Path
from typing import List, Dict
import json
import ast


import openai
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity
import numpy as np

from plugins import plugin
from utils import path_input, get_valid_index


def get_embedding(text, model="text-embedding-3-small"):
    response = openai.embeddings.create(input=[text], model=model)
    response_data = json.loads(response.json())
    return response_data.get("data")[0].get("embedding")


def cosine_similarity(a, b):
    return sklearn_cosine_similarity(
        np.array(a).reshape(1, -1), np.array(b).reshape(1, -1)
    )[0][0]


def get_function_name(code):
    DEF_PREFIXES = ["def ", "async def "]
    for prefix in DEF_PREFIXES:
        if code.startswith(prefix):
            return code[len(prefix) : code.index("(")]
    return None


def get_until_no_space(all_lines, i):
    ret = [all_lines[i]]
    for j in range(i + 1, len(all_lines)):
        if len(all_lines[j]) == 0 or all_lines[j][0] in [" ", "\t", ")"]:
            ret.append(all_lines[j])
        else:
            break
    return "\n".join(ret)


def get_functions(filepath):
    with open(filepath, "r") as file:
        all_lines = file.read().replace("\r", "\n").split("\n")
        for i, l in enumerate(all_lines):
            if l.startswith("def ") or l.startswith("async def "):
                code = get_until_no_space(all_lines, i)
                function_name = get_function_name(code)
                yield {
                    "code": code,
                    "function_name": function_name,
                    "filepath": filepath,
                }


def extract_functions_from_repo(code_root):
    code_files = list(Path(code_root).glob("**/*.py"))
    all_funcs = [
        func for code_file in code_files for func in get_functions(str(code_file))
    ]
    return all_funcs

def write_embeddings(code_root: str) -> None:
    all_funcs = extract_functions_from_repo(code_root)
    print(all_funcs)
    df = pd.DataFrame(all_funcs)
    print(df.columns)
    df["code_embedding"] = df["code"].apply(
        lambda x: get_embedding(x, model="text-embedding-ada-002")
    )
    #df["filepath"] = df["filepath"].map(lambda x: Path(x).relative_to(code_root).as_posix())
    df.to_csv(os.path.join(code_root, "embeddings.csv"), index=False)

def search_embeddings(embeddings_file: str, query: str) -> Dict[str, any]:
    df = pd.read_csv(embeddings_file)
    
    # convert back to actual lists
    df["code_embedding"] = df["code_embedding"].apply(lambda x: np.array(ast.literal_eval(x)))

    df["similarities"] = df["code_embedding"].apply(
        lambda x: cosine_similarity(x, get_embedding(query))
    )
    
    return df.sort_values("similarities", ascending=False).head(3).to_string(index=False)


@plugin
def embeddings(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    if not args.load:
        code_root = path_input(os.path.join(args.exec_dir, "untitled"), args.exec_dir)
    else:
        ll_dir_abs = os.path.abspath(args.ll_dir)
        load_abs = os.path.abspath(args.load)
        rel = os.path.relpath(load_abs, ll_dir_abs)  # e.g. "project/subdir.ll"

        base, ext = os.path.splitext(rel)
        if ext == ".ll":
            rel = base

        code_root = os.path.join(args.exec_dir, rel)
    
    if os.path.exists(code_root) and not os.path.isdir(code_root):
        print("Code root path for embeddings exists and is a file. Recursively calling embeddings for retry (portal).")
        return embeddings(messages, args)
    
    os.makedirs(code_root, exist_ok=True)
    
    if os.path.exists(os.path.join(code_root, "embeddings.csv")):
        user_confirm = input(f"Embeddings file already exists at {code_root}/embeddings.csv. Overwrite? (y for yes, any other key to cancel): ")
        if user_confirm.lower() != 'y':
            return messages
        
    write_embeddings(code_root)   
    messages.extend([
        {
            "role": "assistant",
            "content": f"Embeddings created and saved to {code_root}/embeddings.csv. Running search on it now, in llt.",
        },
        {
            "role": "llt",
            "content": "search",
        }]
    )
    args.embeddings = code_root
    return messages


@plugin
def cmd_query(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    embeddings_file = path_input(args.embeddings) if args.embeddings else os.path.join(os.getcwd(), "plugins/code_embeddings.csv")
    index = get_valid_index(messages, f"message containing search query for {embeddings_file}", index) 

    results = search_embeddings(embeddings_file, messages[index]['content'] if index else "edit this message")
    print(f"Search results:\n{results}")
    #messages.append({"role": "tool", "content": results}, {"role": "llt", "content": "Search results:\n\n"})
    messages.append({"role": "tool", "content": results})
    return messages


if __name__ == "__main__":
    # One argument so far: the path to the code repository
    print(len(sys.argv))
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]}")
        sys.exit(1)
    
    # at runtime, 
    code_root = sys.argv[1]
    if code_root.startswith("~"):
        code_root = os.path.expanduser(code_root)
    elif code_root.startswith("."):
        code_root = os.path.join(os.getcwd(), code_root)
    embeddings_path = os.path.join(code_root, "embeddings.csv")
    if os.path.exists(embeddings_path):
        print(f"Embeddings file already exists at {embeddings_path}")
    else:
        write_embeddings(code_root)
    print(f"Embeddings saved to {code_root}/embeddings.csv")
    
    if len(sys.argv) > 2:
        query = sys.argv[2]
        results = search_embeddings(embeddings_path, query)
        print(results)
    