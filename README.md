# Chat CLI

chat_cli is a highly configurable command-line interface for interacting with GPT-based models. It enables you to have interactive conversations, store and load conversation history, and tweak various settings for an optimal chat experience.

## Features

- Interactive conversations with GPT-based models
- Configurable temperature and other options
- Preset prompts for conversation
- Save and load conversation history
- Command-line arguments for customizing settings
## Prerequisites

Python 3.8 or higher
An OpenAI API key

## Setup
Clone the repository:
```bash
git clone https://github.com/yourusername/chat_cli.git
cd chat_cli
```

Install the required dependencies:
```bash
pip install -r requirements.txt
```

Set up the OpenAI API key:
```bash
export OPENAI_API_KEY=your_openai_api_key
```

Add the chat_cli directory to your `PYTHONPATH`:
```bash
export PYTHONPATH=$PYTHONPATH:/path/to/chat_cli
```

Create an alias for chat_cli (optional):
```bash
alias chat_cli="python3 /path/to/chat_cli/test.py"
```

Configure the application settings in config.json:
```json
{
    "api": {
      ...,
      "model": "gpt-3.5-turbo"
    },
    "conversation": {
      "_comment": "Conversation settings",
      "system": [0],
      "prompts": ["You are a helpful AI assistant."],
      "options": {"temperature": 1.0, "top_p": 1.0}
    },
    "io": {
      "_comment": "Input and output settings",
      "history_directory": "/your/directory/here",
      "input_file": "base.json",
      "output_file": "output.json"
    },
    "extensions": {
    }
  }
```

## Usage
To start a chat session, run the following command:

```bash 
chat_cli [-h] [-c CONFIG] [-d HISTORY] [-f FILE] [-p [PROMPTS ...]] [-t TEMPERATURE]
```

## Options
-c specifies different config.json path from default in project directory. Either way, command line arguments will replace corresponding config values at runtime, but leave config file unchanged. 

## Commands during chat session
s: Save the chat history to a JSON file. You can enter filename or use config input file if it exists. 
x: Exit the chat session.
l: load chat history file, set root message reference to current chat history, and resume with most recent message from loaded history. This allows chaining chat histories at runtime. 
r: print current message and all previous messages in chat history. 
[option]: one of options in config['conversation']['options'] for real time tuning of model parameters.

## License
This project is released under the MIT License. See LICENSE for details.
