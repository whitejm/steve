import json
import os
from typing import List, Dict, Any, Optional, TypeVar, Generic, Type
from pydantic import BaseModel

from storage.storage_interface import StorageInterface

T = TypeVar('T', bound=BaseModel)


class JsonStore(StorageInterface[T]):
    """JSON file-based storage implementation"""
    
    def __init__(self, model_class: Type[T], file_path: str):
        """
        Initialize a JSON storage for a specific model type
        
        Args:
            model_class: The Pydantic model class to store
            file_path: Path to the JSON file
        """
        self.model_class = model_class
        self.file_path = file_path
        self.id_field = self._get_id_field()
        self._ensure_file_exists()
    
    def _get_id_field(self) -> str:
        """Determine the ID field for the model"""
        # Assuming models have an 'id' field or 'name' field that serves as ID
        fields = self.model_class.__annotations__.keys()
        if 'id' in fields:
            return 'id'
        elif 'name' in fields:
            return 'name'
        else:
            raise ValueError(f"Model {self.model_class.__name__} must have an 'id' or 'name' field")
    
    def _ensure_file_exists(self):
        """Create the JSON file if it doesn't exist"""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump([], f)
    
    def _read_data(self) -> List[Dict[str, Any]]:
        """Read all data from the JSON file"""
        with open(self.file_path, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    
    def _write_data(self, data: List[Dict[str, Any]]):
        """Write data to the JSON file"""
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_all(self) -> List[T]:
        """Retrieve all items from storage"""
        data = self._read_data()
        return [self.model_class.model_validate(item) for item in data]
    
    def get_by_id(self, id_value: str) -> Optional[T]:
        """Retrieve a specific item by ID"""
        data = self._read_data()
        for item in data:
            if item.get(self.id_field) == id_value:
                return self.model_class.model_validate(item)
        return None
    
    def create(self, item: T) -> T:
        """Create a new item in storage"""
        data = self._read_data()
        
        # Check for duplicate ID
        id_value = getattr(item, self.id_field)
        if any(i.get(self.id_field) == id_value for i in data):
            raise ValueError(f"Item with {self.id_field}='{id_value}' already exists")
        
        # Add new item
        item_dict = item.model_dump()
        data.append(item_dict)
        self._write_data(data)
        return item
    
    def update(self, id_value: str, item: T) -> Optional[T]:
        """Update an existing item"""
        data = self._read_data()
        
        for i, existing_item in enumerate(data):
            if existing_item.get(self.id_field) == id_value:
                # Ensure the ID remains the same
                item_dict = item.model_dump()
                if item_dict.get(self.id_field) != id_value:
                    item_dict[self.id_field] = id_value
                
                data[i] = item_dict
                self._write_data(data)
                return self.model_class.model_validate(item_dict)
        
        return None
    
    def delete(self, id_value: str) -> bool:
        """Delete an item from storage"""
        data = self._read_data()
        initial_length = len(data)
        
        filtered_data = [item for item in data if item.get(self.id_field) != id_value]
        
        if len(filtered_data) < initial_length:
            self._write_data(filtered_data)
            return True
        
        return False
    
    def query(self, filter_func) -> List[T]:
        """Query items matching a filter function"""
        all_items = self.get_all()
        return [item for item in all_items if filter_func(item)]