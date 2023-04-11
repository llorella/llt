import re
import os
import subprocess

def extract_code_blocks(completion):
    code_blocks = re.findall(r'```(\w+)?\n(.*?)```', completion, re.DOTALL)
    return code_blocks

def save_code_blocks(code_blocks):
    for idx, (language, code) in enumerate(code_blocks, 1):
        if language:
            file_extension = language.lower()
        else:
            file_extension = input("Can't get file type. Enter here or return to exit: ") or ".txt"

        filename = input(f"Enter name for code block {idx} or return for default: ") or f"code_block"
        filename = f"{filename}_{idx}.{file_extension}"
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