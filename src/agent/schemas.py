from typing import List, Literal
from pydantic import BaseModel, Field

class IntentClassification(BaseModel):
    """Intent classification result."""
    intent: Literal['chat', 'lp_margin_check_report'] = Field(
        description="The classified user intent"
    )

class SupervisorRouting(BaseModel):
    """Supervisor's routing decision."""
    next_agent: Literal['chat_assistant', 'margin_check_assistant', 'FINISH'] = Field(
        description="The next agent to route to or FINISH if task is complete"
    )