"""API endpoints for chat operations using multi-agent supervisor."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    """Chat request body for multi-agent system."""
    text: str = Field(..., description="User input text")
    thread_id: Optional[str] = Field(default=None, description="Optional thread id")
    model: Optional[str] = Field(default=None, description="Optional override model name")


class ChatResponse(BaseModel):
    """Chat response body."""
    reply: str
    agent_used: Optional[str] = Field(default=None, description="Which agent handled the request")


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request, body: ChatRequest) -> ChatResponse:
    """Execute chat via multi-agent supervisor and return assistant reply."""
    try:
        graph = request.app.state.graph

        initial_state = {"messages": [HumanMessage(content=body.text)]}
        
        # Provide thread_id and optional model override
        config = {"configurable": {"thread_id": body.thread_id or "chat_default"}}
        if body.model:
            config["configurable"]["model"] = body.model

        # Invoke the multi-agent graph
        result = await graph.ainvoke(initial_state, config=config)
        
        messages = result.get("messages", [])
        if not messages:
            raise HTTPException(status_code=500, detail="No response from multi-agent system")

        # Get the final assistant response
        # The last message should be from one of the assistants
        final_message = messages[-1]
        reply = getattr(final_message, "content", "") or ""
        
        # Try to determine which agent was used based on the conversation flow
        agent_used = None
        for message in reversed(messages):
            if hasattr(message, "name") and message.name:
                if "chat_assistant" in message.name:
                    agent_used = "chat_assistant"
                    break
                elif "margin_assistant" in message.name:
                    agent_used = "margin_assistant"
                    break
        
        return ChatResponse(reply=reply, agent_used=agent_used)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-agent chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")