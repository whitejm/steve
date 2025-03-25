from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, create_model

from models import Task, TaskState
from storage import JsonStore
from tools.tool import Tool, tool
from tools.model_utils import create_subset_model
from tools.goal_tools import goal_store  # Import goal_store to validate goals


# Parameter models for task operations using the model_utils helper
CreateTaskParams = create_subset_model(
    Task,
    ["id", "name", "estimated_completion_time", "goals", "state", "schedule_on_or_after", 
     "due_by", "depends_on", "can_complete_late", "log_instructions"],
    model_name="CreateTaskParams",
    make_optional=["goals", "state", "schedule_on_or_after", "due_by", "depends_on", 
                  "can_complete_late", "log_instructions"]
)

UpdateTaskParams = create_subset_model(
    Task, 
    ["id", "name", "state", "estimated_completion_time", "actual_completion_time", 
     "goals", "schedule_on_or_after", "due_by", "depends_on", "log"],
    model_name="UpdateTaskParams",
    make_optional=["name", "state", "estimated_completion_time", "actual_completion_time", 
                  "goals", "schedule_on_or_after", "due_by", "depends_on", "log"]
)

class GetTaskParams(BaseModel):
    id: str = Field(description=Task.model_fields["id"].description)


class ListTasksParams(BaseModel):
    state: Optional[TaskState] = None
    goal: Optional[str] = None
    due_before: Optional[datetime] = None
    due_after: Optional[datetime] = None
    template_id: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class DeleteTaskParams(BaseModel):
    id: str = Field(description=Task.model_fields["id"].description)


CompleteTaskParams = create_model(
    "CompleteTaskParams",
    id=(str, Field(description="Task ID to mark as complete")),
    actual_completion_time=(Optional[int], Field(default=None, description="Actual time taken in minutes")),
    log_data=(Optional[Dict[str, Any]], Field(default=None, description="Completion log data"))
)


# Create the storage instance for tasks
task_store = JsonStore(Task, "data/tasks.json")


# Tool functions
@tool(parameter_model=CreateTaskParams)
def create_task(id: str, name: str, estimated_completion_time: int, 
                goals: Optional[List[str]] = None,
                state: TaskState = TaskState.INCOMPLETE, 
                schedule_on_or_after: Optional[datetime] = None,
                due_by: Optional[datetime] = None, 
                depends_on: Optional[List[str]] = None,
                can_complete_late: bool = True, 
                log_instructions: Optional[str] = None) -> Task:
    """Create a new task"""
    # Initialize goals to empty list if None
    if goals is None:
        goals = []
    
    # Validate that all specified goals exist
    if goals:
        existing_goals = {goal.name for goal in goal_store.get_all()}
        non_existent_goals = [goal for goal in goals if goal not in existing_goals]
        
        if non_existent_goals:
            raise ValueError(f"The following goals do not exist: {', '.join(non_existent_goals)}")
    
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
    
    # Validate that all specified goals exist if goals are being updated
    if goals is not None:
        existing_goals = {goal.name for goal in goal_store.get_all()}
        non_existent_goals = [goal for goal in goals if goal not in existing_goals]
        
        if non_existent_goals:
            raise ValueError(f"The following goals do not exist: {', '.join(non_existent_goals)}")
    
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