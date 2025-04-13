from typing import List, Optional
from datetime import datetime, date
from enum import Enum
from sqlmodel import Field, Relationship, SQLModel

# Enums
class TaskState(str, Enum):
    incomplete = "incomplete"
    completed = "completed"
    abandoned = "abandoned"
    missed = "missed"

class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

class GoalState(str, Enum):
    incomplete = "incomplete"
    completed = "completed"
    abandoned = "abandoned"
    ongoing = "ongoing"

class NoteType(str, Enum):
    user_preference = "user_preference"
    reference = "reference"
    general = "general"

# Association tables for many-to-many relationships
class TaskGoalLink(SQLModel, table=True):
    task_id: Optional[int] = Field(default=None, foreign_key="task.id", primary_key=True)
    goal_id: Optional[int] = Field(default=None, foreign_key="goal.id", primary_key=True)

class TaskDependencyLink(SQLModel, table=True):
    task_id: Optional[int] = Field(default=None, foreign_key="task.id", primary_key=True)
    depends_on_task_id: Optional[int] = Field(default=None, foreign_key="task.id", primary_key=True)

# Main models
class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    notes: Optional[str] = None
    state: TaskState = TaskState.incomplete
    priority: TaskPriority
    estimated_completion_time_minutes: int
    schedule_on_or_after: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    due: Optional[datetime] = None
    scheduling_notes: Optional[str] = None
    mark_missed_after_days_overdue: Optional[int] = 0
    actual_completion_time_minutes: Optional[int] = None
    rrule: Optional[str] = None
    rrule_template_id: Optional[int] = Field(default=None, foreign_key="task.id")
    
    # Relationships
    goals: List["Goal"] = Relationship(back_populates="tasks", link_model=TaskGoalLink)
    template: Optional["Task"] = Relationship(
        sa_relationship_kwargs={"remote_side": "Task.id"}, 
        back_populates="instances"
    )
    instances: List["Task"] = Relationship(back_populates="template")
    dependencies: List["Task"] = Relationship(
        back_populates="dependent_tasks",
        link_model=TaskDependencyLink,
        sa_relationship_kwargs={"primaryjoin": "Task.id == TaskDependencyLink.task_id", 
                              "secondaryjoin": "Task.id == TaskDependencyLink.depends_on_task_id"}
    )
    dependent_tasks: List["Task"] = Relationship(
        back_populates="dependencies",
        link_model=TaskDependencyLink,
        sa_relationship_kwargs={"primaryjoin": "Task.id == TaskDependencyLink.depends_on_task_id", 
                              "secondaryjoin": "Task.id == TaskDependencyLink.task_id"}
    )

class Goal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str  # No spaces or '.' allowed
    notes: Optional[str] = None
    state: GoalState
    desired_completion_date: Optional[date] = None
    parent_goal_id: Optional[int] = Field(default=None, foreign_key="goal.id")
    
    # Relationships
    tasks: List["Task"] = Relationship(back_populates="goals", link_model=TaskGoalLink)
    parent_goal: Optional["Goal"] = Relationship(
        sa_relationship_kwargs={"remote_side": "Goal.id"}, 
        back_populates="subgoals"
    )
    subgoals: List["Goal"] = Relationship(back_populates="parent_goal")

class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    start_time: datetime
    duration_minutes: int
    notes: Optional[str] = None
    location: Optional[str] = None

# New Note model for user preferences and information
class Note(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(description="Descriptive title for the note")
    content: str = Field(description="The actual content of the note")
    note_type: NoteType = Field(default=NoteType.general, description="Type of note for categorization")
    is_system_prompt: bool = Field(default=False, description="Whether to include this note in the system prompt")
    created_at: datetime = Field(default_factory=datetime.now, description="When the note was created")
    updated_at: datetime = Field(default_factory=datetime.now, description="When the note was last updated")