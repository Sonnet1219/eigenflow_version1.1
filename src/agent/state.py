
from __future__ import annotations
from typing_extensions import TypedDict, Annotated
from langgraph.graph import add_messages, MessagesState
from langchain_core.messages import AnyMessage
from typing import List, Optional, Dict, Any
import operator


class OverallState(TypedDict, total=False):
    """Main graph state managing overall workflow with intent classification."""
    messages: Annotated[list[AnyMessage], add_messages]
    intent: Optional[str]  # Classified user intent: 'chat', 'margin_check', or 'unknown'


class SupervisorState(TypedDict, total=False):
    """Supervisor subgraph state for multi-agent coordination.""" 
    messages: Annotated[list[AnyMessage], add_messages]
    intent: Optional[str]  # Intent passed from main graph to guide routing


# MessagesState is used directly by individual agents in the supervisor subgraph


