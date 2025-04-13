import os
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import asyncio
import uuid
from datetime import datetime
from sqlmodel import select, Session

# Import our poly_completion instead of litellm
from poly_completion import completion

from tools import toolset
from database import engine, create_db_and_tables
from models import Note, NoteType


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
    deepinfra_api_key = os.getenv("DEEPINFRA_API_KEY")
    if not deepinfra_api_key:
        raise ValueError("DEEPINFRA_API_KEY not found in environment variables")
    
    # Model configuration
    model = "deepinfra/google/gemma-3-27b-it"
    
    return {
        "api_key": deepinfra_api_key,
        "model": model
    }


async def send_message(messages: List[Dict[str, Any]], tools_enabled=True) -> Dict[str, Any]:
    """Send messages to the LLM and get the response"""
    config = load_config()
    
    # Get tool descriptions for LiteLLM
    tools = toolset.get_descriptions() if tools_enabled else None
    tool_choice = "auto" if tools_enabled else "none"
    
    # Call the LLM using poly_completion instead of litellm directly
    response = await asyncio.to_thread(
        completion,
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
    # Handle SQLModel objects for JSON serialization
    if hasattr(result, "model_dump"):
        result_dict = result.model_dump()
    else:
        # Convert to dict using SQLModel's dict() method if available
        result_dict = result.dict() if hasattr(result, "dict") else result
        
    result_str = json.dumps(result_dict, default=str, indent=2)
    print(f"{Colors.BOLD}{Colors.GREEN}[TOOL RESULT] {tool_name}{Colors.RESET}")
    
    # Format the result with indentation and color
    formatted_result = "\n".join(f"  {Colors.GREEN}{line}{Colors.RESET}" for line in result_str.split("\n"))
    print(formatted_result)


def get_system_notes() -> str:
    """Retrieve notes that should be included in the system prompt"""
    with Session(engine) as session:
        query = select(Note).where(Note.is_system_prompt == True)
        system_notes = session.exec(query).all()
        
        if not system_notes:
            return ""
            
        notes_text = "\n\nUSER NOTES AND PREFERENCES:\n"
        for note in system_notes:
            notes_text += f"- {note.title}: {note.content}\n"
            
        return notes_text


async def chat_loop():
    """Run the chat loop to interact with the LLM"""
    print(f"{Colors.BOLD}Welcome to the AI Task & Goal Tracker!{Colors.RESET}")
    print("Type 'quit' or 'exit' to end the session.")
    print()
    
    # Initialize the database
    create_db_and_tables()
    
    # Initialize conversation history with current date and time info
    current_time = datetime.now()
    formatted_date = current_time.strftime("%A, %B %d, %Y")  # Full day of week, month name, day, year
    formatted_time = current_time.strftime("%I:%M %p")
    
    # Get user notes for system prompt
    user_notes = get_system_notes()
    
    # Create enhanced system prompt
    system_prompt = (
        f"You are an AI assistant for task and goal tracking. Today is {formatted_date} and the current time is {formatted_time}. "
        "You can help users manage their tasks and goals, create recurring tasks, and track their progress.\n\n"
        
        "TOOL USAGE GUIDELINES:\n"
        "1. Use READ-ONLY tools (list_goals, list_tasks, get_goal, get_task, list_notes, get_note) freely to retrieve information and be helpful.\n"
        "2. For tools that MODIFY data (create_*, update_*, delete_*, complete_task), ASK FOR CONFIRMATION before executing unless the user explicitly requested the action.\n"
        "3. Be proactive in checking available information to give better recommendations.\n"
        "4. ALWAYS DISPLAY PARAMETER VALUES FOR CONFIRMATION before executing tools that modify data.\n\n"
        
        "WORKING WITH ENTITIES:\n"
        "1. Tasks have different states (incomplete, completed, abandoned, missed) and priorities (low, medium, high, urgent).\n"
        "2. Goals have hierarchical structure through the parent_goal_id field.\n"
        "3. Tasks can be linked to multiple goals, and can depend on other tasks.\n"
        "4. Always check if entities exist before attempting to create relationships between them.\n"
        "5. Present users with options from existing data whenever possible.\n"
        "6. Whenever creating a task, SUGGEST linking it to at least one goal. Tasks should ideally support a higher-level goal.\n\n"
        
        "RECURRING TASK MANAGEMENT:\n"
        "1. Task with an 'rrule' field is a template that generates recurring instances.\n"
        "2. Tasks with 'rrule_template_id' are instances created from a template.\n"
        "3. When updating recurring tasks, always confirm if the user wants to:\n"
        "   - Update just the specific instance (update_all_recurring_after=false)\n"
        "   - Update the template and all future instances (update_all_recurring_after=true)\n"
        "4. Be clear about which option you're using and why.\n\n"
        
        "WHEN CALLING TOOLS:\n"
        "1. ONLY include parameters that have actual values - DO NOT pass explicit 'null' or 'None' values.\n"
        "2. Omit optional parameters entirely if they don't have values instead of setting them to null.\n"
        "3. For required parameters, always provide appropriate values.\n"
        "4. Default values will be automatically applied for omitted optional parameters.\n"
        "5. For parameters that accept lists (like goal_ids), you can provide either a single value or a list.\n\n"
        
        "USING POSTGRESQL DATABASE:\n"
        "1. All data is stored in a PostgreSQL database using SQLModel ORM.\n"
        "2. The database schema includes Task, Goal, Note, and Event tables.\n"
        "3. Many-to-many relationships are implemented through link tables.\n\n"
        
        "When responding to users, provide helpful, **CONCISE** responses."
        f"{user_notes}"
    )
    
    history = [
        {
            "role": "system",
            "content": system_prompt
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
            # Refresh system prompt in case user notes have changed
            user_notes = get_system_notes()
            system_prompt = system_prompt.split("USER NOTES AND PREFERENCES")[0] + user_notes
            history = [{"role": "system", "content": system_prompt}]  # Keep only the system message
            continue
        
        try:
            # Add user message to history
            history.append({"role": "user", "content": user_input})
            
            print(f"{Colors.YELLOW}Sending request to LLM...{Colors.RESET}")
            
            # Process LLM responses with potential multiple consecutive tool calls
            consecutive_tool_calls = 0
            max_consecutive_tool_calls = 5  # Limit to prevent infinite loops
            
            # Continue processing responses until there are no more tool calls or we hit the limit
            while consecutive_tool_calls < max_consecutive_tool_calls:
                # Send all messages to LLM
                response = await send_message(history)
                
                # Get assistant message
                assistant_message = response.choices[0].message
                content = assistant_message.get("content", "")
                
                # Check for tool calls
                tool_calls = assistant_message.get("tool_calls", [])
                
                if tool_calls:
                    consecutive_tool_calls += 1
                    print(f"\n{Colors.BOLD}{Colors.MAGENTA}LLM requested {len(tool_calls)} tool call(s) [{consecutive_tool_calls}/{max_consecutive_tool_calls}]{Colors.RESET}")
                    
                    # Store tool results for adding to history
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
                    
                    # Add the assistant's message to history (with tool calls)
                    history.append({
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls
                    })
                    
                    # Create tool results message
                    tool_results_message = {
                        "role": "tool",
                        "tool_call_id": tool_calls[0]["id"],  # First tool call ID
                        "content": json.dumps(
                            {tool_results[0][0]: tool_results[0][1]}, 
                            default=str
                        )
                    }
                    
                    # Handle additional tool calls if there were multiple
                    if len(tool_calls) > 1:
                        for i, tool_call in enumerate(tool_calls[1:], 1):
                            tool_results_message = {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": json.dumps(
                                    {tool_results[i][0]: tool_results[i][1]}, 
                                    default=str
                                )
                            }
                            history.append(tool_results_message)
                    
                    # Add combined tool results message
                    history.append(tool_results_message)
                    
                    # Continue the loop to let the LLM potentially make more tool calls
                
                else:
                    # No tool calls, just add response to history and display it
                    history.append({"role": "assistant", "content": content})
                    print(f"\n{content}")
                    break  # Exit the tool call loop
            
            # If we've hit the maximum consecutive tool calls, let the user know
            if consecutive_tool_calls >= max_consecutive_tool_calls:
                warning_msg = f"\n{Colors.YELLOW}Warning: Reached maximum number of consecutive tool calls ({max_consecutive_tool_calls}).{Colors.RESET}"
                print(warning_msg)
            
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
    check_color_support()
    asyncio.run(chat_loop())