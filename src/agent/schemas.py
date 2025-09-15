from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class IntentScope(BaseModel):
    """Scope information for intent classification."""
    currentLevel: Optional[str] = Field(default="lp", description="Current operation level")
    brokerId: Optional[str] = Field(default=None, description="Broker identifier")
    lp: Optional[str] = Field(default=None, description="LP identifier") 
    group: Optional[str] = Field(default=None, description="Group identifier")


class IntentClassification(BaseModel):
    """Enhanced intent classification result with detailed context."""
    schemaVer: str = Field(default="dc/v1", description="Schema version identifier")
    intent: Literal['chat', 'lp_margin_check_report'] = Field(
        description="The classified user intent"
    )
    confidence: float = Field(description="Classification confidence score (0-1)")
    slots: IntentScope = Field(default_factory=IntentScope, description="Contextual scope information")
    traceId: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique trace identifier")
    occurredAt: str = Field(default_factory=lambda: datetime.now().isoformat() + "Z", description="ISO8601 timestamp of occurrence")


class SupervisorRouting(BaseModel):
    """Supervisor's routing decision."""
    next_agent: Literal['chat_assistant', 'margin_check_assistant', 'FINISH'] = Field(
        description="The next agent to route to or FINISH if task is complete"
    )