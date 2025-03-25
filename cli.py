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


async def send_message(messages: List[Dict[str, Any]], tools_enabled=True) -> Dict[str, Any]:
    """Send messages to the LLM and get the response"""
    config = load_config()
    
    # Get tool descriptions for LiteLLM
    tools = toolset.get_descriptions() if tools_enabled else None
    tool_choice = "auto" if tools_enabled else "none"
    
    # Call the LLM
    response = await acompletion(
        model=config["model"],
        messages=messages,
        tools=tools,
        api_key=config["api_key"],
        tool_choice=tool_choice,
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
                "on tasks, goals, and templates. "
                "Always provide helpful, detailed responses. After using a tool, summarize what you found."
            )
        }
    ]
    
    while True:
        # Get user input
        user_input = input("> ")
        if user_input.lower() in ("quit", "exit"):
            break
        
        try:
            # Add user message to history
            history.append({"role": "user", "content": user_input})
            
            # Send all messages to LLM
            response = await send_message(history)
            
            # Get assistant message
            assistant_message = response.choices[0].message
            content = assistant_message.get("content", "")
            
            # Check for tool calls
            tool_calls = assistant_message.get("tool_calls", [])
            
            if tool_calls:
                print("Executing tools...")
                
                # Store tool results for later use
                tool_results = []
                
                # Process each tool call
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    print(f"- Executing: {tool_name}")
                    
                    # Execute the tool
                    try:
                        result = execute_tool_call(tool_call)
                        # Convert result to string representation for display
                        result_display = str(result)
                        print(f"Result: {result_display[:150]}{'...' if len(result_display) > 150 else ''}")
                        tool_results.append((tool_name, result))
                    except Exception as e:
                        print(f"Tool error: {str(e)}")
                        tool_results.append((tool_name, f"Error: {str(e)}"))
                
                # Create a new history for the follow-up
                followup_history = history.copy()
                
                # Add a summary of tool results as a user message
                tool_summary = "I've executed the tools you requested:\n\n"
                for name, result in tool_results:
                    tool_summary += f"Tool '{name}' returned: {json.dumps(result, default=str)}\n\n"
                tool_summary += "Please summarize these results in a helpful way."
                
                followup_history.append({"role": "user", "content": tool_summary})
                
                # Get the final response without tools
                print("Getting final response...")
                final_response = await send_message(followup_history, tools_enabled=False)
                final_content = final_response.choices[0].message.get("content", "")
                
                if not final_content or final_content.strip() == "None":
                    final_content = "I found some information for you, but I'm having trouble summarizing it."
                
                # Update the main history with a simplified version
                history.append({"role": "assistant", "content": final_content})
                
                print(final_content)
                
            else:
                # No tool calls, just add response to history and display it
                history.append({"role": "assistant", "content": content})
                print(content)
            
        except Exception as e:
            print(f"Error: {str(e)}")
            # Optionally print the full traceback for debugging
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(chat_loop())