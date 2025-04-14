# poly_completion.py
import litellm
import json
import re
import copy
import uuid
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("poly_completion")

# ---- Helper Functions ----

def _format_tools_for_prompt(tools: List[Dict[str, Any]]) -> str:
    """Formats tool descriptions for inclusion in a prompt."""
    if not tools:
        return "No tools available."

    formatted_tools = []
    for tool in tools:
        if tool.get("type") == "function":
            function_spec = tool.get("function", {})
            name = function_spec.get("name", "Unnamed function")
            description = function_spec.get("description", "No description.")
            parameters = function_spec.get("parameters", {})
            
            # Basic representation of parameters
            param_desc = "Parameters: None"
            if parameters and parameters.get('properties'):
                 param_list = [f"{k} ({v.get('type', 'any')})" for k, v in parameters['properties'].items()]
                 param_desc = f"Parameters: {', '.join(param_list)}"
                 required = parameters.get('required')
                 if required:
                    param_desc += f" (Required: {', '.join(required)})"

            formatted_tools.append(f"- Function: {name}\n  Description: {description}\n  {param_desc}")
        
    return "Available Tools:\n" + "\n".join(formatted_tools)

def _generate_tool_prompt(tools: List[Dict[str, Any]], recent_tool_usage: bool = False) -> str:
    """
    Generates the instruction prompt for tool usage.
    
    Args:
        tools: List of tool definitions
        recent_tool_usage: If True, modifies the prompt to discourage repeated tool calls
    """
    tool_description = _format_tools_for_prompt(tools)
    
    # Base instruction template
    instruction = """
You have access to the following tools:
{tool_description}

If you need to use a tool to answer the user's request, follow these instructions *exactly*:
1.  First, think step-by-step about whether you need to call a tool. You can use <think>...</think> blocks for your reasoning. These blocks will be ignored.
2.  If you decide to call one or more tools, output *each* function call as a standard JSON object on its own line. The JSON object *must* have a "name" key and an "arguments" key (if arguments are needed).
    Example with arguments:
    {{"name": "tool_name", "arguments": {{"arg1": "value1", "arg2": "value2"}}}}
    Example without arguments:
    {{"name": "tool_name"}}
3.  DO NOT wrap your tool calls in code blocks with triple backticks. Just output the raw JSON objects.
4.  Do *not* include any other text, explanations, or narrative outside the JSON lines if you are making tool calls.
5.  If you do not need to use a tool, respond to the user naturally without outputting any JSON tool calls.
"""

    # If there's been recent tool usage, add guidance to avoid unnecessary repeated calls
    if recent_tool_usage:
        instruction += """
IMPORTANT: I notice you've already used tools recently in this conversation. Before calling another tool:
- Check if you already have the information you need from previous tool calls
- Only call a tool if you need NEW information that wasn't provided by previous tool calls
- If you have sufficient information, please respond directly to the user without making additional tool calls
"""

    return instruction.format(tool_description=tool_description).strip()

def _parse_tool_calls_from_content(content: Optional[str]) -> List[Dict[str, Any]]:
    """Parses tool call JSON from the model's text response."""
    tool_calls = []
    if not content:
        return tool_calls

    # 1. Remove <think> blocks first
    cleaned_content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)

    # 2. Iterate through lines and look for JSON
    lines = cleaned_content.strip().splitlines()
    for line in lines:
        trimmed_line = line.strip()
        # Basic check: does it look like a JSON object on a single line?
        if trimmed_line.startswith("{") and trimmed_line.endswith("}"):
            try:
                parsed_json = json.loads(trimmed_line)
                # Check if it has a "name" key (required for tool calls)
                if isinstance(parsed_json, dict) and "name" in parsed_json:
                    # Handle the arguments - may be missing entirely
                    args = {}
                    if "arguments" in parsed_json:
                        args = parsed_json["arguments"]
                        # Handle if arguments are provided as a string
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                                if not isinstance(args, dict):
                                    args = {}
                            except json.JSONDecodeError:
                                args = {}
                    
                    # Generate a unique ID for this tool call
                    tool_call_id = f"call_{uuid.uuid4()}"
                    
                    # Create the tool call structure
                    tool_calls.append({
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": parsed_json["name"],
                            # Arguments in the final litellm structure must be a JSON *string*
                            "arguments": json.dumps(args) 
                        }
                    })
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse potential JSON tool call: {trimmed_line}")
                continue
                
    return tool_calls

def _has_recent_tool_calls(messages: List[Dict[str, Any]], window: int = 4) -> bool:
    """
    Check if there are tool calls in the recent message history.
    
    Args:
        messages: The message history
        window: Number of recent messages to check
        
    Returns:
        True if there are tool calls in the recent history
    """
    # Check the most recent messages (limited by window size)
    recent_msgs = messages[-window:] if len(messages) > window else messages
    
    # Look for assistant messages with tool_calls or tool messages
    for msg in recent_msgs:
        role = msg.get("role", "")
        if (role == "assistant" and msg.get("tool_calls")) or role == "tool":
            return True
            
    return False

def _find_tool_responses(messages: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Find all tool responses in the message history and organize them by tool_call_id.
    Returns a dict mapping tool_call_id to a dict with tool name and response content.
    """
    tool_responses = {}
    
    # First identify all assistant messages with tool calls
    tool_calls_by_id = {}
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tool_call in msg["tool_calls"]:
                if "id" in tool_call and "function" in tool_call and "name" in tool_call["function"]:
                    tool_id = tool_call["id"]
                    tool_name = tool_call["function"]["name"]
                    tool_calls_by_id[tool_id] = {
                        "name": tool_name,
                        "message_index": i
                    }
    
    # Then find all tool responses
    for msg in messages:
        if msg.get("role") == "tool" and "tool_call_id" in msg and "content" in msg:
            tool_id = msg["tool_call_id"]
            if tool_id in tool_calls_by_id:
                # Parse the content if it's JSON
                content = msg["content"]
                try:
                    # Try to parse as JSON first
                    parsed_content = json.loads(content)
                    tool_responses[tool_id] = {
                        "name": tool_calls_by_id[tool_id]["name"],
                        "content": parsed_content
                    }
                except (json.JSONDecodeError, TypeError):
                    # If not valid JSON, use as is
                    tool_responses[tool_id] = {
                        "name": tool_calls_by_id[tool_id]["name"],
                        "content": content
                    }
    
    return tool_responses

def _find_recent_tool_calls(messages: List[Dict[str, Any]], max_lookback: int = 10) -> List[Dict[str, Any]]:
    """
    Extract recent tool calls from message history to avoid repetition.
    
    Args:
        messages: The message history
        max_lookback: Maximum number of messages to look back
        
    Returns:
        List of recent tool call names and their arguments
    """
    recent_calls = []
    
    # Look at recent messages only
    recent_msgs = messages[-max_lookback:] if len(messages) > max_lookback else messages
    
    for msg in recent_msgs:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tool_call in msg["tool_calls"]:
                if "function" in tool_call and "name" in tool_call["function"]:
                    name = tool_call["function"]["name"]
                    args = {}
                    if "arguments" in tool_call["function"]:
                        try:
                            args = json.loads(tool_call["function"]["arguments"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    
                    recent_calls.append({
                        "name": name,
                        "arguments": args
                    })
    
    return recent_calls

def _sanitize_messages(messages: List[Dict[str, Any]], add_tool_reminder: bool = False) -> List[Dict[str, Any]]:
    """
    Prepare messages for models that don't support tool calling by converting
    tool responses to text that can be included in message content.
    
    Args:
        messages: Original message history
        add_tool_reminder: If True, adds a reminder about previous tool calls
        
    Returns:
        Sanitized messages suitable for a model without native tool calling
    """
    # Find all tool responses first
    tool_responses = _find_tool_responses(messages)
    
    # Extract recent tool calls to avoid repetition
    recent_tool_calls = _find_recent_tool_calls(messages)
    
    # Process messages to include tool responses as text
    sanitized_messages = []
    skip_indices = set()
    
    for i, msg in enumerate(messages):
        # Skip messages that should be skipped (like tool messages)
        if i in skip_indices:
            continue
            
        # Process based on message role
        role = msg.get("role", "")
        
        if role == "tool":
            # Skip tool messages - their content will be included elsewhere
            skip_indices.add(i)
            continue
            
        elif role == "assistant":
            # Create a copy with just role and content initially
            new_msg = {"role": "assistant"}
            
            # Copy the content if it exists
            if "content" in msg and msg["content"] is not None:
                new_msg["content"] = msg["content"]
            else:
                new_msg["content"] = ""
                
            # If this message has tool calls, add tool results as additional info
            if msg.get("tool_calls"):
                tool_results_text = []
                
                for tool_call in msg.get("tool_calls", []):
                    tool_id = tool_call.get("id")
                    if tool_id in tool_responses:
                        tool_info = tool_responses[tool_id]
                        tool_name = tool_info["name"]
                        tool_result = tool_info["content"]
                        result_text = f"Tool '{tool_name}' returned: {json.dumps(tool_result, default=str)}"
                        tool_results_text.append(result_text)
                
                # Add tool results to content if there are any
                if tool_results_text:
                    # Only add if the content doesn't already include these results
                    if not any(result in new_msg["content"] for result in tool_results_text):
                        # Add a separator if needed
                        if new_msg["content"] and not new_msg["content"].endswith("\n\n"):
                            new_msg["content"] += "\n\n"
                        elif not new_msg["content"]:
                            new_msg["content"] = "I need to look up some information for you.\n\n"
                            
                        new_msg["content"] += "\n".join(tool_results_text)
            
            sanitized_messages.append(new_msg)
            
        else:
            # For user and system messages, just copy as is
            new_msg = {"role": role}
            if "content" in msg:
                new_msg["content"] = msg["content"]
            sanitized_messages.append(new_msg)
    
    # If requested and there are recent tool calls, add a reminder about them
    if add_tool_reminder and recent_tool_calls:
        # Only add reminder if the last message isn't already a tool reminder
        last_msg = sanitized_messages[-1] if sanitized_messages else {}
        if not (last_msg.get("role") == "user" and "recently used tools" in last_msg.get("content", "")):
            tool_names = [call["name"] for call in recent_tool_calls]
            unique_names = list(set(tool_names))
            
            reminder = {
                "role": "user",
                "content": f"Note: You've recently used tools: {', '.join(unique_names)}. Please use the information already gathered when possible instead of calling the same tools again with the same parameters."
            }
            sanitized_messages.append(reminder)
    
    return sanitized_messages

# ---- Main Completion Function ----

def completion(*args, **kwargs) -> litellm.ModelResponse:
    """
    Acts as a drop-in replacement for litellm.completion, adding tool calling
    support via prompt engineering for models that don't natively support it.

    Args:
        *args: Positional arguments intended for litellm.completion.
        **kwargs: Keyword arguments intended for litellm.completion (e.g., model,
                  messages, tools, tool_choice, max_tokens, temperature, etc.).

    Returns:
        litellm.ModelResponse: A response object mimicking litellm's output,
                                potentially including parsed 'tool_calls'.
    """
    model = kwargs.get("model")
    messages = kwargs.get("messages", [])
    tools = kwargs.get("tools")
    
    # Ensure essential arguments are present
    if not model or not messages:
        return litellm.completion(*args, **kwargs)

    # Check if the model supports native tool calling
    use_native_tools = litellm.supports_function_calling(model) and tools

    if use_native_tools:
        # Model supports tools natively, pass through directly
        logger.info(f"Using native tool support for model '{model}'")
        return litellm.completion(*args, **kwargs)
    
    elif tools:
        # Model doesn't support native tools, use prompt engineering
        logger.info(f"Using prompt engineering for tool support with model '{model}'")
        
        # Create a clean copy of kwargs to modify
        call_kwargs = copy.deepcopy(kwargs)
        
        # Check if there's been recent tool usage
        has_recent_tools = _has_recent_tool_calls(messages)
        
        # Sanitize messages to prepare for non-tool-supporting model
        # Add tool reminder if there's been recent tool usage
        sanitized_messages = _sanitize_messages(messages, add_tool_reminder=has_recent_tools)
        
        # Generate the tool instruction prompt, modified if there's been recent tool usage
        tool_prompt = _generate_tool_prompt(tools, recent_tool_usage=has_recent_tools)
        
        # Add the tool prompt as the final user message
        modified_messages = sanitized_messages.copy()
        modified_messages.append({"role": "user", "content": tool_prompt})
        call_kwargs["messages"] = modified_messages
        
        # Remove tool-related parameters
        if "tools" in call_kwargs:
            del call_kwargs["tools"]
        if "tool_choice" in call_kwargs:
            logger.warning("'tool_choice' is ignored when using prompt-engineered tools")
            del call_kwargs["tool_choice"]

        # Make the underlying LiteLLM call
        try:
            response = litellm.completion(*args, **call_kwargs)
        except Exception as e:
            logger.error(f"Error during LiteLLM completion: {str(e)}")
            raise

        # Extract and parse the response content
        response_content = None
        if response.choices and response.choices[0].message:
            response_content = response.choices[0].message.content

        logger.debug(f"Raw response content: {response_content}")
        
        # Parse tool calls from the text response
        parsed_tool_calls = _parse_tool_calls_from_content(response_content)
        logger.debug(f"Parsed tool calls: {parsed_tool_calls}")
            
        # Construct the final response with tool calls if found
        if parsed_tool_calls:
            original_choice = response.choices[0] if response.choices else litellm.utils.Choices(
                finish_reason="stop", 
                index=0, 
                message=litellm.utils.Message(content=None, role='assistant')
            )
            
            # Create a new message with tool_calls
            new_message = litellm.utils.Message(
                content=None, 
                role=original_choice.message.role if original_choice.message else 'assistant',
                tool_calls=parsed_tool_calls
            )
            
            # Create a new choice
            new_choice = litellm.utils.Choices(
                finish_reason="tool_calls", 
                index=original_choice.index,
                message=new_message
            )
            
            # Create a new response
            final_response = litellm.ModelResponse(
                id=response.id,
                choices=[new_choice],
                created=response.created,
                model=response.model, 
                object="chat.completion", 
                system_fingerprint=response.system_fingerprint,
                usage=response.usage, 
                _response_ms=getattr(response, '_response_ms', 0)
            )
            
            # Preserve hidden params if they exist
            if hasattr(response, '_hidden_params'):
                final_response._hidden_params = response._hidden_params
            
            return final_response
        else:
            # No tool calls found, return the original response
            if response.choices and response.choices[0].finish_reason == "tool_calls":
                response.choices[0].finish_reason = "stop" 
            return response
            
    else:
        # No tools provided, pass through to LiteLLM directly
        return litellm.completion(*args, **kwargs)