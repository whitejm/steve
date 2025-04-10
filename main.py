import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import and run the chat loop
from database import create_db_and_tables
from cli import chat_loop

if __name__ == "__main__":
    # Create database tables if they don't exist
    create_db_and_tables()
    
    # Run the chat interface
    asyncio.run(chat_loop())