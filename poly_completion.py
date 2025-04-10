# poly_completion.py
import litellm
import json
import re
import copy
import uuid
from typing import List, Dict, Any, Optional

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
        # Add handling for other tool types if necessary in the future
        
    return "Available Tools:\n" + "\n".join(formatted_tools)

def _generate_tool_prompt(tools: List[Dict[str, Any]]) -> str:
    """Generates the instruction prompt for tool usage."""
    tool_description = _format_tools_for_prompt(tools)
    
    instruction = """
You have access to the following tools:
{tool_description}

If you need to use a tool to answer the user's request, follow these instructions *exactly*:
1.  First, think step-by-step about whether you need to call a tool. You can use <think>...</think> blocks for your reasoning. These blocks will be ignored.
2.  If you decide to call one or more tools, output *each* function call as a standard JSON object on its own line. The JSON object *must* have a "name" key and an "arguments" key.
    Example of a line containing a function call:
    {{"name": "tool_name", "arguments": {{"arg1": "value1", "arg2": "value2"}}}}
3.  Do *not* include any other text, explanations, or narrative outside the JSON lines if you are making tool calls.
4.  If you do not need to use a tool, respond to the user naturally without outputting any JSON tool calls.
""".format(tool_description=tool_description)
    return instruction.strip()

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
                # Check if it looks like a valid tool call structure
                if isinstance(parsed_json, dict) and "name" in parsed_json and "arguments" in parsed_json:
                     # Ensure arguments is a dict, even if empty
                     args = parsed_json.get("arguments")
                     if args is None:
                        args = {}
                     elif not isinstance(args, dict):
                         # Attempt to handle if arguments are accidentally stringified JSON
                         try:
                             args = json.loads(args) if isinstance(args, str) else args
                             if not isinstance(args, dict): # Reset if still not a dict
                                args = {}
                         except json.JSONDecodeError:
                             args = {} # Give up if string is not valid JSON

                     tool_call_id = f"call_{uuid.uuid4()}"
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
                # Ignore lines that look like JSON but fail to parse
                # Consider adding logging here if needed: logging.warning(...)
                print(f"Warning: Failed to parse potential JSON tool call: {trimmed_line}") 
                continue
                
    return tool_calls

# ---- Main Completion Function ----

def completion(*args, **kwargs) -> litellm.ModelResponse:
    """
    Acts as a drop-in replacement for litellm.completion, adding tool calling
    support via prompt engineering for models that don't natively support it,
    using litellm.supports_function_calling() for detection.

    Args:
        *args: Positional arguments intended for litellm.completion.
        **kwargs: Keyword arguments intended for litellm.completion (e.g., model,
                  messages, tools, tool_choice, max_tokens, temperature, etc.).

    Returns:
        litellm.ModelResponse: A response object mimicking litellm's output,
                                potentially including parsed 'tool_calls'.
    """
    model = kwargs.get("model")
    messages = kwargs.get("messages")
    tools = kwargs.get("tools")
    # tool_choice = kwargs.get("tool_choice") # Captured but ignored in fallback

    # Ensure essential arguments are present
    if not model or not messages:
        return litellm.completion(*args, **kwargs)

    use_native_tools = litellm.supports_function_calling(model) and tools

    if use_native_tools:
        # Model supports tools natively, and tools are provided. Pass through directly.
        print(f"Info: Using native tool support for model '{model}'.")
        return litellm.completion(*args, **kwargs)
    
    elif tools:
        # Model does *not* support native tools according to litellm, but tools *are* provided.
        # We need to inject the prompt and parse the output.
        print(f"Info: Using prompt engineering for tool support with model '{model}'.")
        
        call_kwargs = copy.deepcopy(kwargs)
        original_messages = call_kwargs["messages"]
        
        tool_prompt = _generate_tool_prompt(tools)
        
        modified_messages = copy.deepcopy(original_messages)
        modified_messages.append({"role": "user", "content": tool_prompt})
        call_kwargs["messages"] = modified_messages
        
        if "tools" in call_kwargs:
            del call_kwargs["tools"]
        if "tool_choice" in call_kwargs:
            print("Warning: 'tool_choice' is ignored when using prompt-engineered tools.")
            del call_kwargs["tool_choice"]

        # Make the call to the underlying litellm.completion
        response: litellm.ModelResponse = litellm.completion(*args, **call_kwargs)

        # Parse the response content for tool calls
        response_content = None
        if response.choices and response.choices[0].message:
           response_content = response.choices[0].message.content

        parsed_tool_calls = _parse_tool_calls_from_content(response_content)

        # Construct the final response object
        if parsed_tool_calls:
            original_choice = response.choices[0] if response.choices else litellm.utils.Choices(finish_reason="stop", index=0, message=litellm.utils.Message(content=None, role='assistant'))
            
            new_message = litellm.utils.Message(
                content=None, 
                role=original_choice.message.role if original_choice.message else 'assistant',
                tool_calls=parsed_tool_calls
            )
            
            new_choice = litellm.utils.Choices(
                finish_reason="tool_calls", 
                index=original_choice.index,
                message=new_message
            )
            
            final_response = litellm.ModelResponse(
                id=response.id,
                choices=[new_choice],
                created=response.created,
                model=response.model, 
                object="chat.completion", 
                system_fingerprint=response.system_fingerprint,
                usage=response.usage, 
                _response_ms=getattr(response,'_response_ms', 0)
            )
            if hasattr(response, '_hidden_params'):
                 final_response._hidden_params = response._hidden_params # type: ignore
            
            return final_response
        else:
            # No tool calls parsed, return the original response as is.
            if response.choices and response.choices[0].finish_reason == "tool_calls":
                 response.choices[0].finish_reason = "stop" 
            return response
            
    else:
        # No tools were provided in the first place, just pass through.
        return litellm.completion(*args, **kwargs)