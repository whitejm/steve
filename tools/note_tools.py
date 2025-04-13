from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from sqlmodel import select, Session

from database import engine
from models import Note, NoteType
from tools.tool import Tool, tool


# Parameter models for note operations
class CreateNoteParams(BaseModel):
    title: str = Field(description="Descriptive title for the note")
    content: str = Field(description="The actual content of the note")
    note_type: NoteType = Field(default=NoteType.general, description="Type of note for categorization")
    is_system_prompt: bool = Field(default=False, description="Whether to include this note in the system prompt")

class UpdateNoteParams(BaseModel):
    id: int = Field(description="ID of the note to update")
    title: Optional[str] = Field(default=None, description="Updated title for the note")
    content: Optional[str] = Field(default=None, description="Updated content of the note")
    note_type: Optional[NoteType] = Field(default=None, description="Updated type of note")
    is_system_prompt: Optional[bool] = Field(default=None, description="Updated system prompt inclusion flag")

class GetNoteParams(BaseModel):
    id: int = Field(description="ID of the note to retrieve")

class ListNotesParams(BaseModel):
    note_type: Optional[NoteType] = Field(default=None, description="Filter notes by type")
    is_system_prompt: Optional[bool] = Field(default=None, description="Filter notes by system prompt inclusion")

class DeleteNoteParams(BaseModel):
    id: int = Field(description="ID of the note to delete")


# Tool functions
@tool(parameter_model=CreateNoteParams)
def create_note(title: str, content: str, note_type: NoteType = NoteType.general, 
               is_system_prompt: bool = False) -> Note:
    """Create a new note for user preferences or information"""
    with Session(engine) as session:
        note = Note(
            title=title,
            content=content,
            note_type=note_type,
            is_system_prompt=is_system_prompt,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        session.add(note)
        session.commit()
        session.refresh(note)
        
        return note


@tool(parameter_model=UpdateNoteParams)
def update_note(id: int, title: Optional[str] = None, content: Optional[str] = None,
               note_type: Optional[NoteType] = None, is_system_prompt: Optional[bool] = None) -> Optional[Note]:
    """Update an existing note"""
    with Session(engine) as session:
        note = session.get(Note, id)
        if not note:
            return None
        
        # Update provided fields
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        if note_type is not None:
            note.note_type = note_type
        if is_system_prompt is not None:
            note.is_system_prompt = is_system_prompt
            
        # Always update the updated_at timestamp
        note.updated_at = datetime.now()
        
        session.add(note)
        session.commit()
        session.refresh(note)
        
        return note


@tool(parameter_model=GetNoteParams)
def get_note(id: int) -> Optional[Note]:
    """Get a note by ID"""
    with Session(engine) as session:
        note = session.get(Note, id)
        if not note:
            return None
        return note


@tool(parameter_model=ListNotesParams)
def list_notes(note_type: Optional[NoteType] = None, is_system_prompt: Optional[bool] = None) -> List[Note]:
    """List notes with optional filtering"""
    with Session(engine) as session:
        query = select(Note)
        
        if note_type is not None:
            query = query.where(Note.note_type == note_type)
        
        if is_system_prompt is not None:
            query = query.where(Note.is_system_prompt == is_system_prompt)
        
        results = session.exec(query).all()
        return list(results)


@tool(parameter_model=DeleteNoteParams)
def delete_note(id: int) -> bool:
    """Delete a note"""
    with Session(engine) as session:
        note = session.get(Note, id)
        if not note:
            return False
        
        session.delete(note)
        session.commit()
        return True


# Create Tool objects
create_note_tool = Tool("create_note", create_note, CreateNoteParams, "Create a new note for user preferences or information")
update_note_tool = Tool("update_note", update_note, UpdateNoteParams, "Update an existing note")
get_note_tool = Tool("get_note", get_note, GetNoteParams, "Get a note by ID")
list_notes_tool = Tool("list_notes", list_notes, ListNotesParams, "List notes with optional filtering")
delete_note_tool = Tool("delete_note", delete_note, DeleteNoteParams, "Delete a note")

# Create note toolset
note_tools = [
    create_note_tool,
    update_note_tool,
    get_note_tool,
    list_notes_tool,
    delete_note_tool
]