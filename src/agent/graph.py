"""Multi-agent supervisor workflow using prebuilt components from LangGraph"""

import os
from typing import Annotated

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph_supervisor.handoff import create_forward_message_tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from src.agent.prompts import (
    CHAT_ASSISTANT_PROMPT,
    MARGIN_CHECK_ASSISTANT_PROMPT,
    SUPERVISOR_PROMPT
)
from src.agent.utils import chat_response
from src.agent.mcp import get_lp_margin_report


def get_model():
    """Get configured ChatOpenAI model instance."""
    return ChatOpenAI(
        model=os.getenv("MODEL_NAME", "qwen-plus"),
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0.5
    )


# Create handoff tools for supervisor communication
def create_handoff_tool(*, agent_name: str, description: str | None = None):
    """Create handoff tool for supervisor to delegate tasks to worker agents."""
    name = f"transfer_to_{agent_name}"
    description = description or f"Transfer task to {agent_name}."

    @tool(name, description=description)
    def handoff_tool(
        state: Annotated[MessagesState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        tool_message = {
            "role": "tool",
            "content": f"Successfully transferred to {agent_name}",
            "name": name,
            "tool_call_id": tool_call_id,
        }
        return Command(
            goto=agent_name,
            update={**state, "messages": state["messages"] + [tool_message]},
            graph=Command.PARENT,
        )

    return handoff_tool


# Create handoff tools
transfer_to_chat_assistant = create_handoff_tool(
    agent_name="chat_assistant",
    description="Transfer to chat assistant for general conversations and questions.",
)

transfer_to_margin_assistant = create_handoff_tool(
    agent_name="margin_assistant", 
    description="Transfer to margin assistant for LP margin checking and reporting tasks.",
)


# Worker agents and supervisor will be created when module loads
def create_agents():
    """Create worker agents and supervisor agent."""
    model = get_model()
    
    # Create worker agents using create_react_agent
    chat_assistant = create_react_agent(
        model=model,
        tools=[chat_response],
        prompt=CHAT_ASSISTANT_PROMPT,
        name="chat_assistant"
    )

    margin_assistant = create_react_agent(
        model=model,
        tools=[get_lp_margin_report],
        prompt=MARGIN_CHECK_ASSISTANT_PROMPT,
        name="margin_assistant"
    )

    return chat_assistant, margin_assistant


# ref：https://github.com/langchain-ai/langgraph-supervisor-py#customizing-handoff-tools
try:
    model = get_model()
    chat_assistant, margin_assistant = create_agents()

    forwarding_tool = create_forward_message_tool("supervisor") # The argument is the name to assign to the resulting forwarded message

    # Create supervisor 
    graph = create_supervisor(
        [chat_assistant, margin_assistant],
        model=model,
        prompt=SUPERVISOR_PROMPT,
        add_handoff_messages=False,   # Don't add handoff messages to conversation history
        output_mode="last_message",   # Return only the last message from the active agent
        tools=[forwarding_tool]       # Supervisor can use forwarding tool to pass messages between agents
    )

except Exception as e:
    # If API key is not available, create placeholder objects
    print(f"Warning: Could not create agents during module import: {e}")
    graph = None
    


async def build_graph(checkpointer, store=None):
    """
    Compiles the graph with the given checkpointer and memory store.
    
    Args:
        checkpointer: AsyncPostgresSaver instance for checkpointing
        store: AsyncPostgresStore instance for memory storage (optional)
    
    Returns:
        Compiled graph instance
    """
    return graph.compile(
        checkpointer=checkpointer,
        store=store
    )