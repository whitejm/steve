import os
import asyncio

# Check if data directory exists, create if not
if not os.path.exists("data"):
    os.makedirs("data")

# Ensure JSON files exist
data_files = ["goals.json", "tasks.json", "templates.json"]
for file in data_files:
    file_path = os.path.join("data", file)
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("[]")

# Import and run the chat loop
from cli import chat_loop

if __name__ == "__main__":
    asyncio.run(chat_loop())