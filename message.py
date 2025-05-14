# message.py

import os
import json
from typing import Optional, Dict, List, Any

from tools import llt
from utils import input_handler, get_valid_index, Colors

class Message(Dict):
    role: str
    content: Any


@llt()
def load(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Load ll file containing conversation
    Type: string
    Default: default.ll
    flag: load
    short: ll
    """
    if not dict["non_interactive"] and not dict["auto"]:
        ll_path = input_handler.get_path_input(
            "Enter path to ll file",
            default=dict["load"],
            root_dir=dict["ll_dir"]
        )
    else:
        ll_path = os.path.join(dict["ll_dir"], dict["load"])
        
    os.makedirs(os.path.dirname(ll_path), exist_ok=True)

    if os.path.exists(ll_path):
        with open(ll_path, 'r') as file:
            messages = json.load(file)

    if not dict["non_interactive"]:
        Colors.print_colored(f"Loaded {len(messages)} messages from '{ll_path}'.", Colors.GREEN)

    dict["load"] = ll_path
    return messages


@llt()
def save(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Save current conversation to file
    Type: string
    Default: temp.ll
    flag: save
    short: s
    """
    if dict["save"] == ".":
        # if save is "." then save to the same file as load
        dict["save"] = dict["load"]
        
    if not dict["non_interactive"] and not dict["auto"]:
        ww_path = input_handler.get_path_input(
            "Enter path to save ll file",
            default=dict["save"] if dict["save"] != "temp.ll" else dict["load"],
            root_dir=dict["ll_dir"]
        )
    else:
        ww_path = os.path.join(dict["ll_dir"], dict["save"])

    os.makedirs(os.path.dirname(ww_path), exist_ok=True)

    with open(ww_path, "w") as file:
        json.dump(messages, file, indent=2)
    if not dict["non_interactive"]:
        Colors.print_colored(f"Saved {len(messages)} messages to '{ww_path}'.", Colors.GREEN)
    dict["save"] = ww_path
    return messages


@llt()
def prompt(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Add user prompt message
    Type: string
    Default: None
    flag: prompt
    short: p
    """
    new_message = Message(role=dict["role"], content=dict["prompt"])
    if not dict.get('non_interactive'):
        Colors.print_colored("Added new message to the conversation.", Colors.GREEN)
    dict["prompt"] = None
    return messages + [new_message]


@llt(needs_index=True)
def remove(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Remove a message from the conversation
    Type: bool
    Default: false
    flag: remove
    short:
    """
    # get_valid_index now converts negative indices to positive ones
    message_index = get_valid_index(messages, "remove", index)
    if message_index < 0: message_index = len(messages) + message_index
    before = messages[:message_index]
    after = messages[message_index + 1:]
    new_messages = before + after
    
    if not dict["non_interactive"]:
        Colors.print_colored(f"Removed message at index {message_index + 1}.", Colors.GREEN)
    return new_messages


@llt(needs_index=True)
def attach(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Attach a set of messages from file at specified index
    Type: string
    Default: bridge.ll
    flag: attach
    short:
    """
    if dict["attach"]:
        ll_path = os.path.join(dict["ll_dir"], dict["attach"])
    else:
        ll_path = input_handler.get_path_input(
            "Enter path to attach ll file",
            default=None,
            root_dir=dict["ll_dir"]
        )

    if ll_path is None:
        return messages

    with open(ll_path, 'r') as file:
        new_messages = json.load(file)

    # Handle negative indices
    if index < 0:
        index = len(messages) + index + 1
    
    # Ensure index is within bounds
    index = max(0, min(index, len(messages)))

    # Split messages at index and insert new messages
    messages_before = messages[:index]
    messages_after = messages[index:]
    messages = messages_before + new_messages + messages_after

    if not dict["non_interactive"]:
        Colors.print_colored(
            f"Attached {len(new_messages)} messages at index {index}.", 
            Colors.GREEN
        )
    return messages


@llt(needs_index=True)
def detach(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Detach a message from the conversation
    Type: bool
    Default: false
    flag: detach
    short:
    """
    if not dict.get('non_interactive') and not dict.get('auto'):
        index = get_valid_index(messages, "detach", index)
    selected_message = messages[index]
    messages = [selected_message]
    if not dict["non_interactive"]:
        Colors.print_colored(f"Detached message at index {index + 1}.", Colors.GREEN)
    return messages


@llt(needs_index=True)
def fold(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Fold contiguous messages of the same role into one
    Type: bool
    Default: false
    flag: fold
    short:
    """
    if not messages:
        return messages
        
    initial_length = len(messages)
    folded_messages_list = []
    
    if not messages: # Should be caught by the first check, but good for safety
        return messages

    # Iterate through a copy of messages to avoid issues if original dicts were planned to be modified
    # but here we are building a new list with new dicts for folded content.
    
    current_processing_message_dict = None

    for i, msg_dict_orig in enumerate(messages):
        # Ensure we are working with copies if we plan to modify content,
        # or construct new dicts for the folded_messages_list.
        # Here, we'll construct new dicts for current_processing_message_dict.
        
        if current_processing_message_dict is None:
            current_processing_message_dict = Message(**msg_dict_orig) # Create a new Message dict
        elif current_processing_message_dict["role"] == msg_dict_orig["role"]:
            # Append content to the current_processing_message_dict
            current_processing_message_dict["content"] = str(current_processing_message_dict.get("content","")) + "\n" + str(msg_dict_orig.get("content",""))
        else:
            # Roles differ, so the previous message is complete
            folded_messages_list.append(current_processing_message_dict)
            current_processing_message_dict = Message(**msg_dict_orig) # Start a new one

    # Add the last processed message
    if current_processing_message_dict is not None:
        folded_messages_list.append(current_processing_message_dict)
    
    folded_count = initial_length - len(folded_messages_list)
    if not dict.get("non_interactive"):
        Colors.print_colored(f"Folded {folded_count} message(s). Resulting in {len(folded_messages_list)} messages.", Colors.GREEN)
    return folded_messages_list


@llt(needs_index=True)
def insert(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Insert a new message at a specified index
    Type: bool
    Default: false
    flag: insert
    short:
    """
    if not dict.get('non_interactive'):
        message_index = get_valid_index(messages, "insert", index)
    else:
        message_index = index

    # Ensure index is within bounds for insertion
    # Python's list.insert handles this by clamping, but for constructing a new list:
    if message_index < 0:
        message_index = 0
    if message_index > len(messages):
        message_index = len(messages)
        
    new_message_to_insert = Message(role="user", content="")
    
    new_messages = messages[:message_index] + [new_message_to_insert] + messages[message_index:]
    
    Colors.print_colored(f"Inserted new message at index {message_index + 1}.", Colors.GREEN)
    return new_messages


@llt(needs_index=True)
def change_role(messages: List[Message], dict: Dict, index: int = -1) -> List[Message]:
    """
    Description: Modify the role of a message
    Type: bool
    Default: false
    flag: modify_role
    short: mr
    """
    if not dict.get('non_interactive'):
        index = get_valid_index(messages, "modify role of", index)
        new_role = input_handler.get_input("Select new role for the message", ["user", "assistant", "system", "tool"])
    else:
        new_role = dict.get('role', 'user') # Default to 'user' if not specified in non-interactive

    if not (0 <= index < len(messages)):
        if not dict.get('non_interactive', False): # Check if non_interactive is explicitly false
            Colors.print_colored(f"Error: Index {index} is out of bounds.", Colors.RED)
        return messages # Return original list if index is invalid

    # Create a new list with a new dictionary for the modified message
    new_messages_list = list(messages) # Shallow copy the list
    
    # Create a new dictionary for the message being changed to ensure immutability of original message dict
    original_message_dict = new_messages_list[index]
    modified_message_dict = Message(**original_message_dict) # Make a copy
    modified_message_dict["role"] = new_role
    
    new_messages_list[index] = modified_message_dict # Replace the dict in the copied list
    
    if not dict.get('non_interactive', False):
        Colors.print_colored(f"Modified role of message at index {index + 1} to '{new_role}'.", Colors.GREEN)
    return new_messages_list


@llt(needs_index=True)
def view(messages: List[Message], dict: Dict, index: int = 0) -> List[Message]:
    """
    Description: View messages with formatting
    Type: bool
    Default: false
    flag: view
    short: v
    param: all bool False
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
            "llt": Colors.YELLOW,
        }.get(role, Colors.WHITE)

        header = f"{color}[{role.capitalize()}]{Colors.RESET}"
        footer = f"{color}[/{role.capitalize()}]{Colors.RESET}"
        Colors.print_colored(header, color)

        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    print(item.get("text", ""))
                elif item.get("type") == "image_url":
                    Colors.print_colored(
                        f"Image path: {item.get('image_url', '')}", Colors.CYAN
                    )
        else:
            print(content)

        Colors.print_colored(footer, color)
        Colors.print_colored(f"Message {idx} of {len(messages)}", Colors.YELLOW)

    show_all = dict.get("all", False)
    if show_all:
        for i, msg in enumerate(messages, 1):
            view_helper(msg, i)
            print("-" * 50)
        Colors.print_colored(f"Total messages shown: {len(messages)}", Colors.YELLOW)
    else:
        # Clamp index to valid range
        if index < 0:
            index = len(messages) + index
        index = max(0, min(index, len(messages) - 1))
        view_helper(messages[index], index + 1)
        Colors.print_colored(f"Total messages shown: 1", Colors.YELLOW)
    return messages


@llt(needs_index=True)
def cut(messages: List[str], dict: Dict, index: int = -1) -> List[str]:
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
