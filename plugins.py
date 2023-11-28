from message import load_message, write_message, view_message, new_message, prompt_message

def plugins():    
    #add startup plugins so they can be used asynchonously on startup
    #define types for these structs
    #each user has defined plugins code

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
            'complete' : prompt_message
        }
    }
    
    return plugins


""" def edit_message(msg: Optional[Message], file: Optional[str]):
    source = utils.save_code_blocks(utils.extract_code_blocks(msg.content), save_dir)
    
    utils.edit_source(source, editor)
    load_source = input("Load source? (Y/n): ")
    
    editor_message = msg if yes_or_none(load_source) is None else Message("user", utils.encode_code_blocks(source), msg, 0, msg.options)
    return editor_message """


    

""" abbv_exc = ['exit']

abbv = lambda x: x[0] if x not in abbv_exc else x[1]
pairs = lambda arr: [ (x, abbv(x)) for x in arr if len(x) > 1 ]

def generate_plugin_func(func):
    return lambda msg, config: func(msg, config) """