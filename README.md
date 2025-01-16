# llt (Little Language Terminal)

A powerful command-line interface and programmatic tool for managing AI conversations through transformative operations on message logs. llt provides a flexible plugin ecosystem for tasks like code editing, file manipulation, image handling, and model interactions.

## Core Features

- 🔄 **Stateful Conversations**: Preserve and transform conversation context through language logs
- 🔌 **Plugin System**: Extensible architecture for conversation transformations
- 🤖 **Multi-Model Support**: Works with various LLM providers (Claude, GPT-4, DeepSeek, etc.)
- 🛠️ **Tool Integration**: Execute code, manage files, and integrate with external tools
- 📦 **Programmatic API**: Use as a CLI tool or integrate into applications

## Installation

1. Clone the repository:
```bash
git clone https://github.com/llorella/llt.git
cd llt
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment:
```bash
# Set data directory
export LLT_PATH=$HOME/.llt

# Create config file
mkdir -p $LLT_PATH
cp config.example.yaml $LLT_PATH/config.yaml

# Add your API keys
vim $LLT_PATH/config.yaml
```

## Usage

### Basic Commands

```bash
# Start a new conversation
llt --model claude-3-sonnet --prompt "Hello, world!"

# Load and continue a conversation
llt --load my_conversation.ll --complete

# Process a file with a specific model
llt --model deepseek-chat --file code.py --complete

# Execute code blocks from conversation
llt --load code_session.ll --execute python

# Extract and transform content
llt --load chat.ll --extract --json
```

### Interactive Commands

Within the llt shell:

- `complete` (or `c`): Generate model completion
- `edit` (or `e`): Edit code blocks in files
- `execute` (or `x`): Run code blocks
- `view` (or `v`): Display conversation
- `load` (or `l`): Load conversation file
- `write` (or `w`): Save conversation
- `help` (or `h`): Show available commands

### Configuration

Create a `config.yaml` file in your `$LLT_PATH`:

```yaml
providers:
  anthropic:
    api_key: ANTHROPIC_API_KEY
    models:
      claude: [3-sonnet, 3-opus]
  deepseek:
    api_key: DEEPSEEK_API_KEY
    models:
      chat: [latest]
```

### Programmatic Usage

```typescript
// Example: Managing conversations programmatically
async function llResponse(sessionId: string, ll_name: string): Promise<string> {
    // Write conversation to temp file
    const messages = getConversationMessages(sessionId);
    const tempFile = writeTempFile(messages);

    // Different conversation mediators
    if (ll_name === "conversation-manager") {
        return await run_command([
            "llt", "--model", "deepseek-chat",
            "--load", "coquiz/conversation-manager-1",
            "--attach", tempFile,
            "--complete", "-n"
        ]);
    }

    // Tool usage example
    if (ll_name === "code-executor") {
        return await run_command([
            "llt", "--model", "claude-sonnet-3-5",
            "--load", "code-executor",
            "--execute", "bash",
            "--xml_wrap", "exampleOutput",
            "--fold", "--complete", "-n"
        ]);
    }
}
```

### Plugin Development

Create custom transformations by decorating functions with `@llt`:

```python
from plugins import llt
from typing import List, Dict

@llt
def my_transform(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Custom transformation
    Type: bool
    Default: false
    flag: my_transform
    """
    # Transform messages
    return messages
```

## Directory Structure

```
$LLT_PATH/
├── ll/           # Language logs (conversation files)
├── cmd/          # Command history
├── exec/         # Execution workspace
├── tools.json    # Tool definitions
└── config.yaml   # Configuration
```

## Contributing

Contributions are welcome! Please check out our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and contribute to the project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.