# Chat CLI
Chat CLI is an interactive command-line interface that utilizes OpenAI's GPT-3.5 Turbo model to create an engaging chat experience. This project allows you to have real-time conversations with the AI, save and load chat history, and use pre-defined prompts to guide the conversation.

## Features
Real-time chat with OpenAI's GPT-3.5 Turbo model
Save and load chat history in JSON format
Provide initial prompts to guide the conversation
Configurable settings for the AI model, history directory, and prompts
Installation

## Prerequisites

Python 3.8 or higher
An OpenAI API key
Setup
Clone the repository:
```bash
git clone https://github.com/yourusername/chat-cli.git
cd chat-cli
```

Install the required dependencies:
```bash
pip install -r requirements.txt
```

Set up the OpenAI API key:
```bash
export OPENAI_API_KEY=your_openai_api_key
```

Configure the application settings in config.json:
```json
{
"model": "gpt-3.5-turbo",
"history_directory": "./sandbox/",
"prompts": ["You are a helpful AI assistant."]
}
```

## Usage
To start a chat session, run the following command:

```python test.py [-f FILE] [-p PROMPTS]
```

## Options
-f FILE: JSON file containing the history of previous runs. If provided, the conversation will continue from the loaded history.
-p PROMPTS: List of preset prompts as a comma-separated string or a text file containing the prompts, one per line. At least one prompt must be provided if there is no history file.

## Commands during chat session
s: Save the chat history to a JSON file. You will be prompted for the filename.
x: Exit the chat session.

## License
This project is released under the MIT License. See LICENSE for details.