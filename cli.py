import os
import json
from typing import Dict, Any, List
from dotenv import load_dotenv
import litellm
from litellm import acompletion

from tools import toolset


# ANSI color codes for CLI output formatting
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


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


def print_formatted_tool_call(tool_call: Dict[str, Any]):
    """Print a formatted representation of a tool call with colors"""
    function_name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])
    
    print(f"{Colors.BOLD}{Colors.CYAN}[TOOL CALL] {function_name}{Colors.RESET}")
    print(f"{Colors.CYAN}Arguments: {Colors.RESET}")
    
    # Format the arguments nicely
    formatted_args = json.dumps(arguments, indent=2, default=str)
    # Add indentation and color to each line
    formatted_args = "\n".join(f"  {Colors.CYAN}{line}{Colors.RESET}" for line in formatted_args.split("\n"))
    print(formatted_args)


def print_formatted_tool_result(tool_name: str, result: Any):
    """Print a formatted representation of a tool result with colors"""
    result_str = json.dumps(result, default=str, indent=2)
    print(f"{Colors.BOLD}{Colors.GREEN}[TOOL RESULT] {tool_name}{Colors.RESET}")
    
    # Format the result with indentation and color
    formatted_result = "\n".join(f"  {Colors.GREEN}{line}{Colors.RESET}" for line in result_str.split("\n"))
    print(formatted_result)


async def chat_loop():
    """Run the chat loop to interact with the LLM"""
    print(f"{Colors.BOLD}Welcome to the AI Task & Goal Tracker!{Colors.RESET}")
    print("Type 'quit' or 'exit' to end the session.")
    print()
    
    # Initialize conversation history with current date and time info
    from datetime import datetime
    current_time = datetime.now()
    formatted_date = current_time.strftime("%A, %B %d, %Y")  # Full day of week, month name, day, year
    formatted_time = current_time.strftime("%I:%M %p")
    
    history = [
        {
            "role": "system",
            "content": (
                f"You are an AI assistant for task and goal tracking. Today is {formatted_date} and the current time is {formatted_time}. "
                "You can help users manage their tasks and goals, create recurring tasks, "
                "and track their progress. Use the available tools to perform operations "
                "on tasks, goals, and templates ONLY when the user's request requires them. "
                "Do not use tools for general conversation or questions unrelated to task management. "
                "For example, if a user asks about the time, weather, or says hello, just respond normally without calling a tool. "
                "Only use tools when explicitly needed to fulfill a request about goals, tasks, or templates. "
                "Always provide helpful, CONCISE responses. After using a tool, summarize what you found briefly."
            )
        }
    ]
    
    while True:
        # Get user input
        user_input = input(f"{Colors.BOLD}> {Colors.RESET}")
        if user_input.lower() in ("quit", "exit"):
            break
            
        # Add option to reset conversation history
        if user_input.lower() == "reset":
            print(f"{Colors.YELLOW}Resetting conversation history...{Colors.RESET}")
            history = [history[0]]  # Keep only the system message
            continue
        
        try:
            # Add user message to history
            history.append({"role": "user", "content": user_input})
            
            print(f"{Colors.YELLOW}Sending request to LLM...{Colors.RESET}")
            
            # Send all messages to LLM
            response = await send_message(history)
            
            # Get assistant message
            assistant_message = response.choices[0].message
            content = assistant_message.get("content", "")
            
            # Check for tool calls
            tool_calls = assistant_message.get("tool_calls", [])
            
            if tool_calls:
                print(f"\n{Colors.BOLD}{Colors.MAGENTA}LLM requested {len(tool_calls)} tool call(s){Colors.RESET}")
                
                # Store tool results for later use
                tool_results = []
                
                # Process each tool call
                for tool_call in tool_calls:
                    # Print formatted tool call
                    print_formatted_tool_call(tool_call)
                    
                    # Execute the tool
                    tool_name = tool_call["function"]["name"]
                    try:
                        result = execute_tool_call(tool_call)
                        # Print formatted tool result
                        print_formatted_tool_result(tool_name, result)
                        tool_results.append((tool_name, result))
                    except Exception as e:
                        error_message = str(e)
                        print(f"{Colors.RED}Tool error: {error_message}{Colors.RESET}")
                        tool_results.append((tool_name, f"Error: {error_message}"))
                
                # Create a new history for the follow-up
                followup_history = history.copy()
                
                # Add a summary of tool results as a user message
                tool_summary = "I've executed the tools you requested:\n\n"
                for name, result in tool_results:
                    tool_summary += f"Tool '{name}' returned: {json.dumps(result, default=str)}\n\n"
                tool_summary += "Please summarize these results in a helpful way."
                
                followup_history.append({"role": "user", "content": tool_summary})
                
                print(f"\n{Colors.YELLOW}Getting final response...{Colors.RESET}")
                final_response = await send_message(followup_history, tools_enabled=False)
                final_content = final_response.choices[0].message.get("content", "")
                
                if not final_content or final_content.strip() == "None":
                    final_content = "I found some information for you, but I'm having trouble summarizing it."
                
                # Update the main history with a simplified version
                history.append({"role": "assistant", "content": final_content})
                
                print(f"\n{Colors.RESET}{final_content}")
                
            else:
                # No tool calls, just add response to history and display it
                history.append({"role": "assistant", "content": content})
                print(f"\n{content}")
            
        except Exception as e:
            print(f"\n{Colors.RED}Error: {str(e)}{Colors.RESET}")
            # Optionally print the full traceback for debugging
            import traceback
            traceback.print_exc()


def check_color_support():
    """Check if the terminal supports colors and disable if necessary"""
    # Check for NO_COLOR environment variable (https://no-color.org/)
    if os.getenv("NO_COLOR") is not None:
        for attr in dir(Colors):
            if not attr.startswith("__"):
                setattr(Colors, attr, "")
        return
    
    # Check for Windows and enable VT100 if possible
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            # If enabling VT100 fails, disable colors
            for attr in dir(Colors):
                if not attr.startswith("__"):
                    setattr(Colors, attr, "")


if __name__ == "__main__":
    import asyncio
    check_color_support()
    asyncio.run(chat_loop())