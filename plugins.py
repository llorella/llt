import os
import sys
import utils
from message import Message

def _help(msg: Message, config: dict):
    print("User options: ")
    for key, value in config['conversation']['user_options'].items():
        print(f"{key}: {value}")
    print(f"Model options (enter option name to read or change): { [key for key in config['api']['options'].keys()] }")
    print(f"Plugin options (enter option name to run): { [key for key in config['extensions'].keys()] }")
    print(f"Roles (enter role for next message): { config['conversation']['roles'] }")
    return None

def _exit(msg: Message, config: dict):
    print(f"Exiting...")
    sys.exit()
    
##################################################
# message wrappers to behave like plugins
    
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

def new_message(msg: Message, config: dict):
    role = input("Enter role: ")
    content = input("Enter content: ")
    return Message(role, content, msg)

exc = ['exit']
abbv = lambda x: x[0] if x not in exc else x[1]
pairs = lambda arr: [ (x, abbv(x)) for x in arr if len(x) > 1 ]

def plugins():
    exc = ['exit']
    abbv = lambda x: x[0] if x not in exc else x[1]
    
    plugins = {
        'exit' :  _exit,                         
        'help' :  _help,
        'save' :  save_message,
        'load' :  load_message, 
        'view' :  view_message,
        'new'  :   new_message,
        'edit' :  editor_plugin,
        'group':  group_plugin
    }
    
    plugins = { name: lambda msg, config, func=func: func(msg, config) for name, func in plugins.items() }
    keys = list(plugins.keys())
    for key in keys:
        plugins[abbv(key)] = plugins[key]
    
    return plugins

def editor_plugin(msg: Message, config: dict):
    code_blocks = utils.extract_code_blocks(msg.content)
    filename = utils.save_code_blocks(code_blocks)
    utils.edit_source(filename, config['plugins']['editor'])
    
    return msg

def group_plugin(msg: Message, config: dict):
    try:
        group = config['plugins']['group']
    except KeyError:
        group = input("No group name found in config. Enter group name or return to continue: ")
    
    