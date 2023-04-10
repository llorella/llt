import os
import sys
from message import Message


def plugins(msg: Message, config: dict):
    plugins = {
        'edit' : lambda: editor_plugin(config),
        'group': lambda: group_plugin(config),
        'exit' : sys.exit,                         
        'help' : lambda: _help_util(config),
        'save' : lambda: save_message(msg, config), 
        'load' : lambda: load_message(msg, config), 
        'view' : lambda: view_message(msg, config)
    }
    
    key_list = [key for key in plugins.keys()]
    for key in key_list:
        plugins[key[1 if key == 'exit' else 0]] = plugins[key]
        
    return plugins

def _help_util(config: dict):
    print("User options: ")
    for key, value in config['conversation']['user_options'].items():
        print(f"{key}: {value}")
    print(f"Model options (enter option name to read or change): { [key for key in config['api']['options'].keys()] }")
    print(f"Plugin options (enter option name to run): { [key for key in config['extensions'].keys()] }")
    print(f"Roles (enter role for next message): { config['conversation']['roles'] }")
    return None

def save_message(msg: Message, config: dict):
    save_file = input("Enter save file: ") or config['io']['input_file']
    path = os.path.join(config['io']['history_directory'], save_file)
    msg.save(path)
    print(f"Savied to {path}")
    return msg
    
def load_message(msg: Message, config: dict):
    load_file = input("Enter load filename: ")
    load_file = os.path.join(config['io']['history_directory'], load_file)
    load_message = Message.load(load_file)
    print(f"Message loaded. ")
    
    load_before_after = input("Press enter to overwrite, p to prepend, aa to append: ")
    if not load_before_after:
        msg = load_message
    if load_before_after == "p":
        current_message.get_root().prev = msg
        msg = current_message
    if load_before_after == "a":
        msg.get_root().prev = current_message
    return msg
    
def view_message(msg: Message, config: dict):
    depth = int(input("Enter depth: ")) or 1
    msg.view(depth)
    return msg

def extract_code_blocks(completion):
    code_blocks = re.findall(r'```(\w+)?\n(.*?)```', completion, re.DOTALL)
    return code_blocks

def save_code_blocks(code_blocks):
    for idx, (language, code) in enumerate(code_blocks, 1):
        if language:
            file_extension = language.lower()
        else:
            file_extension = input("Can't get file type. Enter here or return to exit: ") or ".txt"

        filename = f"code_block_{idx}.{file_extension}"
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
        
        subprocess.run(vim_command, shell=True)
    except Exception as e:
        print(f"Error: {e}")

def editor_plugin(msg: Message, config: dict):
    # 1. extrace_code_blocks from message
    code_blocks = extract_code_blocks(msg.content)
    # 2. save_code_blocks to file
    filename = save_code_blocks(code_blocks)
    # 3. edit source with editor
    edit_source(filename, config['plugins']['editor'])
    return msg

def group_plugin(msg: Message, config: dict):
   pass