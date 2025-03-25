# Tools System

This directory contains the tools system for the AI Task & Goal Tracking application. Tools are operations that can be executed by the AI assistant through LiteLLM integration.

## Tool Structure

Each tool consists of three components:

1. **Pydantic Parameter Model**: Defines and validates the parameters for the tool
2. **Function**: Implements the actual operation
3. **Tool Object**: Connects the function and parameter model with metadata

## Model Utils

The `model_utils.py` module provides utilities for creating parameter models by reusing field definitions from base models:

```python
from tools.model_utils import create_subset_model
from models import Task

# Create a parameter model from a subset of Task fields
CreateTaskParams = create_subset_model(
    Task,
    ["id", "name", "estimated_completion_time", "goals"],
    model_name="CreateTaskParams",
    make_optional=["goals"],
    overrides={"name": {"description": "Custom description"}}
)
```

This approach ensures consistency between models and parameter definitions, reduces code duplication, and improves maintainability.

## Creating New Tools

Follow this pattern when creating new tools:

### 1. Define a Parameter Model

Use the `create_subset_model` helper when your parameter model is based on an existing model:

```python
from tools.model_utils import create_subset_model
from models import YourModel

YourToolParams = create_subset_model(
    YourModel,
    ["field1", "field2", "field3"],
    model_name="YourToolParams",
    make_optional=["field3"],
    overrides={"field1": {"description": "Custom description"}}
)
```

Or define a new model manually for unique parameter sets:

```python
from pydantic import BaseModel, Field

class YourToolParams(BaseModel):
    param1: str = Field(description="Description of param1")
    param2: int = Field(description="Description of param2")
    optional_param: Optional[bool] = Field(default=False, description="Optional parameter")
```

### 2. Create the Tool Function with Decorator

```python
from tools.tool import tool

@tool(parameter_model=YourToolParams)
def your_tool_function(param1, param2, optional_param=False):
    """Description of what this tool does"""
    # Implementation
    result = do_something(param1, param2, optional_param)
    return result
```

### 3. Create the Tool Object

```python
from tools.tool import Tool

your_tool = Tool(
    "your_tool_name",
    your_tool_function,
    YourToolParams,
    "Human-readable description of the tool"
)
```

### 4. Add to a ToolSet

```python
# Add to an existing toolset
your_tools = [your_tool, another_tool]

# Or add to the global toolset in __init__.py
all_tools = existing_tools + your_tools
toolset = ToolSet(all_tools)
```

## Best Practices

1. **Keep tools focused**: Each tool should do one thing well
2. **Use model_utils**: Leverage the `create_subset_model` function to maintain consistency
3. **Parameter validation**: Use Pydantic's validation features (Field constraints, validators)
4. **Error handling**: Tools should handle errors gracefully and provide clear error messages
5. **Idempotency**: When possible, make tools idempotent (can be called multiple times with same result)
6. **Documentation**: Include detailed docstrings for all tools

## Integration with LiteLLM

The `toolset.get_descriptions()` method provides tool descriptions in the format expected by LiteLLM's tool calling interface.
