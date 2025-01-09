# message.py

import os
import json
from typing import Optional, Dict, List

from plugins import plugin
from utils.input_utils import path_input, get_valid_index, list_input
from utils.colors import Colors


class Message(Dict):
    role: str
    content: any

@plugin
def load(messages: List[Message], args: Dict, index: int = -1)  -> List[Message]:
    if not args.load:
        args.load = "default"
    ll_path = os.path.join(args.ll_dir, args.load)
    if not args.non_interactive:
        ll_path = path_input(ll_path, args.ll_dir)
    if not os.path.exists(ll_path):
        os.makedirs(os.path.dirname(ll_path), exist_ok=True)
    else:
        with open(ll_path, 'r') as file:
            messages = json.load(file)
    args.load = ll_path
    return messages

@plugin
def write(messages: List[Message], args: Dict, index: int = -1)  -> List[Message]:
    if args.write:
        if (args.write == "."):
            args.write = args.load
        ll_path = os.path.join(args.ll_dir, args.write)
        args.write = None
    else:
        ll_path = path_input(args.load, args.ll_dir) if not args.non_interactive else os.path.join(args.ll_dir, args.load)
    os.makedirs(os.path.dirname(ll_path), exist_ok=True)
    with open(ll_path, "w") as file:
        json.dump(messages, file, indent=2)
    if not args.non_interactive:
        Colors.print_colored(
            f"Saved {len(messages)} messages to '{ll_path}'.", Colors.GREEN
        )
    args.load = ll_path
    return messages

@plugin
def prompt(messages: List[Message], args: Dict, index: int = -1)  -> List[Message]:
    message = Message(role=args.role, content=args.prompt)
    messages.append(message)
    if not args.non_interactive:
        Colors.print_colored(f"Added new message to the conversation.", Colors.GREEN)
    return messages

@plugin
def remove(
    messages: List[Message], args: Optional[Dict] = None, index: int = -1
) -> List[Message]:
    """
    Remove a message at a specified index.
    """
    message_index = (
        get_valid_index(messages, "remove", index)
        if not getattr(args, "remove", None)
        else int(args.remove)
    )
    messages.pop(message_index)
    if not args.non_interactive:
        Colors.print_colored(f"Removed message at index {message_index + 1}.", Colors.GREEN)
    setattr(args, "remove", None)
    return messages

@plugin
def attach(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    """
    Attach another conversation history to the current one.
    """
    if args.attach:
        ll_path = os.path.join(args.ll_dir, args.attach)
        args.attach = None
    else:
        ll_path = path_input(None, args.ll_dir)
        
    if ll_path is None:
        return messages
    
    with open(ll_path, 'r') as file:
        new_messages = json.load(file)
        
    messages.extend(new_messages)
    if not args.non_interactive: Colors.print_colored(f"Attached {len(new_messages)} messages to the current conversation.", Colors.GREEN)
    return messages

@plugin
def detach(
    messages: List[Message], args: Optional[Dict] = None, index: int = -1
) -> List[Message]:
    """
    Detach (extract) a message from the conversation.
    """
    if args.detach:
        index = args.detach
        args.detach = None
    else:
        index = get_valid_index(messages, "detach", index) 
        
    detached_message = messages.pop(index)
    
    if not args.non_interactive: Colors.print_colored(
        f"Detached message at index {index + 1}.", Colors.GREEN
    )
    
    return [detached_message]

@plugin
def fold(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    """
    Arg: --fold
    Short: --f
    Help: "Fold consecutive messages from the same role into one."
    Type: bool
    """        
    initial_length = len(messages)
    while len(messages) > 1 and messages[-2]["role"] == args.role:
        messages[-2]["content"] += "\n" + messages[-1]["content"]
        messages.pop()
    folded_messages = initial_length - len(messages)
    print(f"Folded {folded_messages} message(s).")
    return messages

@plugin
def insert(
    messages: List[Message], args: Optional[Dict] = None, index: int = -1
) -> List[Message]:
    """
    Insert a new message at a specified index.
    """
    message_index = get_valid_index(messages, "insert", index)
    new_message = Message(role=args.role, content=args.prompt)
    messages.insert(message_index, new_message)
    Colors.print_colored(
        f"Inserted new message at index {message_index + 1}.", Colors.GREEN
    )
    return messages

@plugin
def role(
    messages: List[Message], args: Optional[Dict] = None, index: int = -1
) -> List[Message]:
    """
    Modify the role of an existing message.
    """
    index = get_valid_index(messages, "modify role of", index)
    new_role = list_input(
        ["user", "assistant", "system", "tool"], "Select new role for the message"
    )
    messages[index]["role"] = new_role
    Colors.print_colored(
        f"Modified role of message at index {index + 1} to '{new_role}'.", Colors.GREEN
    )
    return messages

@plugin
def view(
    messages: List[Message], args: Optional[Dict] = None, index: int = 0
) -> List[Message]:
    """
    View all messages in the conversation with styled formatting.
    """
    if not messages:
        Colors.print_colored("No messages to display.", Colors.YELLOW)
        return messages

    def view_helper(message: Message, idx: int) -> None:
        role = message["role"]
        content = message["content"]
        color = {
            "user": Colors.GREEN,
            "assistant": Colors.MAGENTA,
            "system": Colors.BLUE,
            "tool": Colors.CYAN,
        }.get(role, Colors.WHITE)

        header = f"{color}[{role.capitalize()}]{Colors.RESET}"
        footer = f"{color}[/{role.capitalize()}]{Colors.RESET}"
        Colors.print_colored(header, color)

        if isinstance(content, list):
            for item in content:
                if item["type"] == "text":
                    print(item["text"])
                elif item["type"] == "image_url":
                    Colors.print_colored(
                        f"Image path: {item['image_url']['url']}", Colors.CYAN
                    )
        else:
            print(content)

        Colors.print_colored(footer, color)
        Colors.print_colored(f"Message {idx} of {len(messages)}", Colors.YELLOW)

    for i, msg in enumerate(messages, 1):
        view_helper(msg, i)
        print("-" * 50)  # Separator between messages
    Colors.print_colored(f"Total messages shown: {len(messages)}", Colors.YELLOW)
    return messages

@plugin
def cut(messages: List[str], args: Dict, index: int = -1)  -> List[str]:
    if not messages: return messages
    try:
        values = input(
            "Enter start and optional end index separated by comma (e.g., 2,5): "
        ).split(",")
        start = max(0, int(values[0]) - 1)
        end = int(values[1]) if len(values) > 1 else start + 1
    except (ValueError, IndexError):
        Colors.print_colored(
            "Invalid input. Please enter numbers in the correct format.", Colors.RED
        )
        return messages
    if start >= len(messages) or end > len(messages) or start >= end:
        Colors.print_colored(
            "Invalid range. Make sure start is less than end and within the message list.",
            Colors.RED,
        )
        return messages
    confirmation = (
        input(
            f"Cutting messages from position {start + 1} to {end}. Proceed? (y for yes, any other key to cancel): "
        )
        .strip()
        .lower()
    )
    if confirmation != "y":
        Colors.print_colored("Cut operation canceled.", Colors.YELLOW)
        return messages
    Colors.print_colored(f"Cutting messages from {start + 1} to {end}.", Colors.GREEN)
    return messages[start:end]
