# Tools System

This directory contains the tools system for the AI Task & Goal Tracking application. Tools are operations that can be executed by the AI assistant through LiteLLM integration.

## Tool Structure

Each tool consists of three components:

1. **Pydantic Parameter Model**: Defines and validates the parameters for the tool
2. **Function**: Implements the actual operation
3. **Tool Object**: Connects the function and parameter model with metadata

## Creating New Tools

Follow this pattern when creating new tools:

### 1. Define a Parameter Model

```python
from pydantic import BaseModel, Field

class MyToolParams(BaseModel):
    param1: str = Field(description="Description of param1")
    param2: int = Field(description="Description of param2")
    optional_param: Optional[bool] = Field(default=False, description="Optional parameter")
```

### 2. Create the Tool Function with Decorator

```python
from tools.tool import tool

@tool(parameter_model=MyToolParams)
def my_tool_function(param1, param2, optional_param=False):
    """Description of what this tool does"""
    # Implementation
    result = do_something(param1, param2, optional_param)
    return result
```

### 3. Create the Tool Object

```python
from tools.tool import Tool

my_tool = Tool(
    "my_tool_name",
    my_tool_function,
    MyToolParams,
    "Human-readable description of the tool"
)
```

### 4. Add to a ToolSet

```python
# Add to an existing toolset
my_tools = [my_tool, another_tool]

# Or add to the global toolset in __init__.py
all_tools = existing_tools + my_tools
toolset = ToolSet(all_tools)
```

## Best Practices

1. **Keep tools focused**: Each tool should do one thing well
2. **Descriptive names**: Use clear naming for tools and parameters
3. **Parameter validation**: Use Pydantic's validation features (Field constraints, validators)
4. **Error handling**: Tools should handle errors gracefully and provide clear error messages
5. **Idempotency**: When possible, make tools idempotent (can be called multiple times with same result)
6. **Documentation**: Include detailed docstrings for all tools

## Integration with LiteLLM

The `toolset.get_descriptions()` method provides tool descriptions in the format expected by LiteLLM's tool calling interface.
