# LLT (Little Language Terminal) CLI Tool Specification

## 1. Overview
LLT is a functional, LLM-driven command‐line interface for composing, inspecting, and manipulating conversational transcripts. It follows immutable state transitions and supports a rich set of built-in tools, plugins, and streaming completions with tool-use support.

## 2. Architecture

- **Entry Point**: `main.py`  
- **Core Concepts**  
  - Immutable `AppState` (messages, context, command_queue)  
  - Stateless command handlers decorated with `@llt()`  
  - Tool registry loaded from `tools.json` and `tool_registry.json`  
  - Functional composition helpers (`FunctionComposition`)  

## 3. Modules & Responsibilities

| Module                       | Responsibility                                    |
|------------------------------|---------------------------------------------------|
| `main.py`                    | CLI parsing, environment setup, REPL loop         |
| `message.py`                 | Built-in message commands (`load`, `save`, etc.)  |
| `tools/completion.py`        | LLM integration, streaming events, tool‐use logic |
| `utils.py`                   | I/O, diff, parsing, input handling, file utilities |
| `logger.py`                  | Structured JSONL command logging                  |
| `tools/__init__.py`          | Plugin loader, argument injection, command map    |

## 4. CLI Interface

### 4.1. Parser Definition (`create_parser`)
- **Model Configuration**  
  - `--role, -r` (string, default=`user`)  
  - `--model, -m` (string, default=`deepseek-chat`)  
  - `--temperature, -t` (float, default=`0.9`)  
  - `--max_tokens` (int, default=`0`)  
  - `--logprobs` (int, default=`0`)  
  - `--top_p` (float, default=`1.0`)  

- **Directory Configuration**  
  - `--cmd_dir` (path, default=`$LLT_PATH/cmd`)  
  - `--exec_dir` (path, default=`$LLT_PATH/exec`)  
  - `--ll_dir` (path, default=`$LLT_PATH/ll`)  

- **Operation Mode**  
  - `--auto` (flag)  
  - `--non_interactive, -n` (flag)  
  - `--use_tool` (flag)  

### 4.2. Dynamic Tool Arguments
- Loaded via `add_tool_arguments(parser)`
- Flags derived from `tools.json` and MCP servers (if connected)
- Registered functions in `tools/` become subcommands with:
  - `flag` name  
  - `type` (bool, string, dict)  
  - `short` alias  

## 5. Built-in Message Commands (`message.py`)
Each command signature: `(messages, dict, index) -> messages`

| Command      | Flag           | Short | Needs Index | Description                                 |
|--------------|----------------|-------|-------------|---------------------------------------------|
| `load`       | `--load`       | `-ll` | No          | Load messages from `.ll` file               |
| `save`       | `--save`       | `-s`  | No          | Save messages to `.ll` file                 |
| `prompt`     | `--prompt`     | `-p`  | No          | Append user prompt as a new message         |
| `remove`     | `--remove`     |       | Yes         | Remove message at index                     |
| `attach`     | `--attach`     |       | Yes         | Insert messages from file at index          |
| `detach`     | `--detach`     |       | Yes         | Replace conversation with single message    |
| `fold`       | `--fold`       |       | Yes         | Merge contiguous messages of same role      |
| `insert`     | `--insert`     |       | Yes         | Insert empty message at index               |
| `change_role`| `--change_role`|       | Yes         | Change role of a specific message           |
| `role_change`| `--role_change`| `-ro` | No          | Set the current role                        |
| `view`       | `--view`       | `-v`  | Yes         | Pretty‐print one or all messages            |
| `cut`        | `--cut`        | `-c`  | Yes         | Extract a slice of messages via range input |

## 6. Functional Core Architecture

### 6.1. Immutable State Transitions
LLT uses a purely functional approach to state management, centered around the immutable `AppState` class. This design offers several benefits:

- **Predictable execution flow** - Each state transition is a pure function that produces a new state
- **Simplified debugging** - The system can log the exact state before and after each transition
- **Thread safety** - Immutable states can be safely passed between threads/coroutines
- **Transactional integrity** - Commands either succeed completely or fail without side effects

```
AppState(messages, context, command_queue)
  ↓
process_command(cmd_map, cmd, state) → new_state
  ↓
log_command_execution(old_state, new_state, command)
  ↓
main_loop(new_state)
```

### 6.2. State Management with AppState

The `AppState` dataclass provides the following core operations:

| Method | Purpose | Implementation |
|--------|---------|----------------|
| `with_messages(new_messages)` | Create state with updated messages | Returns new AppState instance |
| `with_context(new_context)` | Create state with updated context | Returns new AppState instance |
| `with_queue(new_queue)` | Create state with updated command queue | Returns new AppState instance |
| `to_tool_args()` | Convert state to tool-compatible arguments | Returns (messages, context) tuple |
| `from_tool_result(messages, context, queue)` | Create state from tool execution | Returns new AppState instance |

### 6.3. Monadic Operations with FunctionComposition

The `FunctionComposition` class provides Haskell-inspired monadic operations:

```python
# Compose multiple functions (right to left)
compose(*functions) -> Callable

# Monadic bind operation
bind(value, func) -> R

# Wrap function execution with error handling
safe_execute(f, default) -> Callable
```

### 6.4. State Delta Calculation

State transitions are logged by comparing the before and after states:

- `calculate_context_delta(old_context, new_context) -> Dict[str, Any]`
- `calculate_messages_delta(old_messages, new_messages) -> Tuple[List[MessagePlaceholder], List[int]]`

These calculations produce:
- **Added/changed context keys** - Tracks which configuration values changed
- **Message placeholders** - References to message content via SHA256 hashes
- **Removed indices** - Which messages were deleted

## 7. LLM Integration & Tool Use (`tools/completion.py`)

### 7.1. Tool Execution Lifecycle

The tool execution process follows this workflow:

1. **User Input** → Parse interactive input
2. **Command Parsing** → Create `ScheduledCommand`
3. **Command Processing** → Execute tool or add user message
4. **State Transition** → Generate new application state
5. **Delta Calculation** → Compute changes to messages and context
6. **Logging** → Record command execution and state changes
7. **Repeat** → Return to step 1 with new state

For LLM-generated tools:
1. **LLM Response** → Parse for tool use blocks
2. **Tool Extraction** → Convert to `ScheduledCommand`
3. **Queue Population** → Add commands to execution queue
4. **Auto-continuation** → Schedule follow-up `complete` command
5. **State Update** → Return new messages and command queue

### 7.2. Providers Supported

- **Anthropic** (streamed)  
- **OpenAI** (via `send_request`)  
- **Local placeholder** (`get_local_completion`)  

### 7.3. Streaming Parsing

- Pydantic models for events (`TextEventModel`, `ContentBlockDeltaModel`, etc.)  
- `ToolUseBlock` detection and scheduling (`make_scheduled_from_tool_use`)  
- Automatic re-asking with `complete` command  

### 7.4. OpenAI Function Conversion

- `convert_tools_to_functions` generates function definitions from registry schema  
- `OpenAIFunctionCall` → `ToolUseBlockModel`  

## 8. Tool Registry & Plugins

### 8.1. Tool Discovery and Registration

- Discovered at startup via `load_tools(tool_dir)`  
- Exposed flags via `registry_to_json_schema()`  
- Each plugin function must be decorated `@llt()`  
- Arguments schema is merged into the global parser  

### 8.2. Tool Registration Format

The `@llt()` decorator parses docstrings to register tools:

```python
@llt(needs_index=True)
def example_tool(messages, context, index=-1):
    """
    Description: Example tool
    Type: bool
    Default: false
    flag: example
    short: e
    param: url string "https://default.com"
    param: timeout int 30
    """
    # Tool implementation
    return messages  # or (messages, commands)
```

## 9. Tool Categories and Functions

### 9.1. Content Management Tools

| Tool | Flag | Short | Description |
|------|------|-------|-------------|
| `file_include` | `--file` | `-f` | Include file content (including images) |
| `content` | `--content` | `-edit` | Edit message content in external editor |
| `paste` | `--paste` | `-pa` | Paste clipboard content as new user message |
| `copy` | `--copy` | `-yy` | Copy message content to clipboard |

### 9.2. LLM Integration Tools

| Tool | Flag | Short | Description |
|------|------|-------|-------------|
| `complete` | `--complete` | | Generate a completion from the LLM |
| `encode_images` | | | Encode image URLs into provider format |
| `mod_cxt` | `--mod_cxt` | `-mod` | Modify configuration arguments |
| `model_change` | `--model_change` | `-mo` | Change the model |

### 9.3. Web and Network Tools

| Tool | Flag | Short | Description |
|------|------|-------|-------------|
| `url_fetch` | `--url_fetch` | `-url` | Fetch and process URL content |
| `navigate` | `--navigate` | `-nav` | Navigate, screenshot, and interact with web pages |
| `email` | `--email` | `-mail` | Send email using Gmail API |

### 9.4. Project Context Tools

| Tool | Flag | Short | Description |
|------|------|-------|-------------|
| `include_project_context` | `--include_project_context` | `-ipc` | Include content of project files based on filters |
| `git_ls_files` | | | List files tracked by Git |
| `git_status` | | | Show the Git status of the project directory |
| `git_diff` | | | Show Git diff for the project directory |

### 9.5. Formatting and Display Tools

| Tool | Flag | Short | Description |
|------|------|-------|-------------|
| `xml_wrap` | `--xml_wrap` | `-xml` | Wrap messages in xml tags |
| `parse_xml` | `--parse_xml` | `-parse` | Parse XML content from a message |
| `strip_trailing_newline` | | | Strip trailing newlines from message content |
| `indent` | | | Indent message content by specified amount |
| `code_block` | `--code_block` | `-cb` | Wrap message in a code block with language highlighting |

### 9.6. Media Tools

| Tool | Flag | Short | Description |
|------|------|-------|-------------|
| `screenshot` | `--screenshot` | `-screen` | Capture a screenshot using ffmpeg |
| `execute` | `--execute` | `-ex` | Execute code blocks by language |

## 10. State Management & Logging

### 10.1. Command Logging Schema

```json
{
  "log_id": "uuid-value",
  "parent_id": "parent-uuid-or-null",
  "timestamp": "2023-10-01T12:34:56Z",
  "command": {
    "name": "tool-name",
    "value": "tool-value",
    "index": 3,
    "tool_source": "tools.module_name"
  },
  "state_delta": {
    "context_changed": {
      "temperature": 0.8,
      "removed_key": null
    },
    "messages_added": [
      {
        "type": "message_ref",
        "role": "assistant",
        "content_length": 1024,
        "content_sha256": "hash-value",
        "index_in_new_state": 4
      }
    ],
    "messages_removed_indices": [2]
  },
  "resource_references": {},
  "output_summary": {
    "status": "success",
    "new_message_count": 1
  }
}
```

This logging structure enables:
- **Audit trails** - Complete history of all operations
- **Replay functionality** - Session restoration from logs
- **Debugging** - Precise state at each step
- **Analytics** - Usage patterns and performance metrics

## 11. Utilities (`utils.py`)
- **Input Handling**: Autocomplete, path mode, list selection  
- **File Handling**: Safe read/write, backups  
- **Diff Generation**: Colored, numbered diffs (`DiffHandler`)  
- **Markdown Parsing**: Extract code blocks and metadata  
- **Token Counting**: Tiktoken support  
- **Temporary Files & Clipboard**  

## 12. Testing & Evolution
1. **Unit Tests**  
   - Argument parsing, state delta, message commands, utils  
2. **Integration Tests**  
   - Subprocess CLI runs (`--help`, load/save cycles)  
   - Streaming completion with mocked API  
3. **Future Enhancements**  
   - MCP server integrations  
   - Interactive TUI (curses/Urwid)  
   - Plugin sandboxing & security  
   - Enhanced diff/merge workflows  
   - Watch mode for live transcripts  

## 13. Workflow Patterns for Session Checkpointing

Based on observed real `llt` session logs, common patterns for capturing conversation (`.ll`) and project state include:

1. Loading and updating configuration or transcript:
   ```
   llt --load llt/update_config --file /home/luciano/llt/config.yaml \
       --xml config --prompt "Add max token info for each model." --auto
   ```
   - Use `--load <llfile>` to begin from existing conversation.
   - Use `--xml <tag>` to wrap configuration or instruction blocks.
   - Use `--prompt` to inject user instructions.
   - Use `--auto` for non-interactive execution.

2. Wrapping prompts in XML for structured editing:
   ```
   llt --prompt "Explain project structure" --xml text --complete --auto
   ```
   - `--xml text` wraps the prompt in `<text>` tags.
   - `--complete` schedules the `complete` tool.
   - `--auto` runs without manual confirmations.

3. Saving session state to a new `.ll` file:
   ```
   llt --save checkpoint.ll --auto
   ```
   - `--save <filename>` writes the current conversation to disk.
   - Often combined with `--auto` to avoid interactive prompts.

4. Changing roles and detaching for cleanup:
   ```
   llt --detach --change_role user --save cleaned.ll --auto
   ```
   - `--detach` isolates the last message.
   - `--change_role user` ensures the message is attributed correctly.
   - `--save` persists the reorganized transcript.

5. Embedding project context and code operations:
   ```
   llt --load bookshelf/source --prompt dirtext --xml files --auto \
       --execute --write .
   ```
   - `--xml files` wraps directory listing instructions.
   - `--execute` runs code blocks found in messages.
   - `--write .` persists file changes to the project directory.

6. Folding and cleaning message history:
   ```
   llt --fold --auto
   ```
   - `--fold` merges consecutive messages of the same role into a single entry.
   - Useful for condensing verbose tool logs or chat exchanges.

7. Role adjustment and targeted detachment:
   ```
   llt --detach --change_role tool --prompt screenshot --complete --auto
   ```
   - `--detach` isolates the most recent message for focused operations.
   - `--change_role tool` ensures tool-generated content is correctly attributed.
   - Follow with `--prompt` or `--complete` to schedule further actions.

### 13.1. Advanced Command Chaining Patterns

Beyond basic command sequences, LLT supports powerful command chaining idioms:

1. **Interleaved Tool/LLM Workflow**
   ```
   llt --prompt "Fix this code" --file --xml code --complete \
       --execute --file . --complete --auto
   ```
   This pattern creates a cycle of:
   - User input (prompt)
   - Context addition (file content)
   - LLM response (complete)
   - Tool execution (execute)
   - File modification (file with path)
   - Final LLM verification (complete)

2. **Refactoring Pipeline**
   ```
   llt --git_diff --xml before --prompt "Refactor this code" --complete \
       --execute --git_diff --xml after --complete --auto
   ```
   This creates a before/after comparison with:
   - Initial state capture (git_diff)
   - Refactoring instruction (prompt)
   - Implementation (complete → execute)
   - Result validation (git_diff)
   - Final analysis (complete)

3. **Project Context Bootstrapping**
   ```
   llt --include_project_context glob="*.py" --fold \
       --prompt "Explain this codebase structure" --complete \
       --save project_overview.ll --auto
   ```
   This quickly generates project documentation by:
   - Loading all relevant files (include_project_context)
   - Condensing content (fold)
   - Requesting analysis (prompt → complete)
   - Persisting the knowledge (save)

## 14. Interactive UI Concept: Necklace of Flags

Envision LLT as a dynamic, templated command registry in TypeScript, with a visual "Necklace of Flags" UI. Each plugin becomes a ring (flag) that the user can add, remove, and reorder on a central necklace (command queue).

1. Core Components
   - NecklaceCanvas: SVG/Canvas area displaying rings connected in sequence.
   - FlagRing: UI element representing a single plugin flag (`--flag`). Rings are color-coded by category (I/O, LLM, Git, UI).
   - QueueAnchor: Starting clasp indicating the base `llt` command.

2. User Interactions
   - Drag-and-Drop: Drag a FlagRing from the Palette to the NecklaceCanvas to enqueue a command.
   - Click to Configure: Clicking a ring opens a modal to set parameters (e.g., language, timeout).
   - Remove Ring: Click the red "×" on a ring to dequeue that flag.
   - Reorder: Drag rings along the necklace path to change argument order.

3. Command Serialization
   - As rings are arranged, a TypeScript template builds a serialized CLI string:
     ```ts
     const flags: CommandFlag[] = [ 
       {name: "load", value: "config.ll"},
       {name: "xml", value: "config"},
       {name: "prompt", value: "Add tokens"},
       {name: "auto"}
     ];
     const cliCommand = ["llt", ...flags.map(f => f.serialize())].join(" ");
     ```
   - Real-time preview updates as rings move.

4. Palette & Categories
   - Plugins grouped by type:
     - Conversation: load, save, prompt, view
     - LLM Tools: complete, encode_images, url_fetch
     - Code & Files: execute, edit_content, include_project_context
     - Git Operations: git_ls_files, git_status, git_diff
     - Utilities: xml_wrap, parse_xml, screenshot, copy, paste
   - Search bar filters rings by name or tag.

5. Configuration Modal
   - Dynamic form generated from each plugin's JSON schema (`registry_to_json_schema()`).
   - Validates input types (string, integer, boolean) on change.
   - Saves user preferences for defaults.

6. Persistent Sessions
   - "Save Necklace" writes current flag sequence to `<name>.ll` via `--save`.
   - "Load Necklace" repopulates rings from an existing `.ll` file.

7. Implementation Sketch (TypeScript Interfaces)
   ```ts
   interface CommandFlag {
     name: string;
     args?: Record<string, any>;
     isBoolean?: boolean;
     serialize(): string;
   }
   
   interface NecklaceState {
     flags: CommandFlag[];
     toCLI(): string;
     addFlag(flag: CommandFlag): void;
     removeFlag(index: number): void;
     reorder(from: number, to: number): void;
   }
   ```

*This specification will evolve as implementation details, plugin interfaces, and user requirements mature.*
