import message
message_plugins = {
    'load': message.load,
    'write': message.write,
    'view': message.view,
    'detach': message.detach,
    'fold': message.append,
    'cut': message.cut,
    'insert': message.insert,
    'remove': message.remove,
    'new': message.new
}

util_plugins = {
    'help': lambda messages, args: print(f"({', '.join(plugins.keys())}): available plugins."),
    'quit': lambda messages, args: exit(0)
}

import pyperclip
clipboard_plugins = {
    'copy': lambda messages, args: pyperclip.copy(messages[-1]['content']),
    'paste': lambda messages, args: messages.append({'role': args.role, 'content': pyperclip.paste()})
}

plugins = { **message_plugins, **util_plugins, **clipboard_plugins }

plugins['help'] = lambda messages, args: (print(f"Available commands (press tab to autocomplete):\n({', '.join(plugins.keys())})"), messages)[-1]

def plugin(func):
    plugins[func.__name__] = func
    return func
#llt> programtically load messages.
