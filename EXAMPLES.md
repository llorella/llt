
### Self improvement workflow ###
Given that you invoke llt in its own source code container: 
```llt --load llt-plugin-hook --exec_dir , --file search.py --completiom --edit -n```

```python
from message import Message

#..main() code
@plugin
def search(messages: List[Message], args: Dict[str, any]):
  index = get_user_index(messages, -1):
  search_message = messages[index]
```

Search.py's functionality is now accessible to llt as a plugin, and can be invoked at runtime or at the command line (--search). 
