import completion
import message

completion_plugins = {
    'complete': completion.complete,
    'model': completion.model,
    'change_role': completion.change_role,
    'temperature': completion.temperature,
    'max_tokens': completion.max_tokens,
    'modify_args': completion.modify_args,
    'get_args': completion.get_args
}

message_plugins = {
    'load': message.load,
    'write': message.write,
    'view': message.view,
    'detach': message.detach,
    'attach': message.attach,
    'fold': message.fold,
    'cut': message.cut,
    'insert': message.insert,
    'remove': message.remove,
    'prompt': message.prompt
}

util_plugins = {
    'help': lambda messages, args, index=-1: print(f"({', '.join(plugins.keys())}): available plugins."),
    'quit': lambda messages, args, index=-1: exit(0)
}

plugins = { **completion_plugins, **message_plugins, **util_plugins }

plugins['help'] = lambda messages, args, index=-1: (print(f"Available commands (press tab to autocomplete):\n({', '.join(plugins.keys())})"), messages)[-1]

def plugin(func):
    plugins[func.__name__] = func
    return func
#llt> programtically load messages.
#lt>

# file, function, url table