# About
```shell
llt -l llt/README_demo.ll -f LLT_ABOUT_SNIPPET.txt --view
```

llt is a UNIX command for applying a set of transformations on an ll file, a language log consisting of messages that have lead to the current state. The current state is represented by an llt created dictionary that corresponds to the current ll name. llt, via a flexible plugin ecosystem, can apply many successive transformations to the current state (virtual filesystem), recorded in the ll file, and reach some user decided threshold of completion of task. Getting from a starting prompt to an end goal is a lot of work, and requires lots of editing, test and executing code, prompting, web searching, and more. Thankfully, llt has plugins for every one of those things and more, which can exposed either at runtime in an interactive shell or non-interactively at command time with specified plugin directives.

```shell
llt -l llt/SETUP.ll -f SETUP.md -p "Return a markdown list that outlines setting up a github repo at https://github.com/llorella/llt.git by running git clone, installing required dependencies, and setting LLT_PATH environment variable."
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/llorella/llt.git
   ```

2. Navigate to the project directory:
   ```
   cd llt
   ```

3. Set up a virtual environment (optional, will be replaced with a better method):
   ```
   python3 -m venv .env
   source venv/bin/activate
   ```

4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Set the `LLT_PATH` environment variable for the llt data directory.
   ```
   export LLT_PATH=$HOME/.llt
   ```

### Usage

Run the `main.py` script to start llt.
```
python main.py [options]
```

Optional flags provide additional customization:

```
usage: llt [-h] [--ll LL_FILE] [--file FILE_INCLUDE] [--image_path IMAGE_PATH] [--prompt PROMPT] [--role ROLE]
               [--model MODEL] [--temperature TEMPERATURE] [--max_tokens MAX_TOKENS] [--logprobs LOGPROBS] [--top_p TOP_P]
               [--cmd_dir CMD_DIR] [--exec_dir EXEC_DIR] [--ll_dir LL_DIR]
               [--non_interactive] [--detach] [--export]
               [--exec] [--view] [--email] [--web]

llt, little language tool and terminal

options:
  --help, -h           show this help message and exit
  --ll, -l LL_FILE
                        Language log file. List of natural language messages stored as JSON.
  --file, -f FILE_INCLUDE
                        Read content from a file and include it in the ll.
  --image_path IMAGE_PATH
  --prompt PROMPT, -p PROMPT
                        Prompt string.
  --role ROLE, -r ROLE  Specify role.
 --model, -m MODEL
 --temperature, -t TEMPERATURE
                        Specify temperature.
  --max_tokens MAX_TOKENS
                        Maximum number of tokens to generate.
  --logprobs LOGPROBS   Include log probabilities in the output, up to the specified number of tokens.
  --top_p TOP_P         Sample from top P tokens.
  --cmd_dir CMD_DIR
  --exec_dir EXEC_DIR
  --ll_dir LL_DIR
  --non_interactive, -n
                        Run in non-interactive mode.
  --detach              Pop last message from given ll.
  --export              Export messages to a file.
  --exec                Execute the last message
  --view                Print the last message.
  --email               Send an email with the last message.
  --web                 Fetch a web page and filter tags between paragraphs and code blocks.
```

### Video Example
[llt_exa_search.webm](https://github.com/llorella/llt/assets/110218399/33695be6-bb02-4bfe-a87e-f405df03e4cb)

### Commands and Examples:

Type `help` within the application to see available commands. Some common commands include:

- `load`: Load a message history.
  ```
  llt> load
  Filename: previous_conversation.ll
  ```
- `write`: Write the current conversation to the history file.
  ```
  llt> write
  Context file: previous_new_conversation.ll
  ```
- `view`: View the messages in the current session.
  ```
  llt> view
  User: Hello, how are you?
  Assistant: I'm doing well, thank you for asking! How can I assist you today?
  ```
- `new`: Add a new message to the conversation.
  ```
  llt> new
  Content: Can you help me write a Python function to calculate the factorial of a number?
  ```
- `complete`: Prompt the model to generate a completion.
  ```
  llt> complete
  Assistant: Certainly! Here's a Python function that calculates the factorial of a number using recursion:

  ## factorial.py
  ```python
  def factorial(n):
      if n == 0:
          return 1
      else:
          return n * factorial(n - 1)
  ```

- `edit`: Edit and manage code blocks from the last message.
  ```
  llt> edit
  Exec directory: /path/to/exec/dir
  File: factorial.py
  Type: python
  Code:
  def factorial(n):
      if n == 0:
          return 1
      else:
          return n * factorial(n - 1)

  Write to file (w), skip (s), or edit (e)? w
  /path/to/exec/dir/factorial.py changed.
  ```
- `file`: Include a file's content into the message.
  ```
  llt> file
  File path: /path/to/code_snippet.py
  ```
- `image`: Attach an encoded image to the message.
  ```
  llt> image
  Image path: /path/to/image.png
  Content: Here's the diagram I mentioned earlier.
  ```
- `quit`: Exit the program.
  ```
  llt> quit
  Exiting...
  ```

## Development and Contributions

Contributions to llt are welcome! Please feel free to fork the repository, make changes, and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
</README>

<instruction>
Please massively improve the readme for your llt project. I liked the original blob I wrote, as it captures the essence of llt, but the project has involved massively since then. Please make it beautiful, concise, elegant, and informative.
</instruction>
[/User]
Message 2 of 3
--------------------------------------------------
[Assistant]
I'll help create a more polished and comprehensive README that better reflects llt's current state and capabilities. Here's my proposed revision:

```markdown
# llt - Little Language Terminal

llt is a modular command-line interface for interacting with language models through a series of transformative operations on message logs. It provides a flexible plugin ecosystem for tasks like code editing, file manipulation, image handling, and model interactions.

## Core Concepts

- **Language Logs (ll)**: JSON files containing conversation history and state
- **Plugin System**: Extensible architecture for adding new functionality
- **Message Transformations**: Each command modifies the message state in well-defined ways
- **Interactive & Non-interactive Modes**: Use as a shell or in scripts/automation

## Key Features

- 🔄 **Stateful Sessions**: Preserve and manipulate conversation context
- 🔌 **Plugin Architecture**: Easy to extend with new capabilities
- 📝 **Code Management**: Edit, execute, and manage code blocks
- 🖼️  **Image Support**: Handle image-based prompts and responses
- 🔧 **Model Configuration**: Fine-tune model parameters and behavior
- 📋 **Clipboard Integration**: Seamless copy/paste operations
- 🎙️  **Audio Input**: Voice-to-text via Whisper API
- 📄 **File Operations**: Direct file inclusion and manipulation

## Installation

```bash
# Clone the repository
git clone https://github.com/llorella/llt.git
cd llt

# Set up environment
export LLT_PATH=$HOME/.llt
pip install -r requirements.txt
```

## Quick Start

```bash
# Start interactive shell
python main.py

# Load existing conversation
python main.py --load my_conversation.ll

# Execute with specific model and temperature
python main.py --model gpt-4-latest --temperature 0.7

# Non-interactive mode with file input
python main.py -n --file input.py --prompt "Explain this code"
```

## Plugin Commands

| Command | Description | Example |
|---------|-------------|---------|
| `load` | Load message history | `load conversation.ll` |
| `write` | Save current state | `write output.ll` |
| `file` | Include file content | `file main.py` |
| `edit` | Manage code blocks | `edit` |
| `complete` | Generate completion | `complete` |
| `execute` | Run code blocks | `execute` |
| `whisper` | Voice input | `whisper` |
| `view` | Display messages | `view` |

## Configuration

llt uses a YAML configuration file for model settings and API credentials:

```yaml
providers:
  openai:
    api_key: OPENAI_API_KEY
    models:
      gpt-4: [latest]
  anthropic:
    api_key: ANTHROPIC_API_KEY
    models:
      claude: [2, 3]
```

## Directory Structure

```
$LLT_PATH/
├── ll/         # Language logs
├── cmd/        # Command history
├── exec/       # Execution workspace
└── config.yaml # Configuration
```

## Plugin Development

Create new plugins by decorating functions with `@plugin`:

```python
from plugins import plugin

@plugin
def my_command(messages: List[Dict], args: Dict) -> List[Dict]:
    # Transform messages
    return messages
```

## Use Cases

- **Code Development**: Interactive coding sessions with AI assistance
- **Documentation**: Generate and maintain documentation
- **Data Analysis**: Process and analyze data with AI guidance
- **Learning**: Educational interactions with language models
- **Content Creation**: Generate and refine content

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Submit a pull request

## License

MIT License - See [LICENSE](LICENSE) for details

---

For more examples and detailed documentation, visit our [Wiki](https://github.com/llorella/llt/wiki).