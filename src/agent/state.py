
from __future__ import annotations
from typing_extensions import TypedDict, Annotated
from langgraph.graph import add_messages, MessagesState
from typing import List, Optional, Dict, Any
import operator


class OverallState(TypedDict, total=False):
    """Multi-agent workflow state extending MessagesState."""
    messages: Annotated[list, add_messages]
    intent: Optional[str]  # Classified user intent
    next_agent: Optional[str]  # Next agent to route to
    margin_data: Optional[Dict[str, Any]]  # Margin check results
    task_complete: Optional[bool]  # Whether the current task is finished


# For compatibility with the new Command pattern workflow
# We can use MessagesState directly which includes messages field


