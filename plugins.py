import completion
import message

completion_plugins = {
    'complete': completion.complete,
    'model': completion.model,
    'role': completion.role,
    'temperature': completion.temperature,
    'max_tokens': completion.max_tokens
}

message_plugins = {
    'load': message.load,
    'write': message.write,
    'view': message.view,
    'detach': message.detach,
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
