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
[Screencast from 05-28-2024 08:58:01 PM.webm](https://github.com/llorella/llt/assets/110218399/be7f9107-d58e-4724-9b7c-230c1fb63fd3)


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
