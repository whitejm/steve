from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskState(str, Enum):
    INCOMPLETE = "incomplete"
    COMPLETED = "completed"
    CANCELED = "canceled"
    MISSED = "missed"


class RecurringTaskTemplate(BaseModel):
    id: str = Field(
        description="Unique identifier for the recurring task template"
    )
    name: str = Field(
        description="Short descriptive title of the recurring task"
    )
    estimated_completion_time: int = Field(
        description="Estimated time required to complete each instance of this task, in minutes"
    )
    goals: List[str] = Field(
        description="References to Goal entities this recurring task contributes toward (must be provided as a list/array, even for a single goal)"
    )
    rrule: str = Field(
        description="Recurrence rule for generating recurring instances of this task"
    )
    can_complete_late: bool = Field(
        default=True,
        description="Whether task instances can be marked as complete after their due date has passed"
    )
    log_instructions: Optional[str] = Field(
        default=None,
        description="Guidelines for what information should be captured in the log and how it should be formatted"
    )


class Task(BaseModel):
    id: str = Field(
        description="Unique identifier for the task"
    )
    state: TaskState = Field(
        default=TaskState.INCOMPLETE,
        description="Current status of the task (incomplete, completed, canceled, or missed)"
    )
    name: str = Field(
        description="Short descriptive title of the specific action to be completed"
    )
    schedule_on_or_after: Optional[datetime] = Field(
        default=None,
        description="The earliest date this task should appear on your schedule. Tasks won't be shown before this date. If not set (None), the task is available to schedule at any time."
    )
    due_by: Optional[datetime] = Field(
        default=None,
        description="Deadline by which the task must be completed"
    )
    estimated_completion_time: int = Field(
        description="Estimated time required to complete the task, in minutes"
    )
    actual_completion_time: Optional[int] = Field(
        default=None,
        description="Actual time taken to complete the task, in minutes"
    )
    goals: List[str] = Field(
        description="References to Goal entities this recurring task contributes toward (must be provided as a list/array, even for a single goal)"
    )
    depends_on: Optional[List[str]] = Field(
        default=None,
        description="IDs of tasks that must be completed before this task can be started"
    )
    template_id: Optional[str] = Field(
        default=None,
        description="ID of the recurring task template this task was generated from"
    )
    can_complete_late: bool = Field(
        default=True,
        description="Whether the task can be marked as complete after its due date has passed"
    )
    log: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured data for tracking progress, metrics, or results of the task"
    )
    log_instructions: Optional[str] = Field(
        default=None,
        description="Guidelines for what information should be captured in the log and how it should be formatted"
    )
    
    @field_validator('depends_on')
    def no_dependencies_for_recurring_task_instances(cls, value, info):
        template_id = info.data.get('template_id')
        if value and template_id and len(value) > 0:
            raise ValueError("Recurring task instances cannot have dependencies")
        return value