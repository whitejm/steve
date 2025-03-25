from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypeVar, Generic, Type

T = TypeVar('T')


class StorageInterface(Generic[T], ABC):
    """Abstract base class for storage implementations"""
    
    @abstractmethod
    def get_all(self) -> List[T]:
        """Retrieve all items from storage"""
        pass
    
    @abstractmethod
    def get_by_id(self, id_value: str) -> Optional[T]:
        """Retrieve a specific item by ID"""
        pass
    
    @abstractmethod
    def create(self, item: T) -> T:
        """Create a new item in storage"""
        pass
    
    @abstractmethod
    def update(self, id_value: str, item: T) -> Optional[T]:
        """Update an existing item"""
        pass
    
    @abstractmethod
    def delete(self, id_value: str) -> bool:
        """Delete an item from storage"""
        pass
    
    @abstractmethod
    def query(self, filter_func) -> List[T]:
        """Query items matching a filter function"""
        pass