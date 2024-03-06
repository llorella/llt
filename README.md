Optional flags provide additional customization:

- `--ll_file, -l`: Specify the filename for message history (default: `out.ll`).
- `--content_input, -f`: Submit an optional prompt file (default: empty).
- `--code_dir, -e`: Specify the root directory for execution files (default: `exec`).
- `--conversation_dir, -d`: Specify the message history directory (default: `msg`).
- `--cmd_dir, -d`: Specify the message history directory (default: `commands`).

- `--prompt, -p`: Preload user message with input string.
- `--non_interactive`: Run in non-interactive mode.
- 
- `--role, -r`: Specify the user's role (default: `user`).
- `--model, -m`: Specify the model to use from available options (default: `gpt-4`).
- `--temperature, -t`: Specify the temperature for text generation (default: `0.9`).

### Commands and Examples:

Type `help` within the application to see available commands. Some common commands include:

- `load`: Load a message history.
  ```
  llt> load
  Filename: conversation_history.ll
  ```
- `write`: Write the current conversation to the history file.
  ```
  llt> write
  Context file: conversation_history.ll
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
  Content: Can you explain the concept of recursion to me?
  ```
- `complete`: Prompt the model to generate a completion.
  ```
  llt> complete
  Assistant: Certainly! Recursion is a programming concept where a function calls itself within its own definition. It's a powerful technique for solving problems that can be broken down into smaller, similar subproblems. [...]
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

Contributions to Little Language Terminal are welcome! Please feel free to fork the repository, make changes, and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
