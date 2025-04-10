from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from sqlmodel import select, Session
import uuid
from dateutil.rrule import rrulestr

from database import engine
from models import Task, TaskState, TaskPriority, Goal, TaskGoalLink, TaskDependencyLink
from tools.tool import Tool, tool


# Parameter models for task operations
class CreateTaskParams(BaseModel):
    name: str = Field(description="Short descriptive title for the task")
    priority: TaskPriority = Field(description="Priority level of the task")
    estimated_completion_time_minutes: int = Field(description="Estimated time needed to complete the task, in minutes")
    notes: Optional[str] = Field(default=None, description="Additional notes or instructions for the task")
    state: TaskState = Field(default=TaskState.incomplete, description="Current state of the task")
    schedule_on_or_after: Optional[datetime] = Field(default=None, description="Earliest date to schedule this task")
    scheduled_at: Optional[datetime] = Field(default=None, description="Specific date and time when the task is scheduled")
    due: Optional[datetime] = Field(default=None, description="Deadline for the task")
    scheduling_notes: Optional[str] = Field(default=None, description="Notes about scheduling preferences")
    mark_missed_after_days_overdue: Optional[int] = Field(default=0, description="Days after which an overdue task is automatically marked missed (0 or None means never)")
    goal_ids: Optional[List[int]] = Field(default=None, description="IDs of goals this task is associated with")
    depends_on_task_ids: Optional[List[int]] = Field(default=None, description="IDs of tasks that must be completed before this one")
    rrule: Optional[str] = Field(default=None, description="Recurrence rule for generating recurring instances (iCalendar RRULE format)")

class UpdateTaskParams(BaseModel):
    id: int = Field(description="ID of the task to update")
    name: Optional[str] = Field(default=None, description="Updated task title")
    priority: Optional[TaskPriority] = Field(default=None, description="Updated priority level")
    estimated_completion_time_minutes: Optional[int] = Field(default=None, description="Updated time estimate in minutes")
    actual_completion_time_minutes: Optional[int] = Field(default=None, description="Actual time taken to complete the task, in minutes")
    notes: Optional[str] = Field(default=None, description="Updated task notes")
    state: Optional[TaskState] = Field(default=None, description="Updated task state")
    schedule_on_or_after: Optional[datetime] = Field(default=None, description="Updated earliest schedule date")
    scheduled_at: Optional[datetime] = Field(default=None, description="Updated scheduled time")
    due: Optional[datetime] = Field(default=None, description="Updated deadline")
    scheduling_notes: Optional[str] = Field(default=None, description="Updated scheduling notes")
    mark_missed_after_days_overdue: Optional[int] = Field(default=None, description="Updated days until marked missed")
    goal_ids: Optional[List[int]] = Field(default=None, description="Updated list of associated goal IDs")
    add_goal_ids: Optional[List[int]] = Field(default=None, description="Goal IDs to add to this task")
    remove_goal_ids: Optional[List[int]] = Field(default=None, description="Goal IDs to remove from this task")
    depends_on_task_ids: Optional[List[int]] = Field(default=None, description="Updated list of prerequisite task IDs")
    add_dependency_ids: Optional[List[int]] = Field(default=None, description="Task IDs to add as dependencies")
    remove_dependency_ids: Optional[List[int]] = Field(default=None, description="Task IDs to remove as dependencies")

class GetTaskParams(BaseModel):
    id: int = Field(description="ID of the task to retrieve")

class ListTasksParams(BaseModel):
    state: Optional[TaskState] = Field(default=None, description="Filter tasks by state")
    priority: Optional[TaskPriority] = Field(default=None, description="Filter tasks by priority")
    goal_id: Optional[int] = Field(default=None, description="Filter tasks associated with a specific goal")
    due_before: Optional[datetime] = Field(default=None, description="Filter tasks due before this date")
    due_after: Optional[datetime] = Field(default=None, description="Filter tasks due after this date")
    scheduled_on: Optional[datetime] = Field(default=None, description="Filter tasks scheduled on this date")
    template_id: Optional[int] = Field(default=None, description="Filter tasks created from a specific template")

class DeleteTaskParams(BaseModel):
    id: int = Field(description="ID of the task to delete")

class CompleteTaskParams(BaseModel):
    id: int = Field(description="ID of the task to mark as complete")
    actual_completion_time_minutes: Optional[int] = Field(default=None, description="Actual time taken to complete the task, in minutes")
    completion_notes: Optional[str] = Field(default=None, description="Notes about task completion")


# Tool functions
@tool(parameter_model=CreateTaskParams)
def create_task(name: str, priority: TaskPriority, estimated_completion_time_minutes: int,
                notes: Optional[str] = None, state: TaskState = TaskState.incomplete,
                schedule_on_or_after: Optional[datetime] = None, scheduled_at: Optional[datetime] = None,
                due: Optional[datetime] = None, scheduling_notes: Optional[str] = None,
                mark_missed_after_days_overdue: Optional[int] = 0,
                goal_ids: Optional[List[int]] = None, depends_on_task_ids: Optional[List[int]] = None,
                rrule: Optional[str] = None) -> Task:
    """Create a new task"""
    with Session(engine) as session:
        # Validate goal IDs if provided
        if goal_ids:
            for goal_id in goal_ids:
                goal = session.get(Goal, goal_id)
                if not goal:
                    raise ValueError(f"Goal with ID {goal_id} does not exist")
        
        # Validate dependency task IDs if provided
        if depends_on_task_ids:
            for task_id in depends_on_task_ids:
                dependency = session.get(Task, task_id)
                if not dependency:
                    raise ValueError(f"Dependency task with ID {task_id} does not exist")
        
        # Create the new task
        task = Task(
            name=name,
            priority=priority,
            estimated_completion_time_minutes=estimated_completion_time_minutes,
            notes=notes,
            state=state,
            schedule_on_or_after=schedule_on_or_after,
            scheduled_at=scheduled_at,
            due=due,
            scheduling_notes=scheduling_notes,
            mark_missed_after_days_overdue=mark_missed_after_days_overdue,
            rrule=rrule
        )
        
        session.add(task)
        session.commit()
        session.refresh(task)
        
        # Add goals if provided
        if goal_ids:
            for goal_id in goal_ids:
                link = TaskGoalLink(task_id=task.id, goal_id=goal_id)
                session.add(link)
        
        # Add dependencies if provided
        if depends_on_task_ids:
            for dep_id in depends_on_task_ids:
                link = TaskDependencyLink(task_id=task.id, depends_on_task_id=dep_id)
                session.add(link)
        
        # Handle recurring task generation if rrule is provided
        if rrule:
            # Store the original task as a template
            task.rrule = rrule
            session.add(task)
            session.commit()
            
            # Generate instances for the next year
            start_date = datetime.now()
            end_date = start_date + timedelta(days=365)
            
            try:
                # Parse the recurrence rule
                rule_set = rrulestr(rrule, dtstart=start_date)
                
                # Get occurrences in the date range
                occurrences = list(rule_set.between(start_date, end_date, inc=True))
                
                # Create instances
                for occurrence in occurrences:
                    instance = Task(
                        name=name,
                        priority=priority,
                        estimated_completion_time_minutes=estimated_completion_time_minutes,
                        notes=notes,
                        state=state,
                        scheduled_at=occurrence,
                        due=occurrence,  # Default to same as scheduled time
                        scheduling_notes=scheduling_notes,
                        mark_missed_after_days_overdue=mark_missed_after_days_overdue,
                        rrule_template_id=task.id
                    )
                    session.add(instance)
                    
                    # Link to the same goals
                    if goal_ids:
                        for goal_id in goal_ids:
                            link = TaskGoalLink(task_id=instance.id, goal_id=goal_id)
                            session.add(link)
            except Exception as e:
                # If there's an error parsing the rrule, still save the task
                # but log the error
                print(f"Error generating recurring tasks: {str(e)}")
        
        session.commit()
        return task


@tool(parameter_model=UpdateTaskParams)
def update_task(id: int, name: Optional[str] = None, priority: Optional[TaskPriority] = None,
                estimated_completion_time_minutes: Optional[int] = None, 
                actual_completion_time_minutes: Optional[int] = None,
                notes: Optional[str] = None, state: Optional[TaskState] = None,
                schedule_on_or_after: Optional[datetime] = None, 
                scheduled_at: Optional[datetime] = None,
                due: Optional[datetime] = None, scheduling_notes: Optional[str] = None,
                mark_missed_after_days_overdue: Optional[int] = None,
                goal_ids: Optional[List[int]] = None,
                add_goal_ids: Optional[List[int]] = None,
                remove_goal_ids: Optional[List[int]] = None,
                depends_on_task_ids: Optional[List[int]] = None,
                add_dependency_ids: Optional[List[int]] = None,
                remove_dependency_ids: Optional[List[int]] = None) -> Optional[Task]:
    """Update an existing task"""
    with Session(engine) as session:
        task = session.get(Task, id)
        if not task:
            return None
        
        # Update basic fields if provided
        if name is not None:
            task.name = name
        if priority is not None:
            task.priority = priority
        if estimated_completion_time_minutes is not None:
            task.estimated_completion_time_minutes = estimated_completion_time_minutes
        if actual_completion_time_minutes is not None:
            task.actual_completion_time_minutes = actual_completion_time_minutes
        if notes is not None:
            task.notes = notes
        if state is not None:
            task.state = state
        if schedule_on_or_after is not None:
            task.schedule_on_or_after = schedule_on_or_after
        if scheduled_at is not None:
            task.scheduled_at = scheduled_at
        if due is not None:
            task.due = due
        if scheduling_notes is not None:
            task.scheduling_notes = scheduling_notes
        if mark_missed_after_days_overdue is not None:
            task.mark_missed_after_days_overdue = mark_missed_after_days_overdue
        
        # Update goals if a complete replacement list is provided
        if goal_ids is not None:
            # Validate all goals exist
            for goal_id in goal_ids:
                goal = session.get(Goal, goal_id)
                if not goal:
                    raise ValueError(f"Goal with ID {goal_id} does not exist")
            
            # Remove existing links
            links_query = select(TaskGoalLink).where(TaskGoalLink.task_id == id)
            existing_links = session.exec(links_query).all()
            for link in existing_links:
                session.delete(link)
            
            # Add new links
            for goal_id in goal_ids:
                link = TaskGoalLink(task_id=id, goal_id=goal_id)
                session.add(link)
        
        # Add goals if specified
        if add_goal_ids:
            # Get existing goal links to avoid duplicates
            links_query = select(TaskGoalLink).where(TaskGoalLink.task_id == id)
            existing_links = {link.goal_id for link in session.exec(links_query).all()}
            
            for goal_id in add_goal_ids:
                if goal_id not in existing_links:
                    goal = session.get(Goal, goal_id)
                    if not goal:
                        raise ValueError(f"Goal with ID {goal_id} does not exist")
                    
                    link = TaskGoalLink(task_id=id, goal_id=goal_id)
                    session.add(link)
        
        # Remove goals if specified
        if remove_goal_ids:
            for goal_id in remove_goal_ids:
                link_query = select(TaskGoalLink).where(
                    TaskGoalLink.task_id == id, 
                    TaskGoalLink.goal_id == goal_id
                )
                link = session.exec(link_query).first()
                if link:
                    session.delete(link)
        
        # Similar logic for dependencies
        if depends_on_task_ids is not None:
            # Validate tasks exist
            for task_id in depends_on_task_ids:
                dependency = session.get(Task, task_id)
                if not dependency:
                    raise ValueError(f"Dependency task with ID {task_id} does not exist")
                if task_id == id:
                    raise ValueError("A task cannot depend on itself")
            
            # Remove existing dependencies
            deps_query = select(TaskDependencyLink).where(TaskDependencyLink.task_id == id)
            existing_deps = session.exec(deps_query).all()
            for dep in existing_deps:
                session.delete(dep)
            
            # Add new dependencies
            for dep_id in depends_on_task_ids:
                link = TaskDependencyLink(task_id=id, depends_on_task_id=dep_id)
                session.add(link)
        
        # Add dependencies
        if add_dependency_ids:
            deps_query = select(TaskDependencyLink).where(TaskDependencyLink.task_id == id)
            existing_deps = {dep.depends_on_task_id for dep in session.exec(deps_query).all()}
            
            for dep_id in add_dependency_ids:
                if dep_id not in existing_deps:
                    if dep_id == id:
                        raise ValueError("A task cannot depend on itself")
                    
                    dependency = session.get(Task, dep_id)
                    if not dependency:
                        raise ValueError(f"Dependency task with ID {dep_id} does not exist")
                    
                    link = TaskDependencyLink(task_id=id, depends_on_task_id=dep_id)
                    session.add(link)
        
        # Remove dependencies
        if remove_dependency_ids:
            for dep_id in remove_dependency_ids:
                dep_query = select(TaskDependencyLink).where(
                    TaskDependencyLink.task_id == id,
                    TaskDependencyLink.depends_on_task_id == dep_id
                )
                dep = session.exec(dep_query).first()
                if dep:
                    session.delete(dep)
        
        session.commit()
        session.refresh(task)
        return task


@tool(parameter_model=GetTaskParams)
def get_task(id: int) -> Optional[Task]:
    """Get a task by ID"""
    with Session(engine) as session:
        task = session.get(Task, id)
        return task


@tool(parameter_model=ListTasksParams)
def list_tasks(state: Optional[TaskState] = None, priority: Optional[TaskPriority] = None,
               goal_id: Optional[int] = None, due_before: Optional[datetime] = None,
               due_after: Optional[datetime] = None, scheduled_on: Optional[datetime] = None,
               template_id: Optional[int] = None) -> List[Task]:
    """List tasks with optional filtering"""
    with Session(engine) as session:
        query = select(Task)
        
        # Apply filters
        if state is not None:
            query = query.where(Task.state == state)
        
        if priority is not None:
            query = query.where(Task.priority == priority)
        
        if due_before is not None:
            query = query.where(Task.due < due_before)
        
        if due_after is not None:
            query = query.where(Task.due > due_after)
        
        if scheduled_on is not None:
            # For date comparison, consider the entire day
            start_of_day = scheduled_on.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            query = query.where(Task.scheduled_at >= start_of_day, Task.scheduled_at < end_of_day)
        
        if template_id is not None:
            query = query.where(Task.rrule_template_id == template_id)
        
        # Handle goal filtering separately since it's a many-to-many relationship
        results = session.exec(query).all()
        
        if goal_id is not None:
            # Filter tasks associated with the specified goal
            filtered_results = []
            goal_links_query = select(TaskGoalLink).where(TaskGoalLink.goal_id == goal_id)
            task_ids_with_goal = {link.task_id for link in session.exec(goal_links_query).all()}
            
            for task in results:
                if task.id in task_ids_with_goal:
                    filtered_results.append(task)
            
            return filtered_results
        
        return list(results)


@tool(parameter_model=DeleteTaskParams)
def delete_task(id: int) -> bool:
    """Delete a task"""
    with Session(engine) as session:
        task = session.get(Task, id)
        if not task:
            return False
        
        # Check if this is a template with instances
        if task.instances:
            raise ValueError(f"Cannot delete task with ID {id} because it is a template with instances. Delete the instances first or update the task instead.")
        
        # Delete associated goal links
        goal_links_query = select(TaskGoalLink).where(TaskGoalLink.task_id == id)
        goal_links = session.exec(goal_links_query).all()
        for link in goal_links:
            session.delete(link)
        
        # Delete associated dependency links (both ways)
        dep_links_query = select(TaskDependencyLink).where(
            (TaskDependencyLink.task_id == id) | (TaskDependencyLink.depends_on_task_id == id)
        )
        dep_links = session.exec(dep_links_query).all()
        for link in dep_links:
            session.delete(link)
        
        # Delete the task
        session.delete(task)
        session.commit()
        return True


@tool(parameter_model=CompleteTaskParams)
def complete_task(id: int, actual_completion_time_minutes: Optional[int] = None,
                 completion_notes: Optional[str] = None) -> Optional[Task]:
    """Mark a task as complete with actual time and completion notes"""
    with Session(engine) as session:
        task = session.get(Task, id)
        if not task:
            return None
        
        # Update task state and completion data
        task.state = TaskState.completed
        
        if actual_completion_time_minutes is not None:
            task.actual_completion_time_minutes = actual_completion_time_minutes
        
        # Append completion notes to existing notes
        if completion_notes:
            if task.notes:
                task.notes = f"{task.notes}\n\nCompletion: {completion_notes}"
            else:
                task.notes = f"Completion: {completion_notes}"
        
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


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