from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from models import Task, TaskState
from storage import JsonStore
from tools.tool import Tool, tool


# Parameter models for task operations
class CreateTaskParams(BaseModel):
    id: str = Field(description="Unique identifier for the task")
    name: str = Field(description="Short descriptive title of the task")
    estimated_completion_time: int = Field(description="Estimated completion time in minutes")
    goals: List[str] = Field(description="List of goal identifiers this task contributes to")
    state: Optional[TaskState] = Field(default=TaskState.INCOMPLETE, description="Task state")
    schedule_on_or_after: Optional[datetime] = Field(default=None, description="Earliest date to schedule")
    due_by: Optional[datetime] = Field(default=None, description="Task deadline")
    depends_on: Optional[List[str]] = Field(default=None, description="IDs of prerequisite tasks")
    can_complete_late: Optional[bool] = Field(default=True, description="Allow completion after due date")
    log_instructions: Optional[str] = Field(default=None, description="Guidelines for task logging")


class UpdateTaskParams(BaseModel):
    id: str = Field(description="Task ID to update")
    name: Optional[str] = Field(default=None, description="Updated task title")
    state: Optional[TaskState] = Field(default=None, description="Updated task state")
    estimated_completion_time: Optional[int] = Field(default=None, description="Updated time estimate")
    actual_completion_time: Optional[int] = Field(default=None, description="Actual completion time")
    goals: Optional[List[str]] = Field(default=None, description="Updated goal references")
    schedule_on_or_after: Optional[datetime] = Field(default=None, description="Updated earliest schedule date")
    due_by: Optional[datetime] = Field(default=None, description="Updated deadline")
    depends_on: Optional[List[str]] = Field(default=None, description="Updated prerequisites")
    log: Optional[Dict[str, Any]] = Field(default=None, description="Task progress log")


class GetTaskParams(BaseModel):
    id: str = Field(description="Task ID to retrieve")


class ListTasksParams(BaseModel):
    state: Optional[TaskState] = Field(default=None, description="Filter by task state")
    goal: Optional[str] = Field(default=None, description="Filter by associated goal")
    due_before: Optional[datetime] = Field(default=None, description="Filter by due date before")
    due_after: Optional[datetime] = Field(default=None, description="Filter by due date after")
    template_id: Optional[str] = Field(default=None, description="Filter by template ID")


class DeleteTaskParams(BaseModel):
    id: str = Field(description="Task ID to delete")


class CompleteTaskParams(BaseModel):
    id: str = Field(description="Task ID to mark as complete")
    actual_completion_time: Optional[int] = Field(default=None, description="Actual time taken in minutes")
    log_data: Optional[Dict[str, Any]] = Field(default=None, description="Completion log data")


# Create the storage instance for tasks
task_store = JsonStore(Task, "data/tasks.json")


# Tool functions
@tool(parameter_model=CreateTaskParams)
def create_task(id: str, name: str, estimated_completion_time: int, goals: List[str],
                state: TaskState = TaskState.INCOMPLETE, schedule_on_or_after: Optional[datetime] = None,
                due_by: Optional[datetime] = None, depends_on: Optional[List[str]] = None,
                can_complete_late: bool = True, log_instructions: Optional[str] = None) -> Task:
    """Create a new task"""
    task = Task(
        id=id,
        name=name,
        estimated_completion_time=estimated_completion_time,
        goals=goals,
        state=state,
        schedule_on_or_after=schedule_on_or_after,
        due_by=due_by,
        depends_on=depends_on,
        can_complete_late=can_complete_late,
        log_instructions=log_instructions
    )
    return task_store.create(task)


@tool(parameter_model=UpdateTaskParams)
def update_task(id: str, name: Optional[str] = None, state: Optional[TaskState] = None,
                estimated_completion_time: Optional[int] = None, actual_completion_time: Optional[int] = None,
                goals: Optional[List[str]] = None, schedule_on_or_after: Optional[datetime] = None,
                due_by: Optional[datetime] = None, depends_on: Optional[List[str]] = None,
                log: Optional[Dict[str, Any]] = None) -> Optional[Task]:
    """Update an existing task"""
    existing_task = task_store.get_by_id(id)
    if not existing_task:
        return None
    
    # Update only provided fields
    updated_data = existing_task.model_dump()
    
    update_fields = {
        "name": name,
        "state": state,
        "estimated_completion_time": estimated_completion_time,
        "actual_completion_time": actual_completion_time,
        "goals": goals,
        "schedule_on_or_after": schedule_on_or_after,
        "due_by": due_by,
        "depends_on": depends_on,
        "log": log
    }
    
    for field, value in update_fields.items():
        if value is not None:
            updated_data[field] = value
    
    updated_task = Task.model_validate(updated_data)
    return task_store.update(id, updated_task)


@tool(parameter_model=GetTaskParams)
def get_task(id: str) -> Optional[Task]:
    """Get a task by ID"""
    return task_store.get_by_id(id)


@tool(parameter_model=ListTasksParams)
def list_tasks(state: Optional[TaskState] = None, goal: Optional[str] = None,
               due_before: Optional[datetime] = None, due_after: Optional[datetime] = None,
               template_id: Optional[str] = None) -> List[Task]:
    """List tasks with optional filtering"""
    
    def filter_func(task: Task) -> bool:
        matches = True
        
        if state is not None:
            matches = matches and task.state == state
            
        if goal is not None:
            matches = matches and goal in task.goals
            
        if due_before is not None and task.due_by is not None:
            matches = matches and task.due_by < due_before
            
        if due_after is not None and task.due_by is not None:
            matches = matches and task.due_by > due_after
            
        if template_id is not None:
            matches = matches and task.template_id == template_id
            
        return matches
    
    return task_store.query(filter_func)


@tool(parameter_model=DeleteTaskParams)
def delete_task(id: str) -> bool:
    """Delete a task"""
    return task_store.delete(id)


@tool(parameter_model=CompleteTaskParams)
def complete_task(id: str, actual_completion_time: Optional[int] = None, log_data: Optional[Dict[str, Any]] = None) -> Optional[Task]:
    """Mark a task as complete with actual time and log data"""
    existing_task = task_store.get_by_id(id)
    if not existing_task:
        return None
    
    # Update task properties
    updated_data = existing_task.model_dump()
    updated_data["state"] = TaskState.COMPLETED
    
    if actual_completion_time is not None:
        updated_data["actual_completion_time"] = actual_completion_time
    
    # Update or initialize log
    if log_data is not None:
        if updated_data["log"] is None:
            updated_data["log"] = log_data
        else:
            updated_data["log"].update(log_data)
    
    updated_task = Task.model_validate(updated_data)
    return task_store.update(id, updated_task)


# Create Tool objects
create_task_tool = Tool("create_task", create_task, CreateTaskParams, "Create a new task")
update_task_tool = Tool("update_task", update_task, UpdateTaskParams, "Update an existing task")
get_task_tool = Tool("get_task", get_task, GetTaskParams, "Get a task by ID")
list_tasks_tool = Tool("list_tasks", list_tasks, ListTasksParams, "List tasks with optional filtering")
delete_task_tool = Tool("delete_task", delete_task, DeleteTaskParams, "Delete a task")
complete_task_tool = Tool("complete_task", complete_task, CompleteTaskParams, "Mark a task as complete")

# Create task toolset
task_tools = [
    create_task_tool,
    update_task_tool,
    get_task_tool,
    list_tasks_tool,
    delete_task_tool,
    complete_task_tool
]