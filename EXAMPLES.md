
### Self improv ###
Givrn that you init llt in source code container: 
```llt --load llt-plugin-hook --exec_dir , --file search.py --completiom -n```

```python
from message import Message

#..main() code
@plugin
def search(messages: List[Message], args: Dict[str, any]):
  index = get_user_index(messages, -1):
  search_message = messages[index]
```
