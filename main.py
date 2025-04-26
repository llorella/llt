#!/usr/bin/env python3
"""
main.py - llt, the little language terminal

A functional implementation of the llt that processes commands and manages 
conversations with language models. This version follows functional programming principles 
and careful parameter ordering inspired by Haskell's design patterns, while maintaining
compatibility with the existing tool system.
"""

import os
import sys
import time
import json
import argparse
import traceback
import uuid
import datetime
import hashlib
import textwrap
from typing import List, Dict, Callable, Optional, TypeVar, Any, Tuple, Union, cast
from dataclasses import dataclass
from functools import reduce
from collections import deque

from logger import llt_logger
from utils import Colors, llt_interactive_input, parse_interactive_input
from tools import (
    load_tools,
    add_tool_arguments,
    init_cmd_map,
    schedule_startup_commands,
    ScheduledCommand,
    pack_namespaced_args,
    registry_to_json_schema,
    get_plugin_args
)

# Type aliases for improved readability and type safety
Message = Dict[str, Any]
Messages = List[Message]
Context = Dict[str, Any]
CommandMap = Dict[str, Callable]
T = TypeVar('T')
R = TypeVar('R')

MessagePlaceholder = Dict[str, Any]

@dataclass(frozen=True)
class AppState:
    """
    Immutable application state container with tool compatibility helpers.
    
    Attributes:
        messages: List of conversation messages
        context: Application configuration and state
        command_queue: Queue of commands to be executed
    """
    messages: Messages
    context: Context
    command_queue: deque[ScheduledCommand]

    def with_messages(self, new_messages: Messages) -> 'AppState':
        """Create new state with updated messages."""
        new_context = dict(self.context)
        new_context.pop("last_log_id", None)
        return AppState(new_messages, self.context, self.command_queue)

    def with_context(self, new_context: Context) -> 'AppState':
        """Create new state with updated context."""
        return AppState(self.messages, new_context, self.command_queue)

    def with_queue(self, new_queue: deque[ScheduledCommand]) -> 'AppState':
        """Create new state with updated command queue."""
        return AppState(self.messages, self.context, new_queue)

    def to_tool_args(self) -> Tuple[Messages, Context]:
        """Convert state to tool-compatible arguments."""
        return self.messages.copy(), dict(self.context)

    @classmethod
    def from_tool_result(
        cls,
        messages: Messages,
        context: Context,
        command_queue: deque[ScheduledCommand]
    ) -> 'AppState':
        """Create new state from tool execution results."""
        return cls(messages, context, command_queue)

class FunctionComposition:
    """Helpers for functional composition and monadic operations."""
    
    @staticmethod
    def compose(*functions: Callable[[T], T]) -> Callable[[T], T]:
        """
        Compose multiple functions right to left (Haskell style).
        """
        return reduce(lambda f, g: lambda x: f(g(x)), functions)

    @staticmethod
    def bind(value: T, func: Callable[[T], R]) -> R:
        """
        Monadic bind operation.
        """
        return func(value)

    @staticmethod
    def safe_execute(f: Callable[..., T], default: T) -> Callable[..., T]:
        """
        Wrap function execution with error handling.
        """
        def wrapper(*args, **kwargs) -> T:
            try:
                return f(*args, **kwargs)
            except Exception as e:
                llt_logger.log_error(str(e), {"traceback": traceback.format_exc()})
                print(f"{Colors.RED}Error: {e}\n{traceback.format_exc()}{Colors.RESET}")
                return default
        return wrapper

def calculate_context_delta(old_context: Context, new_context: Context) -> Dict[str, Any]:
    """Calculate the difference between two context dictionaries."""
    delta = {}
    old_keys = set(old_context.keys())
    new_keys = set(new_context.keys())

    # Check for changed and added keys
    for key in new_keys:
        # Ignore internal logging state
        if key in ["session_id", "last_log_id"]:
            continue
        if key not in old_keys or old_context[key] != new_context[key]:
            delta[key] = new_context[key]

    # Check for removed keys
    for key in old_keys:
        # Ignore internal logging state
        if key in ["session_id", "last_log_id"]:
            continue
        if key not in new_keys:
            delta[key] = None # Indicate removal
    return delta

def calculate_messages_delta(old_messages: Messages, new_messages: Messages) -> Tuple[List[MessagePlaceholder], List[int]]:
    """
    Calculate added message placeholders. Assumes messages are primarily appended.
    Handles the specific case where the last message might be removed (tool command).
    Returns (added_message_placeholders, removed_indices).
    """
    old_len = len(old_messages)
    new_len = len(new_messages)

    def create_placeholder(message: Message, index: int) -> MessagePlaceholder:
        content = message.get("content", "")
        # Ensure content is string if not already (for hashing)
        content_str = json.dumps(content) if not isinstance(content, str) else content
        content_bytes = content_str.encode('utf-8')
        return {
            "type": "message_ref",
            "role": message.get("role", "unknown"),
            "content_length": len(content_bytes),
            "content_sha256": hashlib.sha256(content_bytes).hexdigest(),
            "index_in_new_state": index
        }

    # If no old messages, all new messages are added
    if not old_messages:
        placeholders = [create_placeholder(msg, i) for i, msg in enumerate(new_messages)]
        return placeholders, []

    # Simple append case
    if new_len > old_len and new_messages[:old_len] == old_messages:
        added_messages = new_messages[old_len:]
        placeholders = [create_placeholder(msg, i + old_len) for i, msg in enumerate(added_messages)]
        return placeholders, []

    # Case where last message might have been removed (e.g., tool command)
    if new_len == old_len - 1 and new_messages == old_messages[:-1]:
        return [], [old_len - 1] # Indicate removal of the last index of old_messages

    # If it's neither simple append nor last item removal, log all new messages as added
    # This is a fallback and might not perfectly capture complex modifications.
    # A more sophisticated diff algorithm could be used here if needed.
    # See GEMINI.md: Delta Calculation Complexity
    llt_logger.log_warning("Messages delta calculation fallback used.", {"old_len": old_len, "new_len": new_len})
    placeholders = [create_placeholder(msg, i + old_len) for i, msg in enumerate(new_messages[old_len:])]
    return placeholders, [] # Best guess: treat as append

def get_tool_source(cmd_map: CommandMap, cmd_name: str) -> Optional[str]:
    """Attempt to find the source module of a command."""
    if cmd_name in cmd_map:
        try:
            return cmd_map[cmd_name].__module__
        except AttributeError:
            return "unknown_source"
    return None

def get_resource_references(command: ScheduledCommand, old_state: AppState, new_state: AppState) -> Dict[str, Any]:
    """Determine relevant resource references based on the command."""
    references = {}
    cmd_name = command.name
    cmd_value = command.value

    # File/Path related commands
    if cmd_name in ["load", "write", "attach", "file", "include_project_context"]:
        if cmd_value:
            references["referenced_path"] = cmd_value
        elif cmd_name == "load" and new_state.context.get("load") != old_state.context.get("load"):
             # Handle cases where load might update context directly
             references["referenced_path"] = new_state.context.get("load")
        # Future: Add file hash: references["path_hash_sha256"] = calculate_file_hash(path)

    # Model / Generation related commands
    elif cmd_name in ["complete", "gen", "llm", "generate"]: # Assuming aliases
        references["model_used"] = old_state.context.get("model")
        references["temperature_used"] = old_state.context.get("temperature")
        references["max_tokens_setting"] = old_state.context.get("max_tokens")
        references["top_p_setting"] = old_state.context.get("top_p")
    elif cmd_name == "change_model":
        if cmd_value:
            references["model_changed_to"] = cmd_value

    # External Interaction Commands
    elif cmd_name == "url_fetch":
        if cmd_value:
            references["fetched_url"] = cmd_value
    elif cmd_name == "email":
        if cmd_value:
            references["email_details"] = cmd_value # Could be recipient, subject etc.
    elif cmd_name in ["git_ls_files", "git_status", "git_diff"]:
        references["git_operation"] = cmd_name
        references["project_dir"] = old_state.context.get("project_dir") # Assuming project_dir context exists

    # Execution / Application Commands
    elif cmd_name in ["execute", "apply"]:
        references["action_type"] = cmd_name
        references["target_index"] = command.index
        # Future: Could add language/code snippet hash if feasible

    # Context Modification
    elif cmd_name == "modify_args":
        references["context_modifier"] = cmd_name
        # Changes are primarily captured in context_delta

    # Add others based on llt_tools.json as needed (e.g., screenshot, whisper)

    return references

def log_command_execution(
    old_state: AppState,
    new_state: AppState,
    command: ScheduledCommand,
    cmd_map: CommandMap,
) -> Optional[str]:
    """Logs the execution of a command and the resulting state change."""
    session_id = old_state.context.get("session_id")
    cmd_dir = old_state.context.get("cmd_dir")
    parent_log_id = old_state.context.get("last_log_id") # Get parent ID from old state

    if not session_id or not cmd_dir:
        llt_logger.log_warning("Cannot log command: session_id or cmd_dir missing from context.")
        return parent_log_id if isinstance(parent_log_id, str) else None # Return the old parent ID (str or None)

    log_file_path = os.path.join(cmd_dir, f"session_{session_id}.log.jsonl")
    log_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    context_delta = calculate_context_delta(old_state.context, new_state.context)
    messages_added, messages_removed_indices = calculate_messages_delta(old_state.messages, new_state.messages)

    # Get resource references based on the command
    resource_references = get_resource_references(command, old_state, new_state)

    log_entry = {
        "log_id": log_id,
        "parent_id": parent_log_id,
        "timestamp": timestamp,
        "command": {
            "name": command.name,
            "value": command.value,
            "index": command.index,
            "tool_source": get_tool_source(cmd_map, command.name)
        },
        "state_delta": {
            "context_changed": context_delta,
            "messages_added": messages_added,
            "messages_removed_indices": messages_removed_indices # Placeholder for future use
        },
        "resource_references": resource_references,
        "output_summary": { # Basic summary, could be enhanced by tools returning status
             "status": "success", # Assume success if we got here
             "new_message_count": len(messages_added)
         }
    }

    try:
        with open(log_file_path, 'a') as f:
            json.dump(log_entry, f)
            f.write('\n')
        return log_id # Return the new log_id to be stored
    except IOError as e:
        llt_logger.log_error(f"Failed to write command log: {e}", {"log_file": log_file_path})
        print(f"{Colors.RED}Error logging command to {log_file_path}: {e}{Colors.RESET}")
        return parent_log_id if isinstance(parent_log_id, str) else None # Return the old ID on failure

def create_parser() -> argparse.ArgumentParser:
    """
    Create argument parser with all settings.
    """
    parser = argparse.ArgumentParser(
        description="llt, the little language terminal",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Model configuration
    model_group = parser.add_argument_group('Model Configuration')
    model_group.add_argument('--role', '-r', type=str, help="Specify role (user, system, etc.)", default="user")
    model_group.add_argument('--model', '-m', type=str, help="Which LLM model to use", default="deepseek-chat")
    model_group.add_argument('--temperature', '-t', type=float, help="Sampling temperature", default=0.9)
    model_group.add_argument('--max_tokens', type=int, help="Max tokens to generate", default=0)
    model_group.add_argument('--logprobs', type=int, help="Include logprobs in completion", default=0)
    model_group.add_argument('--top_p', type=float, help="Top-p sampling", default=1.0)
    
    # Directory configuration
    dir_group = parser.add_argument_group('Directory Configuration')
    dir_group.add_argument('--cmd_dir', type=str, 
                          default=os.path.join(os.getenv('LLT_PATH', '~/.llt'), 'cmd'),
                          help="Command directory path")
    dir_group.add_argument('--exec_dir', type=str,
                          default=os.path.join(os.getenv('LLT_PATH', '~/.llt'), 'exec'),
                          help="Execution directory path")
    dir_group.add_argument('--ll_dir', type=str,
                          default=os.path.join(os.getenv('LLT_PATH', '~/.llt'), 'll'),
                          help="Language files directory path")
    
    # Mode settings
    mode_group = parser.add_argument_group('Operation Mode')
    mode_group.add_argument('--auto', action='store_true', help="Enable auto mode")
    mode_group.add_argument('--non_interactive', '-n', action='store_true', 
                           help="Run in non-interactive mode")
    mode_group.add_argument('--use_tool', action='store_true',
                           help="Run in use_tool mode (uses LLM to execute tools)")
    
    return parser

def initialize_environment(dirs: List[str]) -> None:
    """
    Create necessary directories and validate environment.
    """
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)

def create_greeting(context: Context) -> str:
    """
    Create user greeting message.
    """
    return (
        f"Hello {os.getenv('USER', 'User')}! "
        f"ll {context.get('load', 'default')} is loaded "
        f"with model {context['model']} at temperature {context['temperature']}. "
        f"Type 'help' for commands."
    )

def process_command(
    cmd_map: CommandMap,
    cmd: ScheduledCommand,
    state: AppState
) -> AppState:
    """
    Process a single command and return new state.
    Maintains compatibility with existing tools by managing mutable state copies.
    """
    if cmd.name in cmd_map:
        if not state.context.get('non_interactive'):
            print(f"\nllt> {cmd.name}")
        try:
            # Create mutable copies for tool compatibility
            messages, context = state.to_tool_args()
            
            # If the command has a specific value, temporarily override the context
            original_value = None
            
            if cmd.value is not None and cmd.name in context:
                # Save original value
                original_value = context.get(cmd.name)
                # Set the specific value for this command execution
                context[cmd.name] = cmd.value
            
            # Execute tool with mutable structures
            result = cmd_map[cmd.name](messages, context, cmd.index)
            
            # Handle new return signature (messages or tuple of messages and commands)
            if isinstance(result, tuple) and len(result) == 2:
                new_messages, commands = result
                command_queue = state.command_queue.copy()
                for cmd in commands:
                    command_queue.append(cmd)
            else:
                new_messages = result
                command_queue = state.command_queue.copy()
            
            # Handle LLT tool messages for backward compatibility
            """ if new_messages and isinstance(new_messages[-1], dict) and new_messages[-1].get("role") == "tool":
                tool_content = new_messages[-1].get("content", "")
                if not state.context.get("non_interactive"):
                    if input("Add this LLT command to queue? (y/N): ").lower() == 'y':
                        cmd_name, value, index = parse_interactive_input(tool_content)
                        command_queue.append(ScheduledCommand(cmd_name, index if index is not None else -1, value=value))
                        new_messages = new_messages[:-1]
                else:
                    cmd_name, value, index = parse_interactive_input(tool_content)
                    command_queue.append(ScheduledCommand(cmd_name, index if index is not None else -1, value=value))
                    new_messages = new_messages[:-1] """
            
            # Restore original value if needed
            if original_value is not None:
                context[cmd.name] = original_value
            
            # Create new state with updates from tool
            # Explicit typing to satisfy the linter
            messages_list: Messages = list(new_messages)
            context_dict: Context = dict(context)
            cmd_queue: deque[ScheduledCommand] = command_queue
            
            intermediate_state = AppState(
                messages=messages_list,
                context=context_dict,
                command_queue=cmd_queue
            )

            # --- Log Command Execution ---
            last_log_id = log_command_execution(state, intermediate_state, cmd, cmd_map)
            # this is where we can statefully log the command execution as a function of current state
            # Update context with the latest log ID for the next step's parent_id
            final_context = dict(intermediate_state.context)
            final_context["last_log_id"] = last_log_id
            return intermediate_state.with_context(final_context)
            
        except Exception as e:
            llt_logger.log_error(str(e), {"traceback": traceback.format_exc()})
            print(f"{Colors.RED}Command failed: {e}{Colors.RESET}")
            return state
    else:
        # Handle as user message
        full_content = cmd.name
        if cmd.value is not None:
             # Combine name and value if value exists, assuming value holds the rest of the input
             full_content += f" {cmd.value}"
        new_messages = [*state.messages, {
            'role': state.context['role'],
            'content': full_content # Use combined content
        }]
        # --- Log User Input as a Command ---
        # Treat user input as a pseudo-command for logging continuity
        user_input_command = ScheduledCommand(name="<user_input>", index=-1, value=full_content)
        intermediate_state = state.with_messages(new_messages)

        last_log_id = log_command_execution(state, intermediate_state, user_input_command, cmd_map)
        # Update context with the latest log ID
        final_context = dict(intermediate_state.context)
        final_context["last_log_id"] = last_log_id
        return intermediate_state.with_context(final_context)

def get_next_command(
    state: AppState,
    cmd_map: CommandMap
) -> Optional[ScheduledCommand]:
    """
    Determine the next command to execute.
    Handles command queue, non-interactive mode, and transitions
    from redirected stdin to interactive TTY input.
    Adds logging for command retrieval steps.
    """
    if state.command_queue:
        llt_logger.log_info("Dequeuing command from command_queue.", {
            "queue_length": len(state.command_queue),
            "queue": [str(cmd) for cmd in state.command_queue]
        })
        popped_command = state.command_queue.popleft()
        print(f"\nDequeued command: {popped_command.name}")
        print(cmd_map[popped_command.name])
        return popped_command
    elif state.context.get('non_interactive'):
        llt_logger.log_info("Non-interactive mode: no more commands to process.")
        return None

    llt_logger.log_info("Awaiting interactive user input for next command.", {
        "available_commands": list(cmd_map.keys())
    })
    cmd_name, value, index = llt_interactive_input(list(cmd_map.keys()))
    internal_index = index if index is not None else -1
    llt_logger.log_info("Received interactive command.", {
        "cmd_name": cmd_name,
        "value": value,
        "index": internal_index
    })
    return ScheduledCommand(cmd_name, internal_index, value=value)

def run_llt(initial_state: AppState, cmd_map: CommandMap) -> None:
    """
    Main llt loop using immutable state transitions.
    """
    def process_interrupt(state: AppState) -> AppState:
        """Handle keyboard interrupts."""
        if not state.context.get('non_interactive'):
            print("\nReceived keyboard interrupt")
        try:
            time.sleep(0.5)  # Allow for double-interrupt check
        except KeyboardInterrupt:
            if not state.context.get('non_interactive'):
                print("\nDouble interrupt - exiting...")
            sys.exit(1) # Exit with error code on interrupt

        if state.context.get('auto'):
            new_context = dict(state.context)
            new_context['auto'] = False
            if not state.context.get('non_interactive'):
                Colors.print_colored("Auto mode disabled", Colors.YELLOW)
            return state.with_context(new_context)
        return state

    def main_loop(state: AppState) -> Optional[AppState]:
        """Single iteration of the main loop."""
        try:
            cmd = get_next_command(state, cmd_map)
            if cmd is None:
                if not state.context.get('non_interactive'):
                    print("Non-interactive mode complete, exiting...")
                # Otherwise (e.g. stdin redirection ended), exit silently
                return None
            return process_command(cmd_map, cmd, state)

        except KeyboardInterrupt:
            return process_interrupt(state)
        except Exception as e:
            llt_logger.log_error(str(e), {"traceback": traceback.format_exc()})
            print(f"{Colors.RED}Error: {e}\n{traceback.format_exc()}{Colors.RESET}")
            return state

    def loop(state: AppState) -> None:
        """Tail-recursive main loop."""
        new_state = main_loop(state)
        if new_state is not None:
            loop(new_state)
    
    # Start the loop
    loop(initial_state)

def main() -> None:
    """Application entry point."""
    # Load tools
    tool_dir = os.path.join(os.getenv("LLT_DIR", ""), "tools")
    load_tools(tool_dir)
    
    # Initialize parser and arguments
    parser = create_parser()
    add_tool_arguments(parser)
    args = parser.parse_args()
    
    # Initialize directories
    initialize_environment([args.ll_dir, args.exec_dir, args.cmd_dir])
    
    # Convert flat namespace to nested context
    context_dict = pack_namespaced_args(args)
    
    # Add session-specific context
    context_dict["session_id"] = str(uuid.uuid4())
    context_dict["last_log_id"] = None # Initialize parent ID for the first log entry
    
    # If use_tool flag is set, make sure auto is enabled
    if args.use_tool:
        context_dict["auto"] = True

    # Create initial state
    initial_state = AppState(
        messages=[], # Start with empty messages
        context=context_dict,
        command_queue=schedule_startup_commands(args)
    )
    
    # Initialize command map
    cmd_map = init_cmd_map()
    
    # Display greeting only in interactive mode
    if not args.non_interactive:
        Colors.print_header()
        print(create_greeting(initial_state.context))
    
        
    # Run application in REPL mode (use_tool functionality controlled by auto flag)
    run_llt(initial_state, cmd_map)

if __name__ == "__main__":
    main()
