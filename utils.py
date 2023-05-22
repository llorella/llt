import re
import os
import subprocess

extension_map = {
        'python' : 'py',
        'bash' : 'sh',
        'cpp' : 'cpp',
        'javascript' : 'js',
        'text': 'txt',
    }

def get_language_extension(language: str):
    if language not in extension_map:
        return None
    return extension_map[language]

def encode_code_blocks(filename: str):
    with open(filename, 'r') as file:
        code = file.read()
    ext = os.path.splitext(filename)[1][1:]
    language = [k for k, v in extension_map.items() if v == ext][0]
    if language is None:
        return f"```{code}```"
    return f"```{language}\n{code}\n```"

def extract_code_blocks(completion):
    code_blocks = re.findall(r'```(\w+)?\n(.*?)```', completion, re.DOTALL)
    return code_blocks

def save_code_blocks(code_blocks, save_dir: str = None):
    for idx, (language, code) in enumerate(code_blocks, 1):
        if language:
            file_extension = get_language_extension(language.lower())
        else:
            file_extension = input("Can't get language file extension. Enter extension here or return for .txt: ") or "txt"

        filename = input(f"Enter name for code block {idx} or return for default: ") or f"code_block"
        filename = f"{filename}.{file_extension}"
        if save_dir is not None:
            path = os.path.expanduser(save_dir)
            filename = os.path.join(path, filename)
        with open(filename, 'w') as file:
            file.write(code.strip())
        print(f"Saved code block {idx} as {filename}")
        return filename
    
def edit_source(filename: str, editor: str):
    try:
        if not os.path.isfile(filename):
            print(f"Error: File '{filename}' does not exist.")
            return
        edit_command = f"{editor} {filename}"
        
        subprocess.run(edit_command, shell=True)
    except Exception as e:
        print(f"Error: {e}")
        
import auto_complete_module

def custom_completer(text, state):
    options = auto_complete_module.auto_complete(text)
    if state < len(options):
        return options[state]
    else:
        return None
