import inspect
from typing import Any, Callable, Dict, List, Optional, Type
from functools import wraps
from pydantic import BaseModel, create_model


class Tool:
    """Represents an operation with parameter validation"""
    
    def __init__(self, name: str, function: Callable, parameter_model: Type[BaseModel], description: Optional[str] = None):
        """
        Initialize a new tool
        
        Args:
            name: The tool name
            function: The function to execute
            parameter_model: Pydantic model for parameter validation
            description: Optional description of the tool
        """
        self.name = name
        self.function = function
        self.parameter_model = parameter_model
        self.description = description or function.__doc__ or ""
        
        # Validate that function signature matches parameter model
        self._validate_function_signature()
    
    def _validate_function_signature(self):
        """Ensure the function signature matches the parameter model fields"""
        sig = inspect.signature(self.function)
        func_params = set(sig.parameters.keys())
        model_fields = set(self.parameter_model.__annotations__.keys())
        
        if func_params != model_fields:
            missing = model_fields - func_params
            extra = func_params - model_fields
            error_msg = []
            
            if missing:
                error_msg.append(f"Missing parameters in function: {missing}")
            if extra:
                error_msg.append(f"Extra parameters in function: {extra}")
            
            raise ValueError(f"Function signature does not match parameter model: {', '.join(error_msg)}")
    
    def get_description(self) -> Dict[str, Any]:
        """Format tool description for LiteLLM integration"""
        fields = {}
        for name, field in self.parameter_model.__annotations__.items():
            field_info = self.parameter_model.model_fields.get(name)
            description = field_info.description if field_info and field_info.description else ""
            
            # Convert field type to OpenAI function type
            field_type = self._get_openai_type(field)
            fields[name] = {
                "type": field_type,
                "description": description
            }
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": fields,
                    "required": self._get_required_fields()
                }
            }
        }
    
    def _get_required_fields(self) -> List[str]:
        """Get list of required fields from the parameter model"""
        return [
            name for name, field in self.parameter_model.model_fields.items()
            if field.is_required()
        ]
    
    def _get_openai_type(self, field_type) -> str:
        """Convert Python/Pydantic type to OpenAI function type"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }
        
        base_type = getattr(field_type, "__origin__", field_type)
        return type_map.get(base_type, "string")
    
    def execute(self, **kwargs):
        """Validate and execute the function"""
        validated_params = self.parameter_model(**kwargs)
        return self.function(**validated_params.model_dump())


class ToolSet:
    """Collection of related tools"""
    
    def __init__(self, tools: List[Tool]):
        """
        Initialize a set of tools
        
        Args:
            tools: List of Tool objects
        """
        self.tools = tools
        self._tool_dict = {tool.name: tool for tool in tools}
    
    def get_descriptions(self) -> List[Dict]:
        """Get descriptions for all tools in format for LiteLLM tools parameter"""
        return [tool.get_description() for tool in self.tools]
    
    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tool_dict.get(name)


def tool(parameter_model: Type[BaseModel]):
    """
    Decorator for creating tools
    
    Args:
        parameter_model: Pydantic model for parameter validation
    
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Attach metadata for tool creation
        wrapper.tool_parameter_model = parameter_model
        wrapper.is_tool = True
        return wrapper
    return decorator