from pydantic import BaseModel, Field
from enum import Enum
from typing import List


class GoalState(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    PAUSED = "paused"


class Goal(BaseModel):
    name: str = Field(
        description="Identifier using dot notation for hierarchy (no spaces). Example: 'health.run_5k'"
    )
    short_description: str = Field(
        description="Brief summary of the goal"
    )
    long_description: str = Field(
        description="Detailed explanation of the goal, its purpose, and how to achieve it"
    )
    state: GoalState = Field(
        default=GoalState.ACTIVE,
        description="Current status of the goal (active, completed, abandoned, or paused)"
    )