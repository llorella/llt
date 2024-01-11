from message import load_message, write_message, view_message, new_message, prompt_message
from editor import edit_message, include_file


def plugins():    
    #each user can write plugin via simple interface with messages

    plugins = {
        'presets': { 
            'file': 'out.txt',
            'role': 'user'
        },
        'commands': {
            'load' : load_message,
            'write' : write_message,
            'view' : view_message,
            'new' : new_message,
            'complete' : prompt_message,
            'edit' : edit_message,
            'file' : include_file        
        }
    }
    
    return plugins