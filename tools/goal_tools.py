from typing import Optional, List
from pydantic import BaseModel, Field

from models import Goal, GoalState
from storage import JsonStore
from tools.tool import Tool, tool


# Parameter models for goal operations
class CreateGoalParams(BaseModel):
    name: str = Field(description=Goal.model_fields["name"].description)
    short_description: str = Field(description=Goal.model_fields["short_description"].description)
    long_description: str = Field(description=Goal.model_fields["long_description"].description)
    # Removed state from the parameters as it should always default to ACTIVE


class UpdateGoalParams(BaseModel):
    name: str = Field(description=Goal.model_fields["name"].description)
    short_description: Optional[str] = Field(default=None, description=Goal.model_fields["short_description"].description)
    long_description: Optional[str] = Field(default=None, description=Goal.model_fields["long_description"].description)
    state: Optional[GoalState] = Field(default=None, description=Goal.model_fields["state"].description)


class GetGoalParams(BaseModel):
    name: str = Field(description=Goal.model_fields["name"].description)


class ListGoalsParams(BaseModel):
    state: Optional[GoalState] = Field(default=None, description=Goal.model_fields["state"].description)
    parent_prefix: Optional[str] = Field(default=None, description="Filter goals by parent prefix (e.g., 'health')")


class DeleteGoalParams(BaseModel):
    name: str = Field(description=Goal.model_fields["name"].description)


# Create the storage instance for goals
goal_store = JsonStore(Goal, "data/goals.json")


# Tool functions
@tool(parameter_model=CreateGoalParams)
def create_goal(name: str, short_description: str, long_description: str) -> Goal:
    """Create a new goal"""
    goal = Goal(
        name=name,
        short_description=short_description,
        long_description=long_description,
        state=GoalState.ACTIVE  # Always set to ACTIVE by default
    )
    return goal_store.create(goal)


@tool(parameter_model=UpdateGoalParams)
def update_goal(name: str, short_description: Optional[str] = None, 
                long_description: Optional[str] = None, state: Optional[GoalState] = None) -> Optional[Goal]:
    """Update an existing goal"""
    existing_goal = goal_store.get_by_id(name)
    if not existing_goal:
        return None
    
    # Update only provided fields
    updated_data = existing_goal.model_dump()
    if short_description is not None:
        updated_data["short_description"] = short_description
    if long_description is not None:
        updated_data["long_description"] = long_description
    if state is not None:
        updated_data["state"] = state
    
    updated_goal = Goal.model_validate(updated_data)
    return goal_store.update(name, updated_goal)


@tool(parameter_model=GetGoalParams)
def get_goal(name: str) -> Optional[Goal]:
    """Get a goal by name"""
    return goal_store.get_by_id(name)


@tool(parameter_model=ListGoalsParams)
def list_goals(state: Optional[GoalState] = None, parent_prefix: Optional[str] = None) -> List[Goal]:
    """List goals with optional filtering"""
    
    def filter_func(goal: Goal) -> bool:
        matches = True
        if state is not None:
            matches = matches and goal.state == state
        if parent_prefix is not None:
            matches = matches and goal.name.startswith(f"{parent_prefix}.")
        return matches
    
    return goal_store.query(filter_func)


@tool(parameter_model=DeleteGoalParams)
def delete_goal(name: str) -> bool:
    """Delete a goal"""
    return goal_store.delete(name)


# Create Tool objects
create_goal_tool = Tool("create_goal", create_goal, CreateGoalParams, "Create a new goal")
update_goal_tool = Tool("update_goal", update_goal, UpdateGoalParams, "Update an existing goal")
get_goal_tool = Tool("get_goal", get_goal, GetGoalParams, "Get a goal by name")
list_goals_tool = Tool("list_goals", list_goals, ListGoalsParams, "List goals with optional filtering")
delete_goal_tool = Tool("delete_goal", delete_goal, DeleteGoalParams, "Delete a goal")

# Create goal toolset
goal_tools = [
    create_goal_tool,
    update_goal_tool,
    get_goal_tool,
    list_goals_tool,
    delete_goal_tool
]