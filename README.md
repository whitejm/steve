# AI Task & Goal Tracking System

A command-line interface for managing personal tasks and goals with AI assistance.

## Overview

This application helps users track and manage their goals and tasks with a clear, flexible data model supporting personal productivity and goal achievement. It integrates with LiteLLM to provide AI-powered assistance through a simple chat interface.

## Key Features

- Create and manage goals with hierarchical structure
- Track one-time and recurring tasks
- Associate tasks with goals
- Generate recurring task instances from templates
- Natural language interaction with AI assistant

## Project Structure

```
project_root/
├── models/              # Pydantic data models
├── storage/             # Data persistence layer
├── tools/               # Tool definitions for AI operations
├── cli.py               # Command-line interface
├── main.py              # Entry point
├── .env                 # Environment variables (not in git)
├── .gitignore           # Git ignore rules
├── requirements.txt     # Dependencies
└── README.md            # This file
```

## Installation

1. Clone the repository
2. Install the requirements:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Groq API key:
   ```
   GROQ_API_KEY=your_api_key_here
   ```

## Usage

Run the application:

```
python main.py
```

This will start the command-line interface where you can interact with the AI assistant to manage your tasks and goals.

## Data Models

- **Goal**: Hierarchical objectives using dot notation (e.g., "health.run_5k")
- **Task**: Specific actionable items with scheduling, dependencies, and time estimates
- **RecurringTaskTemplate**: Patterns for generating recurring task instances

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the [MIT License](LICENSE).
