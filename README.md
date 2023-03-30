# chat-cli

usage: test.py [-h] [-f FILE] [-p PROMPTS]

options:
  -h, --help            show this help message and exit
  -f FILE, --file FILE  JSON file containing history of previous runs.
  -p PROMPTS, --prompts PROMPTS
                        List of preset prompts, comma separated.

chat-cli is a single threaded runtime which synchronously loops through user prompts and assistant messages. The main loop finds an assistant message for every user prompt. Each assistant message references a user or system message, building a tractable way to load, store, and add to previous chats with predefined prompts and/or real time input. 