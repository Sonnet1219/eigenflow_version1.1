
from __future__ import annotations
from typing_extensions import TypedDict, Annotated
from langgraph.graph import add_messages
from typing import List, Optional, Dict, Any
import operator


class OverallState(TypedDict, total=False):
    """Minimal chat state."""
    messages: Annotated[list, add_messages]


