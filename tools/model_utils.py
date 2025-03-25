from typing import Type, List, Optional, Dict, Any, Union, get_type_hints, get_origin, get_args
from pydantic import BaseModel, Field, create_model

def create_subset_model(
    model_class: Type[BaseModel],
    field_names: List[str],
    model_name: Optional[str] = None,
    make_optional: List[str] = None,
    overrides: Dict[str, Dict[str, Any]] = None
) -> Type[BaseModel]:
    """
    Create a new Pydantic model class that includes only specified fields from an existing model.
    
    Args:
        model_class: The source Pydantic model class
        field_names: List of field names to include in the new model
        model_name: Optional name for the new model (defaults to f"{model_class.__name__}Subset")
        make_optional: List of field names that should be made optional in the new model
        overrides: Dictionary of field name to field parameter overrides
        
    Returns:
        A new Pydantic model class with the specified fields
    """
    if make_optional is None:
        make_optional = []
    
    if overrides is None:
        overrides = {}
    
    # Get type hints for annotations
    type_hints = get_type_hints(model_class)
    
    # Prepare fields for the new model
    fields = {}
    
    for field_name in field_names:
        if field_name not in model_class.model_fields:
            raise ValueError(f"Field '{field_name}' not found in {model_class.__name__}")
        
        original_field = model_class.model_fields[field_name]
        field_type = type_hints[field_name]
        
        # Make field optional if requested
        if field_name in make_optional:
            # Get the original type without Optional wrapper
            origin = get_origin(field_type)
            if origin is not None and origin is Union and type(None) in get_args(field_type):
                # Already Optional
                pass
            else:
                from typing import Optional as OptionalType
                field_type = OptionalType[field_type]
        
        # Get field parameters including defaults
        field_params = {
            "description": original_field.description,
        }
        
        # FIXED: Preserve original default values even for optional fields
        if original_field.default is not Ellipsis:
            field_params["default"] = original_field.default
        elif field_name in make_optional:
            # Only set to None if there was no default and it's optional
            field_params["default"] = None
            
        # Apply any overrides for this field
        if field_name in overrides:
            field_params.update(overrides[field_name])
        
        # Add the field to our collection
        fields[field_name] = (field_type, Field(**field_params))
    
    # Create and return the new model
    new_model_name = model_name or f"{model_class.__name__}Subset"
    return create_model(new_model_name, **fields)