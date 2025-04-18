# llt usage

## transform/markdown

Transform unstructured text into structured Markdown.

1) Create a new generic base with specific instructions.

```bash
llt --model claude-3-5-sonnet-20241022 --prompt Transform the unstructured text in the text tags into proper Markdown. --xml instruction --auto --write transform/markdown
```

2) Use the `transform/markdown` ll to transform the unstructured text in the text tags into proper Markdown.

```bash
llt --model claude-3-5-sonnet-20241022 --load transform/markdown --paste --xml text --complete --auto
```

This command loads the prepared 

If every ll can be turned into a standalone tool, then we can generically create a new bash function markdown_transform that will take a string and return a string. Instead of pasting the text, we can pass the text as an argument to the function.

```bash
function markdown_transform() {
    input=$( [ -t 0 ] && echo "$1" || cat - )
    llt --model claude-3-5-sonnet-20241022 --load transform/markdown --prompt "$input" --xml text --complete --auto
}
```


## transform/prompt


## optimize-prompt

Create a tool that optimizes simple prompts into more effective ones.

1) Create a new optimize-prompt template:

```bash
llt --auto --prompt "The user prompt is in the text tags. Your task is to grok what the user wants, and beef up the prompt significantly. Provide your new prompt in prompt xml tags." --xml instruction --write optimize-prompt

```

```llt
llt> prompt
Added new message to the conversation.

llt> xml_wrap

llt> write
Saved 1 messages to '/home/luciano/.llt/ll/optimize-prompt'.
llt> q
```


2) Use the optimize-prompt template to enhance a basic prompt:

```bash
llt --auto --load optimize-prompt --prompt "look at current directory and explain project structure" --xml text --complete --change_role user --parse_xml prompt --detach
```

```llt
llt> load
Loaded 1 messages from '/home/luciano/.llt/ll/optimize-prompt'.

llt> prompt
Added new message to the conversation.

llt> xml_wrap

llt> complete
 <prompt>
<objective>
Analyze the current working directory's contents and provide a detailed, structured explanation of the project's organization, including file hierarchy, key components, and potential relationships between files.
</objective>

<requirements>
1. Perform a recursive directory listing showing all files and subdirectories
2. Identify and categorize files by type (source code, configuration, documentation, etc.)
3. Analyze file naming patterns and directory structure for organizational logic
4. Highlight potential entry points or main files (e.g., package.json, main.py, Makefile)
5. Note any unusual or noteworthy file/directory structures
6. Infer project type (web app, CLI tool, library, etc.) based on structure
7. Point out any missing conventional directories/files for the apparent project type
8. Provide the analysis in a clear, hierarchical format with explanations
</requirements>

<format>
1. Start with overall project type assessment
2. Present directory tree (abbreviated if very large)
3. Break down structure by logical components
4. Explain significance of key files/directories
5. Note any structural observations or anomalies
6. Conclude with summary of project organization quality
</format>

<additional_instructions>
- For large projects, focus on the most relevant parts of the structure
- Highlight build/configuration files and their relationships
- Note version control artifacts if present
- Mention test directories and their organization
- Point out documentation locations
- Flag any potentially problematic structures
</additional_instructions>
</prompt>

llt> change_role
Changed role of message at index -1 to: user

llt> parse_xml

llt> detach
Detached message at index 0.

llt> complete

llt> q
```

This workflow:
- Takes your simple prompt and passes it to the optimization tool
- The model generates an improved, more detailed prompt
- The `--detach` flag pops the most recent message (the optimized prompt)
- `--change_role user` sets that response as a user message
- The final `--complete` runs the model with this optimized prompt

This technique helps transform simple, underspecified prompts into more effective ones automatically.

We can turn this into a bash function that takes a prompt and returns an optimized prompt.

```bash
function optimize_prompt() {
    input=$( [ -t 0 ] && echo "$1" || cat - )
    llt --load optimize-prompt --prompt "$input" --xml text --complete --detach --change_role user --complete
}

optimize_prompt "look at current directory and explain project structure"   
```
# llt usage

## transform/markdown

Transform unstructured text into structured Markdown.

1) Create a new generic base with specific instructions.

```bash
llt --model claude-3-5-sonnet-20241022 --prompt Transform the unstructured text in the text tags into proper Markdown. --xml instruction --auto --write transform/markdown
```

2) Use the `transform/markdown` ll to transform the unstructured text in the text tags into proper Markdown.

```bash
llt --model claude-3-5-sonnet-20241022 --load transform/markdown --paste --xml text --complete --auto
```

This command loads the prepared 

If every ll can be turned into a standalone tool, then we can generically create a new bash function markdown_transform that will take a string and return a string. Instead of pasting the text, we can pass the text as an argument to the function.

```bash
function markdown_transform() {
    input=$( [ -t 0 ] && echo "$1" || cat - )
    llt --model claude-3-5-sonnet-20241022 --load transform/markdown --prompt "$input" --xml text --complete --auto
}
```


## transform/prompt


## optimize-prompt

Create a tool that optimizes simple prompts into more effective ones.

1) Create a new optimize-prompt template:

```bash
llt --auto --prompt "The user prompt is in the text tags. Your task is to grok what the user wants, and beef up the prompt significantly. Provide your new prompt in prompt xml tags." --xml instruction --write optimize-prompt

```

```llt
llt> prompt
Added new message to the conversation.

llt> xml_wrap

llt> write
Saved 1 messages to '/home/luciano/.llt/ll/optimize-prompt'.
llt> q
```


2) Use the optimize-prompt template to enhance a basic prompt:

```bash
llt --auto --load optimize-prompt --prompt "look at current directory and explain project structure" --xml text --complete --change_role user --parse_xml prompt --detach
```

```llt
llt> load
Loaded 1 messages from '/home/luciano/.llt/ll/optimize-prompt'.

llt> prompt
Added new message to the conversation.

llt> xml_wrap

llt> complete
 <prompt>
<objective>
Analyze the current working directory's contents and provide a detailed, structured explanation of the project's organization, including file hierarchy, key components, and potential relationships between files.
</objective>

<requirements>
1. Perform a recursive directory listing showing all files and subdirectories
2. Identify and categorize files by type (source code, configuration, documentation, etc.)
3. Analyze file naming patterns and directory structure for organizational logic
4. Highlight potential entry points or main files (e.g., package.json, main.py, Makefile)
5. Note any unusual or noteworthy file/directory structures
6. Infer project type (web app, CLI tool, library, etc.) based on structure
7. Point out any missing conventional directories/files for the apparent project type
8. Provide the analysis in a clear, hierarchical format with explanations
</requirements>

<format>
1. Start with overall project type assessment
2. Present directory tree (abbreviated if very large)
3. Break down structure by logical components
4. Explain significance of key files/directories
5. Note any structural observations or anomalies
6. Conclude with summary of project organization quality
</format>

<additional_instructions>
- For large projects, focus on the most relevant parts of the structure
- Highlight build/configuration files and their relationships
- Note version control artifacts if present
- Mention test directories and their organization
- Point out documentation locations
- Flag any potentially problematic structures
</additional_instructions>
</prompt>

llt> change_role
Changed role of message at index -1 to: user

llt> parse_xml

llt> detach
Detached message at index 0.

llt> complete

llt> q
```

This workflow:
- Takes your simple prompt and passes it to the optimization tool
- The model generates an improved, more detailed prompt
- The `--detach` flag pops the most recent message (the optimized prompt)
- `--change_role user` sets that response as a user message
- The final `--complete` runs the model with this optimized prompt

This technique helps transform simple, underspecified prompts into more effective ones automatically.

We can turn this into a bash function that takes a prompt and returns an optimized prompt.

```bash
function optimize_prompt() {
    input=$( [ -t 0 ] && echo "$1" || cat - )
    llt --load optimize-prompt --prompt "$input" --xml text --complete --detach --change_role user --parse_xml prompt --complete
}

     
optimize_prompt "look at current directory and explain project structure"   
```

```llt
llt> load
Loaded 1 messages from '/home/luciano/.llt/ll/optimize-prompt'.

llt> prompt
Added new message to the conversation.

llt> xml_wrap

llt> complete

Here's a new prompt:
<prompt>
<objective>
Analyze the current working directory's contents and provide a detailed, structured explanation of the project's organization, including file hierarchy, key components, and potential relationships between files.
</objective>

<requirements>
1. Perform a recursive directory listing showing all files and subdirectories
2. Identify and categorize files by type (source code, configuration, documentation, etc.)
3. Analyze file naming patterns and directory structure for organizational logic
4. Highlight potential entry points or main files (e.g., package.json, main.py, Makefile)
5. Note any unusual or noteworthy file/directory structures
6. Infer project type (web app, CLI tool, library, etc.) based on structure
7. Point out any missing conventional directories/files for the apparent project type
8. Provide the analysis in a clear, hierarchical format with explanations
</requirements>

<format>
1. Start with overall project type assessment
2. Present directory tree (abbreviated if very large)
3. Break down structure by logical components
4. Explain significance of key files/directories
5. Note any structural observations or anomalies
6. Conclude with summary of project organization quality
</format>

<additional_instructions>
- For large projects, focus on the most relevant parts of the structure
- Highlight build/configuration files and their relationships
- Note version control artifacts if present
- Mention test directories and their organization
- Point out documentation locations
- Flag any potentially problematic structures
</additional_instructions>
</prompt>

llt> parse_xml prompt

llt> change_user user
llt> change_model gpt-4.1-2025-04-14

llt> complete

llt> q
```
