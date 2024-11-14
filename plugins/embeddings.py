# embeddings.py

import os
import pandas as pd
from pathlib import Path
from typing import List, Dict
from utils import content_input, path_input

import openai
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine_similarity
import numpy as np


def get_embedding(text, model="text-embedding-3-small"):
    response = openai.embeddings.create(input=[text], model=model)
    print(response.json())
    return response.json().get("choices")


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


from plugins import plugin


@plugin
def embeddings(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    code_root = path_input("Enter the path to the code repository: ", os.getcwd())
    all_funcs = extract_functions_from_repo(code_root)

    df = pd.DataFrame(all_funcs)
    df["code_embedding"] = df["code"].apply(
        lambda x: get_embedding(x, model="text-embedding-3-small")
    )
    df["filepath"] = df["filepath"].map(lambda x: Path(x).relative_to(code_root))

    output_file = path_input(
        "Enter the path to save the embeddings CSV: ",
        os.path.join(args.exec_dir, "plugins/code_embeddings.csv"),
    )
    df.to_csv(output_file, index=False)

    messages.append(
        {
            "role": "assistant",
            "content": f"Embeddings created and saved to {output_file}",
        }
    )
    return messages


@plugin
def search(messages: List[Dict[str, any]], args: Dict) -> List[Dict[str, any]]:
    embeddings_file = path_input(
        "Enter the path to the embeddings CSV: ",
        os.path.join(args.exec_dir, "plugins/code_embeddings.csv"),
    )
    df = pd.read_csv(embeddings_file)
    df["code_embedding"] = df["code_embedding"].apply()

    query = content_input("Enter your search query: ")
    n = int(content_input("Enter the number of results to display: ") or "3")

    embedding = get_embedding(query, model="text-embedding-3-small")
    df["similarities"] = df.code_embedding.apply(
        lambda x: cosine_similarity(x, embedding)
    )

    res = df.sort_values("similarities", ascending=False).head(n)

    result_message = "Search results:\n\n"
    for _, r in res.iterrows():
        result_message += (
            f"{r.filepath}:{r.function_name}  score={round(r.similarities, 3)}\n"
        )
        result_message += "\n".join(r.code.split("\n")[:7])
        result_message += "\n" + "-" * 70 + "\n"

    messages.append({"role": "assistant", "content": result_message})
    return messages