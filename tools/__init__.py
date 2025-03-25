from tools.tool import Tool, ToolSet, tool
from tools.goal_tools import goal_tools
from tools.task_tools import task_tools
from tools.template_tools import template_tools

# Combine all tools into a single toolset
all_tools = goal_tools + task_tools + template_tools
toolset = ToolSet(all_tools)

__all__ = [
    'Tool',
    'ToolSet',
    'tool',
    'goal_tools',
    'task_tools',
    'template_tools',
    'toolset'
]