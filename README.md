# llt (little language tool)

A powerful command-line interface and programmatic tool for managing AI conversations through transformative operations on message logs. llt provides a flexible plugin ecosystem for tasks like code editing, file manipulation, model interactions, synthetic data generation, and more.


## Installation

1. Clone the repository:
```bash
git clone https://github.com/llorella/llt.git
cd llt
```

2. Install `uv`:
```bash
# On Unix-like systems (Linux, macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex
```

3. Create and activate a virtual environment with `uv`:
```bash
uv venv
source .venv/bin/activate  # On Unix-like systems
# Or on Windows:
# .venv\Scripts\activate
```

4. Install dependencies using `uv`:
```bash
uv pip install -r requirements.txt
```

5. Install llt as a CLI tool:
```bash
# Make the main.py executable
chmod +x main.py

# Create a symlink in a directory in your PATH
# Option 1: User-specific installation (recommended)
mkdir -p ~/.local/bin
ln -s "$(pwd)/main.py" ~/.local/bin/llt

# Option 2: System-wide installation (requires sudo)
# sudo ln -s "$(pwd)/main.py" /usr/local/bin/llt

# Verify the installation
which llt
llt --help
```

6. Set up environment:
```bash
# Set data directory
export LLT_PATH=$HOME/.llt

# Add this to your shell's rc file (.bashrc, .zshrc, etc.) to make it permanent
echo 'export LLT_PATH=$HOME/.llt' >> ~/.bashrc  # or ~/.zshrc

echo 'export LLT_DIR=$HOME/llt' >> ~/.bashrc  # or ~/.zshrc


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

## Advanced Workflows

The following workflows demonstrate powerful usage patterns for complex development scenarios. Each workflow combines multiple llt features to create sophisticated development pipelines.

### 1. Full Development Pipeline
Automates the complete development lifecycle from initial design to implementation and testing.

```bash
# Step 1: Project Initialization
# - Loads semantic context from embeddings
# - Processes architecture document
# - Establishes development environment
llt --model claude-sonnet \
    --embeddings project.csv \
    --load project/base.ll \
    --file architecture.md \
    --role system \
    --tools true \
    --complete --temperature 0.7 \
    --write project/init.ll

# Step 2: Code Generation & Validation
# - Generates implementation code
# - Performs automatic testing
# - Creates safety backups
llt --model claude-sonnet \
    --load project/init.ll \
    --tools true \
    --edit --backup true --lang python \
    --execute --timeout 60 \
    --write project/implementation.ll

# Step 3: Documentation Generation
# - Creates documentation from implementation
# - Runs final validation tests
# - Produces complete project state
llt --model claude-sonnet \
    --load project/implementation.ll \
    --tools true \
    --edit --lang markdown \
    --execute --verify true \
    --write project/complete.ll
```

### 2. Code Review & Refactoring Pipeline
Facilitates comprehensive code analysis and systematic refactoring.

```bash
# Step 1: Codebase Analysis
# - Processes entire codebase semantically
# - Identifies refactoring opportunities
# - Creates analysis report
llt --model claude-sonnet \
    --embeddings codebase.csv \
    --load review/start.ll \
    --file src/*.py \
    --tools true \
    --complete --temperature 0.8 \
    --write review/analysis.ll

# Step 2: Automated Refactoring
# - Implements suggested improvements
# - Maintains code safety with backups
# - Verifies changes through testing
llt --model claude-sonnet \
    --load review/analysis.ll \
    --tools true \
    --edit --backup true --force true \
    --execute --verify true \
    --write review/refactored.ll
```

### 3. Multi-Modal Development
Handles complex development scenarios involving visual designs and implementation.

```bash
# Step 1: Visual Analysis
# - Processes design diagrams
# - Extracts system architecture
# - Creates implementation plan
llt --model claude-sonnet \
    --file design.png \
    --prompt "Analyze this system diagram" \
    --tools true \
    --complete --temperature 0.7 \
    --write visual/analysis.ll

# Step 2: Implementation
# - Generates code from analysis
# - Includes automatic testing
# - Creates documentation
llt --model claude-sonnet \
    --load visual/analysis.ll \
    --tools true \
    --edit --backup true --lang python \
    --execute --timeout 30 \
    --write visual/implementation.ll
```

### Key Features Used

#### Safety & Stability
- `--backup true`: Automatic backup creation before modifications
- `--verify true`: Validation of changes
- `--timeout`: Execution time limits for safety

#### Context Management
- `--embeddings`: Semantic context from existing code/docs
- `--load/--write`: State preservation between steps
- `--tools true`: Enhanced capability access

#### Workflow Control
- `--temperature`: Control over generation creativity
- `--role`: Context-specific behavior
- `--force`: Override protection when needed

### Best Practices

1. **State Management**
   - Always use `--write` to preserve pipeline state
   - Load previous states with `--load` for continuity
   - Maintain backups with `--backup true`

2. **Safety Measures**
   - Set appropriate timeouts for executions
   - Use verification steps for critical changes
   - Maintain semantic context with embeddings

3. **Pipeline Design**
   - Break complex workflows into discrete steps
   - Preserve intermediate states
   - Include validation between transformations

## Plugin System

### Plugin Specification
Plugins are defined using Python decorators and type hints for automatic integration.

```python
from plugins import llt
from typing import List, Dict, Optional, Union

@llt
def pdf_extract(messages: List[Dict], args: Dict, index: int = -1) -> List[Dict]:
    """
    Description: Extract and process text content from PDF files
    Type: transformer
    Default: false
    Flag: pdf
    Options:
        - ocr: bool = False      # Enable OCR for scanned documents
        - pages: str = "all"     # Page range (e.g., "1-5,7,9-11")
        - tables: bool = False   # Extract tables as structured data
    """
    # Plugin implementation
    return messages

@llt
def code_metrics(messages: List[Dict], args: Dict) -> Dict[str, Union[int, float]]:
    """
    Description: Analyze code quality and complexity
    Type: analyzer
    Default: false
    Flag: metrics
    Options:
        - threshold: int = 10    # Complexity threshold
        - format: str = "json"   # Output format (json/yaml)
    """
    # Plugin implementation
    return {
        "complexity": 8,
        "maintainability": 85.5,
        "test_coverage": 92.3
    }
```

### Plugin Usage in Workflows

#### 1. PDF Processing Pipeline
Demonstrates PDF extraction and analysis workflow.

```bash
# Step 1: Extract Content from PDF
# - Processes PDF document with OCR
# - Extracts tables and text
# - Preserves document structure
llt --model claude-sonnet \
    --file document.pdf \
    --plugin pdf --ocr true --tables true \
    --complete --temperature 0.7 \
    --write pdf/extracted.ll

# Step 2: Content Analysis
# - Analyzes extracted content
# - Generates structured summary
# - Creates markdown documentation
llt --model claude-sonnet \
    --load pdf/extracted.ll \
    --tools true \
    --edit --lang markdown \
    --complete \
    --write pdf/analysis.ll
```

#### 2. Code Quality Pipeline
Combines code metrics with refactoring suggestions.

```bash
# Step 1: Code Analysis
# - Calculates code metrics
# - Identifies improvement areas
# - Generates quality report
llt --model claude-sonnet \
    --file src/*.py \
    --plugin metrics --threshold 8 --format json \
    --complete --temperature 0.7 \
    --write metrics/analysis.ll

# Step 2: Automated Improvements
# - Implements suggested changes
# - Verifies quality improvements
# - Updates documentation
llt --model claude-sonnet \
    --load metrics/analysis.ll \
    --tools true \
    --edit --backup true --lang python \
    --execute --verify true \
    --write metrics/improved.ll
```

### Creating Custom Plugins

1. **Basic Plugin Structure**
```python
@llt
def custom_plugin(messages: List[Dict], args: Dict) -> List[Dict]:
    """
    Description: Your plugin description
    Type: transformer|analyzer|generator
    Default: false
    Flag: custom_name
    Options:
        - option1: type = default  # Description
        - option2: type = default  # Description
    """
    # Implementation
    return messages
```

2. **Plugin Types**
- `transformer`: Modifies message content
- `analyzer`: Provides analysis without modification
- `generator`: Creates new content or files

3. **Integration Points**
```bash
# Direct plugin usage
llt --plugin custom_name --option1 value1

# Chained plugin execution
llt --plugin "custom1,custom2" --custom1.opt1 val1 --custom2.opt2 val2

# Plugin with model completion
llt --model claude-sonnet --plugin custom_name --complete
```

### Plugin Best Practices

1. **Input Validation**
```python
@llt
def validated_plugin(messages: List[Dict], args: Dict) -> List[Dict]:
    """
    Description: Plugin with input validation
    Type: transformer
    Flag: validated
    """
    # Validate input
    if not messages or not isinstance(messages, list):
        raise ValueError("Invalid message format")
    
    # Validate args
    threshold = args.get('threshold', 10)
    if not isinstance(threshold, (int, float)):
        raise TypeError("Threshold must be numeric")
    
    # Process with validation
    return messages
```

2. **Error Handling**
```python
@llt
def robust_plugin(messages: List[Dict], args: Dict) -> List[Dict]:
    """
    Description: Plugin with error handling
    Type: transformer
    Flag: robust
    """
    try:
        # Main processing
        result = process_messages(messages)
        
    except FileNotFoundError:
        logging.error("Required file not found")
        return messages
        
    except Exception as e:
        logging.error(f"Plugin error: {str(e)}")
        raise PluginError(f"Processing failed: {str(e)}")
        
    return result
```

3. **Performance Optimization**
```python
@llt
def optimized_plugin(messages: List[Dict], args: Dict) -> List[Dict]:
    """
    Description: Performance-optimized plugin
    Type: transformer
    Flag: optimized
    Options:
        - batch_size: int = 100  # Processing batch size
    """
    # Batch processing
    batch_size = args.get('batch_size', 100)
    results = []
    
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        results.extend(process_batch(batch))
    
    return results
```