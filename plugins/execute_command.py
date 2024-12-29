# plugins/execute_command.py
import subprocess
from typing import List, Dict, Any
from plugins import plugin
from utils.helpers import get_valid_index
from utils.md_parser import parse_markdown_for_codeblocks

def run_code_block(language: str, code: str, skip_check: bool = False) -> str:
    """
    Example of running a snippet in python or bash.
    If skip_check=False, we prompt user. Otherwise we just run it.
    """
    args = []
    shell = False
    if language in ["bash", "shell", "sh"]:
        # Run as shell script
        args, shell = [code], True
    elif language in ["python", "py"]:
        args = ["python3", "-c", code]

    if not skip_check:
        user_input = input(f"Run {language} code? (y/N) ").strip().lower()
        if user_input != 'y':
            return "Skipped by user."

    try:
        result = subprocess.run(
            args,
            shell=shell,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        return result.stdout or "(No stdout)"
    except subprocess.CalledProcessError as e:
        return f"Error: {e}\nStderr:\n{e.stderr}"

@plugin
def execute_command(messages: List[Dict[str,Any]], args: Dict, index: int=-1) -> List[Dict[str,Any]]:
    """
    1. Extract code blocks from the selected message
    2. For each code block, prompt to run
    3. Append results to conversation
    """
    msg_index = get_valid_index(messages, "execute command of", index)
    content = messages[msg_index]["content"]
    blocks = parse_markdown_for_codeblocks(content)

    all_outputs = []
    for block in blocks:
        lang = block["language"]
        code = block["content"]
        output = run_code_block(lang, code, skip_check=args.get("non_interactive", False))
        all_outputs.append(output)

    # summarize results
    messages.append({
        "role": "assistant",
        "content": "\n".join(all_outputs)
    })
    return messages
