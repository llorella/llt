import requests
import os
import yaml
import json
from typing import List, Dict, Any, Iterable, cast, Literal, Union, Optional, Tuple 

import anthropic
from anthropic.types import ToolUseBlock, ContentBlockStopEvent
from tools import registry_to_json_schema, make_scheduled_from_tool_use, ScheduledCommand

from message import Message
from utils import (
    Colors, file_handler, input_handler, InputValue
) 
from tools import llt
from logger import llt_logger

from pydantic import BaseModel, ValidationError, TypeAdapter

class TextDelta(BaseModel):
    type: Literal["text_delta"]
    text: str

class InputJSONDelta(BaseModel):
    type: Literal["input_json_delta"]
    partial_json: str

class TextBlockModel(BaseModel):
    type: Literal["text"]
    text: str
    citations: Optional[List[Dict[str, Any]]] = None

class ToolUseBlockModel(BaseModel):
    type: Literal["tool_use"]
    id: str
    name: str
    input: Dict[str, Any]

# High-level helper events for processing
class TextEventModel(BaseModel):
    type: Literal["text"]
    text: str
    snapshot: str

class InputJsonEventModel(BaseModel):
    type: Literal["input_json"]
    partial_json: str
    snapshot: Dict[str, Any]

# Raw stream events from Anthropic API
class ContentBlockDeltaModel(BaseModel):
    type: Literal["content_block_delta"]
    delta: Union[TextDelta, InputJSONDelta]
    index: int

class RawContentBlockStopEventModel(BaseModel):
    type: Literal["content_block_stop"]
    content_block: Union[TextBlockModel, ToolUseBlockModel]
    index: int

class MessageDeltaUsage(BaseModel):
    output_tokens: int

class Delta(BaseModel):
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None

class MessageDeltaModel(BaseModel):
    type: Literal["message_delta"]
    delta: Delta
    usage: Optional[MessageDeltaUsage] = None

class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

class MessageModel(BaseModel):
    """Model representing Anthropic API Message (distinct from our Message class from message.py)"""
    id: str
    type: str
    role: str
    content: List[Dict[str, Any]]
    model: str
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Optional[Usage] = None

class MessageStopModel(BaseModel):
    type: Literal["message_stop"]
    message: MessageModel  # Using the Message class imported from message.py

# Union type for all stream events
StreamingEvent = Union[
    TextEventModel,
    InputJsonEventModel,
    ContentBlockDeltaModel,
    RawContentBlockStopEventModel,
    MessageDeltaModel,
    MessageStopModel
]
streaming_adapter: TypeAdapter[StreamingEvent] = TypeAdapter(StreamingEvent)

# Cached tool schema and its version identifier
_CACHED_ANTHROPIC_TOOL_CATALOGUE = None
_CACHED_TOOLS_JSON_MTIME = None
# Path to tools.json, assuming it's in LLT_DIR or CWD (defaults to CWD if LLT_DIR is not set).
TOOLS_JSON_PATH = os.path.join(os.getenv("LLT_DIR", os.getcwd()), "tools.json")


# Type mapping from tool spec to JSON schema
TYPE_MAP = {
    "int": "integer",
    "float": "number",
    "str": "string",
    "string": "string",
    "bool": "boolean",
    "boolean": "boolean",
}

def load_config(path: str):
    try:
        with open(path, 'r') as config_file:
            config = yaml.safe_load(config_file)
            return config
    except Exception as e:
        Colors.print_colored(f"Error loading config: {e}", Colors.RED)
        return {}


def list_model_names(providers: Dict[str, Any]) -> List[str]:
    """
    Helper to produce a list of "model-version" strings from your config.
    """
    return [
        f"{model}-{version}"
        for _, details in providers.items()
        for model, versions in details.get('models', {}).items()
        for version in versions
    ]


api_config = load_config(os.path.join(os.getenv("LLT_DIR", ""), "config.yaml"))
full_model_choices = list_model_names(api_config["providers"])


def get_provider_details(model_name: str):
    """
    Returns (provider, api_key_string, completion_url)
    or raises ValueError if not found in config.
    """
    for provider, details in api_config["providers"].items():
        for model, versions in details.get("models", {}).items():
            possible_names = [f"{model}-{ver}" for ver in versions]
            if model_name in possible_names:
                return (
                    provider,
                    details.get("api_key", None),
                    details.get("completion_url", None)
                )
    raise ValueError(f"Model {model_name} not found in config.")

class OpenAIFunctionParameter(BaseModel):
    """Parameter definition for an OpenAI function."""
    type: str
    description: Optional[str] = None
    enum: Optional[List[str]] = None
    
class OpenAIFunctionParameters(BaseModel):
    """Parameters for an OpenAI function."""
    type: Literal["object"]
    properties: Dict[str, Dict[str, Any]]
    required: Optional[List[str]] = None
    additionalProperties: Optional[bool] = False

class OpenAIFunction(BaseModel):
    """Definition of an OpenAI function."""
    name: str
    description: str
    parameters: OpenAIFunctionParameters

class OpenAITool(BaseModel):
    """OpenAI tool definition."""
    type: Literal["function"]
    function: OpenAIFunction

class OpenAIFunctionCall(BaseModel):
    """Function call from OpenAI."""
    id: str
    call_id: str
    type: Literal["function_call"]
    name: str
    arguments: str  # JSON string of arguments

    def to_tool_use_block(self) -> ToolUseBlock:
        """Convert OpenAI function call to Anthropic ToolUseBlock."""
        try:
            args = json.loads(self.arguments)
            return ToolUseBlock(
                id=self.id,
                type="tool_use",
                name=self.name,
                input=args
            )
        except Exception as e:
            llt_logger.log_error(f"Error converting OpenAI function call to tool use block: {e}")
            return ToolUseBlock(
                id=self.id,
                type="tool_use",
                name=self.name,
                input={}
            )

def convert_tools_to_functions(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert LLT tool definitions to OpenAI function format.
    Handles tools with input_schema format as shown by 'tool' output.
    """
    openai_tools = []
    
    for tool in tools:
        # Skip tools without necessary fields
        if not tool.get("name") or not tool.get("description"):
            llt_logger.log_warning(f"Skipping tool without name or description: {tool}")
            continue
            
        # Convert input_schema to OpenAI parameters format
        parameters = {"type": "object", "properties": {}}
        required = []
        
        # Process input_schema if present
        if "input_schema" in tool:
            input_schema = tool.get("input_schema", {})
            
            # Copy type from input_schema
            if "type" in input_schema:
                parameters["type"] = input_schema.get("type")
                
            # Copy properties 
            if "properties" in input_schema:
                for prop_name, prop_details in input_schema.get("properties", {}).items():
                    parameters["properties"][prop_name] = {
                        "type": prop_details.get("type", "string"),
                        "description": prop_details.get("description", f"Parameter '{prop_name}'")
                    }
                    
                    # Add default value if present
                    if "default" in prop_details:
                        parameters["properties"][prop_name]["default"] = prop_details.get("default")
                        
            # Copy required fields
            if "required" in input_schema:
                required = input_schema.get("required", [])
                
            # Set required field in parameters if we have required properties
            if required:
                parameters["required"] = required
                
            # Add additionalProperties
            parameters["additionalProperties"] = False
            
        # Create function definition
        function_def = {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": parameters
            }
        }
        
        openai_tools.append(function_def)
        
#     llt_logger.log_info(f"Converted {len(openai_tools)} tools to OpenAI function format")
    return openai_tools

def send_request(
    completion_url: str,
    api_key_string: str,
    messages: List[Message],
    args: Dict[str, Any]
) -> Union[Message, Tuple[List[Message], List[ScheduledCommand]]]:
    """
    Generic request to a completion endpoint that streams tokens.
    Supports OpenAI tool/function calling.
    """
    headers = {
        "Authorization": f"Bearer {os.getenv(api_key_string)}",
        "Content-Type": "application/json",
    }
    
    # Prepare request data
    data = {
        "messages": messages,
        "model": args.get('model'),
        "temperature": args.get('temperature'),
        "stream": True,
    }
    
    # Handle max tokens parameter
    if args.get('max_tokens'):
        data["max_tokens"] = args['max_tokens']
    
    # Add tools/function calling support for OpenAI models
    use_tool_mode = bool(args.get("use_tool", False))
    tool_blocks = []
    
    if use_tool_mode:
#         llt_logger.log_info("Use tool mode enabled for OpenAI API. Setting up functions.")
        
        # Get tools from the same place Anthropic gets them
        openai_tools = convert_tools_to_functions(registry_to_json_schema())
        
        print(f"OpenAI tools: {json.dumps(openai_tools, indent=2)}")
        
        # Add tools to request
        if openai_tools:
            data["tools"] = openai_tools
            data["tool_choice"] = "auto"  # Let the model decide when to call functions
            
            llt_logger.log_info("Sending request to OpenAI API with tools.", {
                "model": data.get("model", "unknown"),
                "message_count": len(messages),
                "tool_count": len(openai_tools),
            })

    full_response_content = ""
    response_buffer = []
    final_status_code = None

    try:
        with requests.post(
            completion_url, headers=headers, json=data, stream=True
        ) as response:
            for chunk in response.iter_lines():
                if chunk:
                    decoded_chunk = chunk.decode("utf-8")
                    response_buffer.append(decoded_chunk) # buffer all chunks

                    if decoded_chunk.startswith("data: [DONE]"):
                        break
                    if decoded_chunk.startswith("data: "):
                        payload = decoded_chunk[len("data: "):]
                        try:
                            json_data = json.loads(payload)
                            
                            # Handle OpenAI function calling
                            if "tool_calls" in json_data:
                                # Function call in non-streaming response
                                for tool_call in json_data.get("tool_calls", []):
                                    if tool_call.get("type") == "function":
                                        function_call = OpenAIFunctionCall(
                                            id=tool_call.get("id", ""),
                                            call_id=tool_call.get("id", ""),  # OpenAI uses just id
                                            type="function_call",
                                            name=tool_call.get("function", {}).get("name", ""),
                                            arguments=tool_call.get("function", {}).get("arguments", "{}")
                                        )
                                        tool_blocks.append(function_call.to_tool_use_block())
                                continue
                                
                            # Handle OpenAI streaming response
                            choice = json_data.get("choices", [{}])[0]
                            
                            # Check for tool/function calls in streaming
                            delta = choice.get("delta", {})
                            if "tool_calls" in delta:
                                # Extract function call information
                                tool_call = delta.get("tool_calls", [{}])[0]
                                
                                if tool_call.get("type") == "function":
                                    function_info = tool_call.get("function", {})
                                    
                                    # Create or update function call
                                    tool_id = tool_call.get("id", "")
                                    function_name = function_info.get("name", "")
                                    function_args = function_info.get("arguments", "")
                                    
                                    # We'd need to accumulate these properly in a real implementation
                                    # Here we're just capturing complete function calls
                                    if function_name and function_args and function_args != "":
                                        function_call = OpenAIFunctionCall(
                                            id=tool_id,
                                            call_id=tool_id,  # OpenAI uses just id
                                            type="function_call",
                                            name=function_name,
                                            arguments=function_args
                                        )
                                        tool_blocks.append(function_call.to_tool_use_block())
#                                         llt_logger.log_info(f"Detected function call: {function_name}")
                                continue
                                    
                            # Process regular content
                            finish_reason = choice.get("finish_reason")

                            if finish_reason is None:
                                text = delta.get("content") or delta.get("reasoning_content") or " "
                                print(text, end="", flush=True)
                                full_response_content += text
                            if finish_reason == "stop" or finish_reason == "tool_calls":
                                print("\r")
                                break
                        except json.JSONDecodeError:
                            # Ignore chunks that are not valid JSON in the stream if needed
                            pass

            final_status_code = response.status_code # Store status code after iteration

        # Check status code after the stream is processed
        if final_status_code and final_status_code >= 400:
            Colors.print_colored(f"Request failed with status code: {final_status_code}", Colors.RED)
            full_buffered_response = "\n".join(response_buffer)
            try:
                # Attempt to parse the entire buffered response as JSON
                error_data = json.loads(full_buffered_response)
                Colors.print_colored(f"Error response JSON: {json.dumps(error_data, indent=2)}", Colors.RED)
            except json.JSONDecodeError:
                # If not JSON, print the raw buffered response
                Colors.print_colored(f"Error response text: {full_buffered_response}", Colors.RED)
            return Message(role="assistant", content=f"Error: Received status code {final_status_code}")

    except requests.RequestException as e:
        # This catches connection errors, etc., before a response is received
        Colors.print_colored(f"Request failed (pre-response): {e}", Colors.RED)
        # Print the full traceback for debugging connection errors
        import traceback
        Colors.print_colored(f"Full traceback: {traceback.format_exc()}", Colors.RED)
        return Message(role="assistant", content=f"Error: {str(e)}")

    # Process tool calls if there are any
    if tool_blocks and use_tool_mode:
        try:
            scheduled = []
            for tool_use_item in tool_blocks:
#                 llt_logger.log_info("Processing tool use block:", {"block": str(tool_use_item)})
                scheduled.append(make_scheduled_from_tool_use(tool_use_item))
            
            # Automatically re-ask the model after tools run
            if scheduled:
                scheduled.append(ScheduledCommand("complete", -1))
#                 llt_logger.log_info("Scheduled re-ask of the model after tool execution.")
                return (messages, scheduled)
        except Exception as e:
            Colors.print_colored(f"Error processing tool use blocks: {str(e)}", Colors.RED)
            llt_logger.log_error("Failed to process tool use blocks.", {"error": str(e)})
            # Fall through to return regular message

    # If no tool use or if tools aren't enabled, return the regular message
    return Message(role="assistant", content=full_response_content)

def get_anthropic_completion(messages: List[Message], args: Dict[str, Any]) -> Any:
    """
    Use the Anthropic python client for streaming completions with tool support.
    """
    try:
        anthropic_client = anthropic.Client()
    except Exception as e:
        llt_logger.log_error("Use tool mode initialization failed: Missing anthropic package.", {"error": str(e)})
        return Message(role="assistant", content=f"Error: {str(e)}")
    
    # Extract system prompt if present (only the first system message, ignore others)
    system_msgs = list(filter(lambda m: m.get("role") == "system", messages))
    system_prompt = system_msgs[0]["content"] if system_msgs else "You are a helpful assistant. You can use tools to assist the user."
    payload_msgs = list(filter(lambda m: m.get("role") != "system", messages))
    
    # Handle image content if present
    for message in payload_msgs:
        if isinstance(message.get("content"), list):
            for content_item in message["content"]:
                if content_item.get("type") == "image" and content_item["source"].get("data", "").startswith("file://"):
                    print(f"Found image in message: {content_item['source']['data']}")
                    pass  # Handle image loading if needed

    response_content = ""
    tool_blocks: List[ToolUseBlock] = []  # Explicitly type tool_blocks
    use_tool_mode = bool(args.get("use_tool", False))
        
    params = {
        "model": args.get('model', "claude-3-7-sonnet-20250219"),
        "system": system_prompt,
        "messages": payload_msgs,
        "temperature": args.get('temperature', 0.7),
    }
    
    if args.get('max_tokens'):
        params["max_tokens"] = args['max_tokens']
    
    # Add tool support if requested
    if use_tool_mode:
#         llt_logger.log_info("Use tool mode enabled. Attempting to use/build tool catalogue.")
        
        global _CACHED_ANTHROPIC_TOOL_CATALOGUE, _CACHED_TOOLS_JSON_MTIME
        
        current_mtime = None
        try:
            if os.path.exists(TOOLS_JSON_PATH):
                current_mtime = os.path.getmtime(TOOLS_JSON_PATH)
            else:
                llt_logger.log_warning(f"Tool definition file {TOOLS_JSON_PATH} not found. Tool schema caching may be affected.")
        except OSError as e:
            llt_logger.log_warning(f"Could not get mtime for {TOOLS_JSON_PATH}: {e}. Tool schema caching may be affected.")

        # Cache validation logic
        if _CACHED_ANTHROPIC_TOOL_CATALOGUE is not None:
            # Case 1: File existed and mtime matches
            if current_mtime is not None and _CACHED_TOOLS_JSON_MTIME is not None and current_mtime == _CACHED_TOOLS_JSON_MTIME:
                llt_logger.log_info("Using cached tool catalogue (version match based on tools.json mtime).")
            # Case 2: File was missing/inaccessible before, and still is. Assume cache is valid for this state.
            elif current_mtime is None and _CACHED_TOOLS_JSON_MTIME is None:
                llt_logger.log_info("Using cached tool catalogue (tool file tools.json still missing/inaccessible).")
            # Case 3: Mismatch (file changed, appeared, or disappeared). Invalidate cache.
            else:
                llt_logger.log_info("Tool definition file tools.json changed, appeared, or disappeared. Regenerating tool catalogue.")
                _CACHED_ANTHROPIC_TOOL_CATALOGUE = None # Invalidate cache
        
        if _CACHED_ANTHROPIC_TOOL_CATALOGUE is None:
            llt_logger.log_info("No valid cached tool catalogue found or cache invalidated. Generating...")
            _CACHED_ANTHROPIC_TOOL_CATALOGUE = registry_to_json_schema()
            _CACHED_TOOLS_JSON_MTIME = current_mtime # Cache the mtime (or None if file was inaccessible)
#             llt_logger.log_info("Tool catalogue generated and cached.")
        
        catalogue = _CACHED_ANTHROPIC_TOOL_CATALOGUE
        params["tools"] = catalogue
        params["tool_choice"] = {"type": "auto"}
    
    try:
        with anthropic_client.messages.stream(**params) as stream:
            for block in stream:
                raw = block.model_dump() if hasattr(block, "model_dump") else block.__dict__
                try:
                    # Validate and parse streaming event
                    event = streaming_adapter.validate_python(raw)
                except ValidationError as e:
                    llt_logger.log_error("Invalid streaming event", {"error": str(e), "raw": raw})
                    continue
                # Dispatch on event type
                if isinstance(event, TextEventModel):
                    print(event.text, end="", flush=True)
                    response_content += event.text
                elif isinstance(event, ContentBlockDeltaModel):
                    # Handle content block delta events (these appear most commonly)
                    delta = event.delta
                    if isinstance(delta, TextDelta):
                        # Print text deltas directly
                        print(delta.text, end="", flush=True)
                        response_content += delta.text
                elif isinstance(event, RawContentBlockStopEventModel):
                    cb = event.content_block
                    if isinstance(cb, ToolUseBlockModel):
                        # Convert Pydantic model back into anthropic.types.ToolUseBlock
                        tool_blocks.append(cast(ToolUseBlock, ToolUseBlock.parse_obj(cb.dict())))
    except Exception as e:
        Colors.print_colored(f"Anthropic API error: {str(e)}", Colors.RED)
        # Print the full traceback for debugging
        import traceback
        Colors.print_colored(f"Full traceback: {traceback.format_exc()}", Colors.RED)
        return Message(role="user", content=f"Error: {str(e)}")
    
    # Check if we have any tool use blocks and need to create scheduled commands
    if tool_blocks:
    
        # Turn tool_use blocks into ScheduledCommand objects
        try:
            scheduled = []
            # Rename loop variable to avoid potential scope collision with 'block' from the stream
            for tool_use_item in tool_blocks: 
                # Since tool_blocks is List[ToolUseBlock], tool_use_item is ToolUseBlock.
                # The getattr check for "type" == "tool_use" is redundant here if the list is correctly populated.
#                 llt_logger.log_info("Processing tool use block:", {"block": str(tool_use_item)})
                # make_scheduled_from_tool_use expects a ToolUseBlock.
                scheduled.append(make_scheduled_from_tool_use(tool_use_item))
            
        except Exception as e:
            Colors.print_colored(f"Error processing tool use blocks: {str(e)}", Colors.RED)
            llt_logger.log_error("Failed to process tool use blocks.", {"error": str(e)})
            return messages
        
        # Automatically re-ask the model after tools run
        if scheduled:
            scheduled.append(ScheduledCommand("complete", -1))
#             llt_logger.log_info("Scheduled re-ask of the model after tool execution.")
            
            return (messages, scheduled)
    
    # If no tool use or if tools aren't enabled, just return the message
    return Message(role="assistant", content=response_content)
    
def get_local_completion(messages: List[Message], args: Dict[str, Any]) -> Message:
    """
    Placeholder for a local LLM or other offline approach.
    """
    return Message(role="assistant", content="TODO: Reintegrate local LLM support. This is a placeholder response.")

@llt()
def encode_images(messages: List[Message], args: Dict[str, Any], index: int = -1) -> List[Message]:
    """
    Encode image URLs into the proper format for different providers.
    Handles both file paths and regular URLs.
    """
    encoded_messages = None
    
    for i, message in enumerate(messages):
        if message.get("role") == "user" and message.get("content") and isinstance(message["content"], list):
            for j, content_item in enumerate(message["content"]):
                if content_item.get("type") == "image_url":
                    image_url = content_item["image_url"]
                    if image_url.startswith("file://") or os.path.exists(image_url):
                        if encoded_messages is None:
                            encoded_messages = json.loads(json.dumps(messages))
                        try:
                            base64_image = file_handler.encode_image_to_base64(
                                image_url.replace("file://", "")
                            )
                            _, ext = os.path.splitext(image_url)
                            if args.get('model', '').startswith("claude"):
                                encoded_messages[i]["content"][j] = {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": f"image/{ext[1:].lower()}",
                                        "data": base64_image
                                    }
                                }
                            else:  # OpenAI format
                                encoded_messages[i]["content"][j] = {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/{ext[1:].lower()};base64,{base64_image}"
                                    }
                                }
                        except Exception as e:
                            Colors.print_colored(f"Error encoding image: {e}", Colors.RED)
                            return messages
                        
    return encoded_messages or messages
                

@llt()
def complete(messages: List[Message], args: Dict, index: int = -1):
    """
    Description: Generate a completion from the LLM
    Type: bool
    Default: false
    flag: complete
    short:
    """
    use_tool_mode = bool(args.get("use_tool", False))
    auto_mode = bool(args.get("auto", False))

    # ------------------------------------------------------------------ #
    # Handle completions with or without tool use                        #
    # ------------------------------------------------------------------ #
    provider, api_key, completion_url = get_provider_details(
        args.get("model", "deepseek-chat")
    )
    
    if use_tool_mode and provider != "anthropic":
        llt_logger.log_error("Use tool mode is only supported with the Anthropic provider.")

    # encode_images handles creating a copy if modifications are needed for image encoding.
    # The original 'messages' list passed to 'complete' should not be mutated directly by encode_images.
    messages_with_images = encode_images(messages, args)

    if provider == "anthropic":
        result = get_anthropic_completion(messages_with_images, args)
        # Check if result is a tuple with (messages, scheduled)
        if isinstance(result, tuple) and len(result) == 2:
            return result  # Return directly if it contains scheduled commands
        completion = result  # Otherwise treat as a normal completion
    elif provider == "local":
        completion = get_local_completion(messages_with_images, args)
    else:
        completion = send_request(completion_url, api_key,
                                  messages_with_images, args)

    # Return a new list with the completion appended
    return messages_with_images + [completion]

@llt()
def mod_cxt(messages: List[Dict[str, Any]], context: Dict[str, Any], index: int = -1) -> List[Dict[str, Any]]:
    """
    Description: Modify configuration arguments
    Type: bool
    Default: false
    flag: mod_cxt
    short: mod
    """

    llt_logger.log_info(f"Context values (pretty printed, well formatted): {json.dumps(context, indent=2)}")
    options = [f"{k} ({type(v).__name__})" for k, v in context.items()]
    selected = input_handler.get_list_input(options, prompt="Select context variable to modify:")
    if not selected:
        return messages

    key = selected.split()[0]
    current = context.get(key)
    llt_logger.log_info(f"Current value of {key}: {current}")
    new_value: Optional[InputValue] = None
    try:
        if isinstance(current, bool):
            new_value = input_handler.get_list_input(["True", "False"]) == "True"
        elif key == "model":
            new_value = input_handler.get_list_input(full_model_choices)
        elif key == "role":
            new_value = input_handler.get_list_input(["user", "assistant", "system", "tool"])
        elif isinstance(current, (int, float)):
            while True:
                val = input_handler.get_input(f"Enter new {type(current).__name__} value")
                try:
                    # Try to cast to the type of current value
                    new = type(current)(val)
                    break
                except ValueError:
                    Colors.print_colored("Invalid value.", Colors.RED)
        else:
            new = input_handler.get_input("Enter new value")

        context[key] = new
        llt_logger.log_info(f"Changed {key} to: {new}")
    except Exception as e:
        Colors.print_colored(f"Error: {e}", Colors.RED)

    return messages


@llt()
def model(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Change the model
    Type: string
    Default: None
    flag: model_change
    short: mo
    """
    new_value = input_handler.get_list_input(full_model_choices)
    if new_value:
        args['model'] = new_value
        Colors.print_colored(f"Changed model to: {new_value}", Colors.GREEN)
    return messages

@llt()
def modify_role(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Modify the role of the message at index
    Type: string
    Default: user
    flag: change_role
    """
    if not args.get('non_interactive') and not args.get('auto'):
        new_value = input_handler.get_list_input(["user", "assistant", "system", "tool"])
    elif args.get('change_role'):
        new_value = args['change_role']
    else:
        # new value is one of available roles except current role
        new_value = next(iter(set(["user", "assistant", "system", "tool"]) - {messages[index]["role"]}))
    
    if new_value:
        messages[index]["role"] = new_value
        if not args.get('non_interactive'):
            Colors.print_colored(f"Changed role of message at index {index} to: {new_value}", Colors.GREEN)
    
    return messages

@llt()
def change_role(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Set the current role
    Type: string
    Default: user
    flag: role_change
    short: ro
    """
    roles = ["user", "assistant", "system", "tool"]
    if args.get("non_interactive"):
        new_role = args["role"]
    else:
        new_role = input_handler.get_list_input(roles, prompt="Select role:")
        if not new_role:
            return messages

    args["role"] = new_role
    Colors.print_colored(f"Set default role to: {new_role}", Colors.GREEN)
    return messages