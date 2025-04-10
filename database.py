from sqlmodel import SQLModel, create_engine, Session
import os
from typing import Generator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database connection details from environment variables or use defaults
DB_USER = os.getenv("DB_USER", "aicoach_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "yourpassword")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "aicoach")

# Create the SQLAlchemy engine
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, echo=False)

def create_db_and_tables():
    """Create database tables from SQLModel classes"""
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    """Get a database session"""
    with Session(engine) as session:
        yield session
        
        
        