"""Projects and the memory of their meetings."""

from meetingtool.projects.store import (
    ProjectError,
    add_meeting,
    create_project,
    default_data_dir,
    knowledge_context,
    list_meetings,
    list_projects,
)

__all__ = [
    "ProjectError",
    "add_meeting",
    "create_project",
    "default_data_dir",
    "knowledge_context",
    "list_meetings",
    "list_projects",
]
