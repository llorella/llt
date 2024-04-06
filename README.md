llt is a UNIX-like terminal application that allows users to interact with a language model using commands included in the plugins definition in main.py. It is designed to be easily extensible and customizable, allowing users to add their own commands and functionality to the application. Commands range from simple actions like loading a message history to more complex tasks like editing code blocks or including images in the conversation. llt is a work in progress and is still in development, but can reliably serve as a functional tool as both a natural language shell and non-interactive UNIX command. 

### Installation

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
usage: main.py [-h] [--ll_file LL_FILE] [--file_include FILE_INCLUDE] [--prompt PROMPT] [--role ROLE]
               [--model MODEL] [--temperature TEMPERATURE] [--image_path IMAGE_PATH]
               [--cmd_dir CMD_DIR] [--exec_dir EXEC_DIR] [--ll_dir LL_DIR]
               [--non_interactive]

llt, little language tool and terminal 

options:
  -h, --help            show this help message and exit
  --ll_file LL_FILE, -l LL_FILE
                        Language log file. List of natural language messages stored as JSON.
  --file_include FILE_INCLUDE, -f FILE_INCLUDE
                        Content file to include in conversation. 
  --prompt PROMPT, -p PROMPT
                        Prompt string.
  --role ROLE, -r ROLE  Specify role.
  --model MODEL, -m MODEL
                        Specify model.
  --temperature TEMPERATURE, -t TEMPERATURE

                        Specify temperature.
  --non_interactive, -n
                        Run in non-interactive mode.

  --image_path IMAGE_PATH
                        Specify the path to an image file.
  --cmd_dir 
                        Specify the command history directory (default: `commands`).
  --exec_dir EXEC_DIR
                        Specify the root directory for execution files (default: `exec`).
  --ll_dir LL_DIR
                        Specify the directory for message history (default: `msg`).
```



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
