from typing import Optional, List, Union
from datetime import date
from pydantic import BaseModel, Field, validator
from sqlmodel import select, Session

from database import engine
from models import Goal, GoalState
from tools.tool import Tool, tool


# Parameter models for goal operations
class CreateGoalParams(BaseModel):
    name: str = Field(description="Goal name (no spaces or dots allowed)")
    notes: Optional[str] = Field(default=None, description="Detailed notes about the goal")
    state: GoalState = Field(default=GoalState.ongoing, description="Current state of the goal")
    desired_completion_date: Optional[date] = Field(default=None, description="Target date to complete this goal")
    parent_goal_id: Optional[int] = Field(default=None, description="ID of the parent goal if this is a subgoal")

class UpdateGoalParams(BaseModel):
    id: int = Field(description="ID of the goal to update")
    name: Optional[str] = Field(default=None, description="Updated goal name (no spaces or dots allowed)")
    notes: Optional[str] = Field(default=None, description="Updated detailed notes")
    state: Optional[GoalState] = Field(default=None, description="Updated goal state")
    desired_completion_date: Optional[date] = Field(default=None, description="Updated target completion date")
    parent_goal_id: Optional[int] = Field(default=None, description="Updated parent goal ID")

class GetGoalParams(BaseModel):
    id: int = Field(description="ID of the goal to retrieve")

class ListGoalsParams(BaseModel):
    state: Optional[GoalState] = Field(default=None, description="Filter goals by state")
    parent_goal_id: Optional[int] = Field(default=None, description="Filter by parent goal ID")

class DeleteGoalParams(BaseModel):
    id: int = Field(description="ID of the goal to delete")


# Tool functions
@tool(parameter_model=CreateGoalParams)
def create_goal(name: str, state: GoalState = GoalState.ongoing, 
                notes: Optional[str] = None, 
                desired_completion_date: Optional[date] = None,
                parent_goal_id: Optional[int] = None) -> Goal:
    """Create a new goal"""
    with Session(engine) as session:
        # Check if parent goal exists if specified
        if parent_goal_id is not None:
            parent_goal = session.get(Goal, parent_goal_id)
            if not parent_goal:
                raise ValueError(f"Parent goal with ID {parent_goal_id} does not exist")
        
        # Create new goal
        goal = Goal(
            name=name,
            notes=notes,
            state=state,
            desired_completion_date=desired_completion_date,
            parent_goal_id=parent_goal_id
        )
        
        session.add(goal)
        session.commit()
        session.refresh(goal)
        
        # Return a dict representation since SQLModel objects might have lazy-loaded attributes
        return goal


@tool(parameter_model=UpdateGoalParams)
def update_goal(id: int, name: Optional[str] = None, notes: Optional[str] = None,
                state: Optional[GoalState] = None, 
                desired_completion_date: Optional[date] = None,
                parent_goal_id: Optional[int] = None) -> Optional[Goal]:
    """Update an existing goal"""
    with Session(engine) as session:
        goal = session.get(Goal, id)
        if not goal:
            return None
        
        # Check if parent goal exists if specified
        if parent_goal_id is not None:
            parent_goal = session.get(Goal, parent_goal_id)
            if not parent_goal:
                raise ValueError(f"Parent goal with ID {parent_goal_id} does not exist")
            
            # Prevent circular references
            if parent_goal_id == id:
                raise ValueError("A goal cannot be its own parent")
        
        # Update provided fields
        if name is not None:
            goal.name = name
        if notes is not None:
            goal.notes = notes
        if state is not None:
            goal.state = state
        if desired_completion_date is not None:
            goal.desired_completion_date = desired_completion_date
        if parent_goal_id is not None:
            goal.parent_goal_id = parent_goal_id
        
        session.add(goal)
        session.commit()
        session.refresh(goal)
        
        return goal


@tool(parameter_model=GetGoalParams)
def get_goal(id: int) -> Optional[Goal]:
    """Get a goal by ID"""
    with Session(engine) as session:
        goal = session.get(Goal, id)
        if not goal:
            return None
        return goal


@tool(parameter_model=ListGoalsParams)
def list_goals(state: Optional[GoalState] = None, parent_goal_id: Optional[int] = None) -> List[Goal]:
    """List goals with optional filtering"""
    with Session(engine) as session:
        query = select(Goal)
        
        if state is not None:
            query = query.where(Goal.state == state)
        
        if parent_goal_id is not None:
            query = query.where(Goal.parent_goal_id == parent_goal_id)
        
        results = session.exec(query).all()
        return list(results)


@tool(parameter_model=DeleteGoalParams)
def delete_goal(id: int) -> bool:
    """Delete a goal"""
    with Session(engine) as session:
        goal = session.get(Goal, id)
        if not goal:
            return False
        
        # Check if this goal has subgoals
        subgoals_query = select(Goal).where(Goal.parent_goal_id == id)
        subgoals = session.exec(subgoals_query).all()
        
        if subgoals:
            raise ValueError(f"Cannot delete goal with ID {id} because it has {len(subgoals)} subgoals. Delete the subgoals first.")
        
        session.delete(goal)
        session.commit()
        return True


# Create Tool objects
create_goal_tool = Tool("create_goal", create_goal, CreateGoalParams, "Create a new goal")
update_goal_tool = Tool("update_goal", update_goal, UpdateGoalParams, "Update an existing goal")
get_goal_tool = Tool("get_goal", get_goal, GetGoalParams, "Get a goal by ID")
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