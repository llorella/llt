#!/usr/bin/env python3
"""
main.py - llt, the little language terminal

A functional implementation of the llt that processes commands and manages 
conversations with language models. This version follows functional programming principles 
and careful parameter ordering inspired by Haskell's design patterns, while maintaining
compatibility with the existing plugin system.
"""

import os
import sys
import time
import argparse
import traceback
from typing import List, Dict, Callable, Optional, TypeVar, Any, Tuple
from dataclasses import dataclass
from functools import reduce
from collections import deque

from logger import llt_logger
from utils import Colors, llt_input, parse_cmd_string
from plugins import (
    load_plugins,
    add_plugin_arguments,
    init_cmd_map,
    schedule_startup_commands,
    ScheduledCommand
)

# Type aliases for improved readability and type safety
Message = Dict[str, Any]
Messages = List[Message]
Context = Dict[str, Any]
CommandMap = Dict[str, Callable]
T = TypeVar('T')
R = TypeVar('R')

@dataclass(frozen=True)
class AppState:
    """
    Immutable application state container with plugin compatibility helpers.
    
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
        return AppState(new_messages, self.context, self.command_queue)

    def with_context(self, new_context: Context) -> 'AppState':
        """Create new state with updated context."""
        return AppState(self.messages, new_context, self.command_queue)

    def with_queue(self, new_queue: deque[ScheduledCommand]) -> 'AppState':
        """Create new state with updated command queue."""
        return AppState(self.messages, self.context, new_queue)

    def to_plugin_args(self) -> Tuple[Messages, Context]:
        """Convert state to plugin-compatible arguments."""
        return self.messages.copy(), dict(self.context)

    @classmethod
    def from_plugin_result(
        cls,
        messages: Messages,
        context: Context,
        command_queue: deque[ScheduledCommand]
    ) -> 'AppState':
        """Create new state from plugin execution results."""
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
                print(f"Error: {e}\n{traceback.format_exc()}")
                return default
        return wrapper

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
    model_group.add_argument('--max_tokens', type=int, help="Max tokens to generate", default=8192)
    model_group.add_argument('--logprobs', type=int, help="Include logprobs in completion", default=0)
    model_group.add_argument('--top_p', type=float, help="Top-p sampling", default=1.0)
    
    # Directory configuration
    dir_group = parser.add_argument_group('Directory Configuration')
    dir_group.add_argument('--cmd_dir', type=str, 
                          default=os.path.join(os.getenv('LLT_PATH', ''), 'cmd'),
                          help="Command directory path")
    dir_group.add_argument('--exec_dir', type=str,
                          default=os.path.join(os.getenv('LLT_PATH', ''), 'exec'),
                          help="Execution directory path")
    dir_group.add_argument('--ll_dir', type=str,
                          default=os.path.join(os.getenv('LLT_PATH', ''), 'll/'),
                          help="Language files directory path")
    
    # Mode settings
    mode_group = parser.add_argument_group('Operation Mode')
    mode_group.add_argument('--auto', action='store_true', help="Enable auto mode")
    mode_group.add_argument('--non_interactive', '-n', action='store_true', 
                           help="Run in non-interactive mode")
    
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
    Maintains compatibility with existing plugins by managing mutable state copies.
    """
    if cmd.name in cmd_map:
        print(f"\nExecuting command: {cmd.name}")
        try:
            # Create mutable copies for plugin compatibility
            messages, context = state.to_plugin_args()
            
            # Execute plugin with mutable structures
            new_messages = cmd_map[cmd.name](messages, context, cmd.index)
            
            # Handle LLT role messages
            command_queue = state.command_queue.copy()
            if new_messages and new_messages[-1]["role"] == "llt":
                if not state.context.get("non_interactive"):
                    if input("Add this LLT command to queue? (y/N): ").lower() == 'y':
                        cmd_name, index = parse_cmd_string(new_messages[-1]["content"])
                        command_queue.append(ScheduledCommand(cmd_name, index))
                        new_messages = new_messages[:-1]
                else:
                    command_queue.append(
                        ScheduledCommand(new_messages[-1]["content"], cmd.index)
                    )
                    new_messages = new_messages[:-1]
            
            # Create new state with updates from plugin
            return AppState.from_plugin_result(new_messages, context, command_queue)
            
        except Exception as e:
            llt_logger.log_error(str(e), {"traceback": traceback.format_exc()})
            print(f"Command failed: {e}")
            return state
    else:
        # Handle as user message
        new_messages = [*state.messages, {
            'role': state.context['role'],
            'content': cmd.name
        }]
        return state.with_messages(new_messages)

def get_next_command(
    state: AppState,
    cmd_map: CommandMap
) -> Optional[ScheduledCommand]:
    """
    Determine the next command to execute.
    """
    if state.command_queue:
        return state.command_queue.popleft()
    elif state.context.get('non_interactive'):
        return None
    else:
        print("\nWaiting for command input...")
        cmd_name, index = llt_input(list(cmd_map.keys()))
        print(f"Received command: {cmd_name} (index: {index})")
        return ScheduledCommand(cmd_name, index)

def run_llt(initial_state: AppState, cmd_map: CommandMap) -> None:
    """
    Main application loop using immutable state transitions.
    """
    def process_interrupt(state: AppState) -> AppState:
        """Handle keyboard interrupts."""
        print("\nReceived keyboard interrupt")
        try:
            time.sleep(0.5)  # Allow for double-interrupt check
        except KeyboardInterrupt:
            print("\nDouble interrupt - exiting...")
            sys.exit(0)
            
        if state.context.get('auto'):
            new_context = dict(state.context)
            new_context['auto'] = False
            Colors.print_colored("Auto mode disabled", Colors.YELLOW)
            return state.with_context(new_context)
        return state

    def main_loop(state: AppState) -> Optional[AppState]:
        """Single iteration of the main loop."""
        try:
            cmd = get_next_command(state, cmd_map)
            if cmd is None:
                print("Non-interactive mode complete, exiting...")
                return None
            return process_command(cmd_map, cmd, state)
            
        except KeyboardInterrupt:
            return process_interrupt(state)
        except Exception as e:
            llt_logger.log_error(str(e), {"traceback": traceback.format_exc()})
            print(f"Error: {e}\n{traceback.format_exc()}")
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
    # Load plugins
    plugin_dir = os.path.join(os.getenv("LLT_DIR", ""), "plugins")
    load_plugins(plugin_dir)
    
    # Initialize parser and arguments
    parser = create_parser()
    add_plugin_arguments(parser)
    args = parser.parse_args()
    
    # Initialize directories
    initialize_environment([args.ll_dir, args.exec_dir, args.cmd_dir])
    
    # Create initial state
    initial_state = AppState(
        messages=[],
        context=vars(args),
        command_queue=schedule_startup_commands(args)
    )
    
    # Initialize command map
    cmd_map = init_cmd_map()
    
    # Display greeting
    Colors.print_header()
    print(create_greeting(initial_state.context))
    
    # Run application
    run_llt(initial_state, cmd_map)

if __name__ == "__main__":
    main()