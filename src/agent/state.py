
from __future__ import annotations
from typing_extensions import TypedDict, Annotated
from langgraph.graph import add_messages, MessagesState
from langchain_core.messages import AnyMessage
from typing import List, Optional, Dict, Any
import operator
from dataclasses import dataclass


@dataclass
class IntentContext:
    """Enhanced intent context with detailed classification information."""
    schemaVer: str = "dc/v1"
    intent: str = "margin_check"
    confidence: float = 0.0
    slots: Dict[str, Any] = None
    traceId: str = ""
    occurredAt: str = ""
    
    def __post_init__(self):
        if self.slots is None:
            self.slots = {}


class OverallState(TypedDict, total=False):
    """Main graph state managing overall workflow with enhanced intent classification."""
    messages: Annotated[list[AnyMessage], add_messages]
    intentContext: Optional[IntentContext]  # Enhanced intent context with full classification details


class SupervisorState(TypedDict, total=False):
    """Supervisor subgraph state for multi-agent coordination.""" 
    messages: Annotated[list[AnyMessage], add_messages]
    intentContext: Optional[IntentContext]  # Intent context passed from main graph to guide routing


# MessagesState is used directly by individual agents in the supervisor subgraph


