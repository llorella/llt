# message.py

import os
import json
from typing import Optional, Dict, List

from plugins import llt
from utils.input_utils import path_input, get_valid_index, list_input
from utils.colors import Colors


class Message(Dict):
    role: str
    content: any


@llt
def load(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Load ll file containing conversation
    Type: string
    Default: default.ll
    flag: load
    short: ll
    """
    if not args.non_interactive:
        ll_path = path_input(args.load, args.ll_dir)
    else:
        ll_path = os.path.join(args.ll_dir, args.load)

    os.makedirs(os.path.dirname(ll_path), exist_ok=True)

    if os.path.exists(ll_path):
        with open(ll_path, 'r') as file:
            messages = json.load(file)

    if not args.non_interactive:
        Colors.print_colored(f"Loaded {len(messages)} messages from '{ll_path}'.", Colors.GREEN)

    args.load = ll_path
    return messages


@llt
def write(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Write conversation to file
    Type: string
    Default: None
    flag: write
    short: w
    """
    if args.write == ".":
        # if write is "." then write to the same file as load
        args.write = args.load
    if not args.non_interactive and not args.write:
        ww_path = path_input(args.load, args.ll_dir)
    else:
        ww_path = os.path.join(args.ll_dir, args.write)

    os.makedirs(os.path.dirname(ww_path), exist_ok=True)

    with open(ww_path, "w") as file:
        json.dump(messages, file, indent=2)
    if not args.non_interactive:
        Colors.print_colored(f"Saved {len(messages)} messages to '{ww_path}'.", Colors.GREEN)
    args.write = ww_path
    return messages


@llt
def prompt(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Add user prompt message
    Type: string
    Default: None
    flag: prompt
    short: p
    """
    message = Message(role=args.role, content=args.prompt)
    messages.append(message)
    if not args.non_interactive:
        Colors.print_colored("Added new message to the conversation.", Colors.GREEN)
    return messages


@llt
def remove(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    """
    Description: Remove a message from the conversation
    Type: bool
    Default: false
    flag: remove
    short:
    """
    message_index = get_valid_index(messages, "remove", index) if not getattr(args, "remove", False) else index
    messages.pop(message_index)
    if not args.non_interactive:
        Colors.print_colored(f"Removed message at index {message_index + 1}.", Colors.GREEN)
    setattr(args, "remove", False)
    return messages


@llt
def attach(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    """
    Description: Attach a set of messages from file
    Type: string
    Default: None
    flag: attach
    short:
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
    if not args.non_interactive:
        Colors.print_colored(f"Attached {len(new_messages)} messages to the current conversation.", Colors.GREEN)
    return messages


@llt
def detach(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    """
    Description: Detach a message from the conversation
    Type: bool
    Default: false
    flag: detach
    short:
    """
    if args.detach:
        args.detach = False
    else:
        index = get_valid_index(messages, "detach", index)

    detached_message = messages.pop(index)

    if not args.non_interactive:
        Colors.print_colored(f"Detached message at index {index + 1}.", Colors.GREEN)

    return [detached_message]


@llt
def fold(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    """
    Description: Combine last user message with the previous user message
    Type: bool
    Default: false
    flag: fold
    short:
    """
    initial_length = len(messages)
    while len(messages) > 1 and messages[-2]["role"] == args.role:
        messages[-2]["content"] += "\n" + messages[-1]["content"]
        messages.pop()
    folded_messages = initial_length - len(messages)
    print(f"Folded {folded_messages} message(s).")
    return messages


@llt
def insert(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    """
    Description: Insert a new message at a specified index
    Type: bool
    Default: false
    flag: insert
    short:
    """
    message_index = get_valid_index(messages, "insert", index)
    new_message = Message(role=args.role, content=args.prompt)
    messages.insert(message_index, new_message)
    Colors.print_colored(f"Inserted new message at index {message_index + 1}.", Colors.GREEN)
    return messages


@llt
def role(messages: List[Message], args: Optional[Dict] = None, index: int = -1) -> List[Message]:
    index = get_valid_index(messages, "modify role of", index)
    new_role = list_input(["user", "assistant", "system", "tool"], "Select new role for the message")
    messages[index]["role"] = new_role
    Colors.print_colored(f"Modified role of message at index {index + 1} to '{new_role}'.", Colors.GREEN)
    return messages


@llt
def view(messages: List[Message], args: Optional[Dict] = None, index: int = 0) -> List[Message]:
    """
    Description: View messages with formatting
    Type: bool
    Default: false
    flag: view
    short: v
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


@llt
def cut(messages: List[str], args: Dict, index: int = -1) -> List[str]:
    """
    Description: Cut messages within a specified range
    Type: bool
    Default: false
    flag: cut
    short: c
    """
    if not messages:
        return messages
    try:
        values = input("Enter start and optional end index separated by comma (e.g., 2,5): ").split(",")
        start = max(0, int(values[0]) - 1)
        end = int(values[1]) if len(values) > 1 else start + 1
    except (ValueError, IndexError):
        Colors.print_colored("Invalid input. Please enter numbers in the correct format.", Colors.RED)
        return messages
    if start >= len(messages) or end > len(messages) or start >= end:
        Colors.print_colored("Invalid range. Make sure start is less than end and within the message list.", Colors.RED)
        return messages

    confirmation = input(f"Cutting messages from position {start + 1} to {end}. Proceed? (y for yes): ").strip().lower()
    if confirmation != "y":
        Colors.print_colored("Cut operation canceled.", Colors.YELLOW)
        return messages

    Colors.print_colored(f"Cutting messages from {start + 1} to {end}.", Colors.GREEN)
    return messages[start:end]
