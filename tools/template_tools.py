from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
import uuid
from dateutil.rrule import rrulestr
from dateutil.tz import tzlocal

from models import RecurringTaskTemplate, Task, TaskState
from storage import JsonStore
from tools.tool import Tool, tool
from tools.model_utils import create_subset_model


# Parameter models for template operations using the model_utils helper
CreateTemplateParams = create_subset_model(
    RecurringTaskTemplate,
    ["id", "name", "estimated_completion_time", "goals", "rrule", "can_complete_late", "log_instructions"],
    model_name="CreateTemplateParams",
    make_optional=["id", "can_complete_late", "log_instructions"]
)

UpdateTemplateParams = create_subset_model(
    RecurringTaskTemplate,
    ["id", "name", "estimated_completion_time", "goals", "rrule", "can_complete_late", "log_instructions"],
    model_name="UpdateTemplateParams",
    make_optional=["name", "estimated_completion_time", "goals", "rrule", "can_complete_late", "log_instructions"]
)

class GetTemplateParams(BaseModel):
    id: str = Field(description=RecurringTaskTemplate.model_fields["id"].description)

class ListTemplatesParams(BaseModel):
    goal: Optional[str] = None

class DeleteTemplateParams(BaseModel):
    id: str = Field(description=RecurringTaskTemplate.model_fields["id"].description)

class GenerateTasksParams(BaseModel):
    template_id: str
    start_date: datetime
    end_date: datetime


# Create storage instances
template_store = JsonStore(RecurringTaskTemplate, "data/templates.json")
task_store = JsonStore(Task, "data/tasks.json")


# Tool functions
@tool(parameter_model=CreateTemplateParams)
def create_template(name: str, estimated_completion_time: int, goals: List[str], rrule: str,
                    id: Optional[str] = None, can_complete_late: bool = True,
                    log_instructions: Optional[str] = None) -> RecurringTaskTemplate:
    """Create a new recurring task template"""
    if id is None:
        id = str(uuid.uuid4())
        
    template = RecurringTaskTemplate(
        id=id,
        name=name,
        estimated_completion_time=estimated_completion_time,
        goals=goals,
        rrule=rrule,
        can_complete_late=can_complete_late,
        log_instructions=log_instructions
    )
    return template_store.create(template)


@tool(parameter_model=UpdateTemplateParams)
def update_template(id: str, name: Optional[str] = None, estimated_completion_time: Optional[int] = None,
                    goals: Optional[List[str]] = None, rrule: Optional[str] = None,
                    can_complete_late: Optional[bool] = None,
                    log_instructions: Optional[str] = None) -> Optional[RecurringTaskTemplate]:
    """Update an existing recurring task template"""
    existing_template = template_store.get_by_id(id)
    if not existing_template:
        return None
    
    # Update only provided fields
    updated_data = existing_template.model_dump()
    
    update_fields = {
        "name": name,
        "estimated_completion_time": estimated_completion_time,
        "goals": goals,
        "rrule": rrule,
        "can_complete_late": can_complete_late,
        "log_instructions": log_instructions
    }
    
    for field, value in update_fields.items():
        if value is not None:
            updated_data[field] = value
    
    updated_template = RecurringTaskTemplate.model_validate(updated_data)
    return template_store.update(id, updated_template)


@tool(parameter_model=GetTemplateParams)
def get_template(id: str) -> Optional[RecurringTaskTemplate]:
    """Get a recurring task template by ID"""
    return template_store.get_by_id(id)


@tool(parameter_model=ListTemplatesParams)
def list_templates(goal: Optional[str] = None) -> List[RecurringTaskTemplate]:
    """List recurring task templates with optional filtering"""
    
    def filter_func(template: RecurringTaskTemplate) -> bool:
        if goal is not None:
            return goal in template.goals
        return True
    
    return template_store.query(filter_func)


@tool(parameter_model=DeleteTemplateParams)
def delete_template(id: str) -> bool:
    """Delete a recurring task template"""
    return template_store.delete(id)


@tool(parameter_model=GenerateTasksParams)
def generate_tasks(template_id: str, start_date: datetime, end_date: datetime) -> List[Task]:
    """Generate tasks from a recurring template for a date range"""
    template = template_store.get_by_id(template_id)
    if not template:
        raise ValueError(f"Template with ID {template_id} not found")
    
    # Parse the recurrence rule
    rrule_set = rrulestr(template.rrule, dtstart=start_date)
    
    # Get all occurrences in the date range
    occurrences = list(rrule_set.between(start_date, end_date, inc=True))
    
    generated_tasks = []
    for occurrence in occurrences:
        # Check if a task for this occurrence already exists
        existing_tasks = task_store.query(
            lambda t: t.template_id == template_id and t.due_by == occurrence
        )
        
        if not existing_tasks:
            # Create a new task for this occurrence
            task_id = f"{template_id}_{occurrence.strftime('%Y%m%d%H%M%S')}"
            
            task = Task(
                id=task_id,
                name=template.name,
                state=TaskState.INCOMPLETE,
                due_by=occurrence,
                estimated_completion_time=template.estimated_completion_time,
                goals=template.goals,
                template_id=template_id,
                can_complete_late=template.can_complete_late,
                log_instructions=template.log_instructions
            )
            
            generated_task = task_store.create(task)
            generated_tasks.append(generated_task)
    
    return generated_tasks


# Create Tool objects
create_template_tool = Tool("create_template", create_template, CreateTemplateParams, "Create a new recurring task template")
update_template_tool = Tool("update_template", update_template, UpdateTemplateParams, "Update an existing template")
get_template_tool = Tool("get_template", get_template, GetTemplateParams, "Get a template by ID")
list_templates_tool = Tool("list_templates", list_templates, ListTemplatesParams, "List templates with optional filtering")
delete_template_tool = Tool("delete_template", delete_template, DeleteTemplateParams, "Delete a template")
generate_tasks_tool = Tool("generate_tasks", generate_tasks, GenerateTasksParams, "Generate tasks from a template")

# Create template toolset - explicitly defining the variable
template_tools = [
    create_template_tool,
    update_template_tool,
    get_template_tool,
    list_templates_tool,
    delete_template_tool,
    generate_tasks_tool
]