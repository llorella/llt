# Little Language Terminal (llt)

Little Language Terminal (llt) is a conversational tool designed to process messages, generate text based on provided context, and handle the integration of code generation into a structured environment. It leverages language models (e.g., GPT-4) to provide intelligent and context-aware responses and offers a suite of utilities for message handling and code management.

## Features

- **Conversational Interface**: Interact with the tool using a command-line interface that understands and responds to conversational prompts.
- **Message Management**: Load, view, and write message histories for context preservation and conversation continuation.
- **Code Generation**: Generate and manage code snippets that get saved into corresponding directories based on the conversation history.
- **File Inclusion**: Include the content of a specified file into the current message.
- **Image Attachment**: Encode and attach images to messages in a conversation.
- **Contextual Directory Mapping**: Automatically map conversation history files (.ll) in the message directory to corresponding directories in the execution directory for code snippets.

## Project Structure

### Main Components:

- `main.py`: The core entry point of the application. It processes command-line arguments, sets up the environment, and runs the primary application loop.
- `editor.py`: This module contains functions for editing code blocks, including extracting code from markdown and interfacing with external text editors.
- `api.py`: Facilitates communication with the OpenAI API for generating text completions and handling stream responses.
- `message.py`: Contains functions for loading, viewing, writing, and modifying messages within the conversational history.
- `utils.py`: Provides utility functions for the application such as input helpers and color-coded printing.

### Message Directory (`msg_dir`):

- This directory contains `.ll` files, each representing a conversation's history. These files store messages in a JSON format to maintain context for the language model.

### Execution Directory (`exec_dir`):

- Corresponds to the `msg_dir`. Each `.ll` file from `msg_dir` will have a paired directory in `exec_dir`. This directory stores generated code files and assets related to the conversation history.

## Getting Started

### Prerequisites:

- Ensure you have Python 3.7 or higher installed.
- Install the necessary Python libraries using:
  ```bash
  pip install -r requirements.txt
  ```
- Set up the `LLT_PATH` environment variable to point to the root directory containing `msg_dir` and `exec_dir`.

### Running the Application:

Run the application using the following command:

Optional flags provide additional customization:

- `--context_file, -c`: Specify the filename for message history (default: `out.ll`).
- `--content_input, -f`: Submit an optional prompt (default: empty).
- `--exec_dir, -e`: Specify the root directory for execution files (default: `exec`).
- `--message_dir, -d`: Specify the message history directory (default: `msg`).
- `--role, -r`: Specify the user's role (default: `user`).
- `--model, -m`: Specify the model to use from available options (default: first available model).
- `--temperature, -t`: Specify the temperature for text generation (default: `0.9`).

### Commands:

Type `help` within the application to see available commands. Some common commands include:

- `load`: Load a message history.
- `write`: Write the current conversation to the history file.
- `view`: View the messages in the current session.
- `new`: Add a new message to the conversation.
- `complete`: Prompt the model to generate a completion.
- `edit`: Edit and manage code blocks from the last message.
- `file`: Include a file's content into the message.
- `image`: Attach an encoded image to the message.
- `quit`: Exit the program.

## Development and Contributions

Contributions to Little Language Terminal are welcome! Please feel free to fork the repository, make changes, and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

