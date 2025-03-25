import os
import json
from typing import Dict, Any, List
from dotenv import load_dotenv
import litellm
from litellm import acompletion

from tools import toolset


def load_config():
    """Load the configuration from environment variables"""
    load_dotenv()
    
    # Get API key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables")
    
    # LiteLLM configuration
    model = "groq/llama-3.3-70b-versatile"
    
    return {
        "api_key": api_key,
        "model": model
    }


async def send_message(message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Send a message to the LLM and get the response"""
    config = load_config()
    
    # Add the current message to history
    history.append({"role": "user", "content": message})
    
    # Build messages for the LLM
    messages = history
    
    # Get tool descriptions for LiteLLM
    tools = toolset.get_descriptions()
    
    # Call the LLM
    response = await acompletion(
        model=config["model"],
        messages=messages,
        tools=tools,
        api_key=config["api_key"],
        tool_choice="auto",
    )
    
    return response


def execute_tool_call(tool_call: Dict[str, Any]) -> Any:
    """Execute a tool call from the LLM response"""
    # Parse the function name and arguments
    function_name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])
    
    # Find the tool by name
    tool = toolset.get_tool_by_name(function_name)
    if not tool:
        raise ValueError(f"Tool '{function_name}' not found")
    
    # Execute the tool
    return tool.execute(**arguments)


async def chat_loop():
    """Run the chat loop to interact with the LLM"""
    print("Welcome to the AI Task & Goal Tracker!")
    print("Type 'quit' or 'exit' to end the session.")
    print()
    
    # Initialize conversation history
    history = [
        {
            "role": "system",
            "content": (
                "You are an AI assistant for task and goal tracking. "
                "You can help users manage their tasks and goals, create recurring tasks, "
                "and track their progress. Use the available tools to perform operations "
                "on tasks, goals, and templates."
            )
        }
    ]
    
    while True:
        # Get user input
        user_input = input("> ")
        if user_input.lower() in ("quit", "exit"):
            break
        
        try:
            # Send message to LLM
            response = await send_message(user_input, history)
            
            # Get assistant message
            assistant_message = response.choices[0].message
            
            # Add to history
            history.append({"role": "assistant", "content": assistant_message.get("content", "")})
            
            # Process tool calls
            tool_calls = assistant_message.get("tool_calls", [])
            if tool_calls:
                for tool_call in tool_calls:
                    # Execute the tool
                    result = execute_tool_call(tool_call)
                    
                    # Add tool result to history
                    history.append({
                        "role": "tool", 
                        "tool_call_id": tool_call["id"],
                        "name": tool_call["function"]["name"],
                        "content": json.dumps(result, default=str)
                    })
                
                # Get LLM's final response after tool calls
                final_response = await send_message("", history)
                assistant_message = final_response.choices[0].message
                
                # Update the last assistant message in history
                history[-1] = {"role": "assistant", "content": assistant_message.get("content", "")}
            
            # Display the assistant's response
            print(assistant_message.get("content", ""))
            
        except Exception as e:
            print(f"Error: {str(e)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(chat_loop())