import os
import sys
import utils
from utils import custom_completer
from message import Message
import requests
from pydantic import BaseModel
from typing import Dict, List, Set, Optional
import readline

yes_or_none = lambda x: x if x == 'yes' or x[0] == 'y' else None
 
class Action(BaseModel):
     user_id: str
     op: str
     source_id: str
     message: Optional[ Dict[str, str] ]

def _help(msg: Message, config: dict, args: Optional[ List ] = None):
    print("Available commands: ")
    return None

def _exit(msg: Message, config: dict, args: Optional[ List ] = None):
    print(f"Exiting...")
    sys.exit()

def set_auto_complete_path(directory: str)-> str:
    os.environ['AUTOCOMPLETE_PATH'] = os.path.expanduser(directory)
    return os.environ['AUTOCOMPLETE_PATH']
    
def prompt_for_filename(config: dict) -> str:
    save_dir = config['io']['save_dir']
    path = set_auto_complete_path(save_dir)
    return os.path.join(path, input("Enter filename: "))
    
def save_message(msg: Message, config: dict):
    save_file = prompt_for_filename(config)
    msg.save(save_file)
    print(f"Savied to {save_file}")
    return msg
    
def load_message(msg: Message, config: dict):
    load_file = prompt_for_filename(config)
    load_message = Message.load(load_file)
    
    load_before_after = input(f"Message history loaded.\nPress enter to overwrite, p to prepend, aa to append: ")
    
    if not load_before_after:
        msg = load_message
    if load_before_after == "a":
        load_message.get_root().prev = msg
        msg = load_message
    if load_before_after == "p":
        msg.get_root().prev = load_message
    return msg

def view_message(msg: Message, config: dict):
    depth = int(input("Enter depth: ")) or 1
    msg.view(depth)
    return msg

def new_message(msg: Message, config: dict, args: Optional[ List ] = None):
    role = input("Enter role: ")
    content = input("Enter content: ")
    return Message(role, content, msg)
    
def editor_plugin(msg: Message, config: Dict[ str, any ]):
    save_dir = os.path.expanduser(config['plugins']['source']['save_dir'])
    editor = config['plugins']['source']['editor']
    source = utils.save_code_blocks(utils.extract_code_blocks(msg.content), save_dir)
    
    utils.edit_source(source, editor)
    load_source = input("Load source? (Y/n): ")
    
    editor_message = msg if yes_or_none(load_source) is None else Message("user", utils.encode_code_blocks(source), msg, 0, msg.options)
    return editor_message
    

abbv_exc = ['exit']

abbv = lambda x: x[0] if x not in abbv_exc else x[1]
pairs = lambda arr: [ (x, abbv(x)) for x in arr if len(x) > 1 ]

def generate_plugin_func(func):
    return lambda msg, config: func(msg, config)

def plugins():
    abbv = lambda x: x[0] if x not in abbv_exc else x[1]
    
    #add startup plugins so they can be used asynchonously on startup
    
    readline.set_completer(custom_completer)
    readline.parse_and_bind("tab: complete")
    
    plugin_funcs = {
        'exit' :  _exit,                         
        'help' :  _help,
        'save' :  save_message,
        'load' :  load_message, 
        'view' :  view_message,
        'new'  :   new_message,
        'edit' :  editor_plugin
    }
    
    plugins = {name: generate_plugin_func(func) for name, func in plugin_funcs.items()}
    
    keys = list(plugins.keys())
    for key in keys:
        plugins[abbv(key)] = plugins[key]
    
    return plugins



""" async def group_plugin(msg: Message = None, config: dict = None):
	# 0, 1, 2
    if not config['source']['user_id']: 
        user_id = input("Enter user id: ")
        config['source']['user_id'] = user_id
    if not config['source']['group_id']:
        group_id = input("Enter group id: ")
    if not config['source']['source']:
        source_id = input("Enter source id: ")
        config['source']['source'] = source_id
        
    create_group = requests.post(f"{config['source']['url']}/groups", json={ "group_id": "{group_id}", "user_id": "{user_id}", source_id: "{source_id}" })
    
    if create_group.status_code == 200:
        async with connect(f"ws://localhost:8000/groups/{group_id}/ws") as websocket:
            while True:    
                op = input("Enter op (get or prompt): ")
                if action == "x":
                    _exit(msg, config)
                if action != "get" and action != "prompt":
                    print("Invalid op.")
                    continue
                else:
                    action = Action(user_id=user_id, op=op, source_id=source_id, message=msg.to())
                    send_action = await websocket.send(action)
                    return send_action
                    
    else:
        print(create_group.text)
        raise Exception(f"Error creating group {group_id}.")
    
    
    #user can edit original source file, get partial feedback, or wait for full source update
    
    #source starts on first write piped from model to user
     """
    
