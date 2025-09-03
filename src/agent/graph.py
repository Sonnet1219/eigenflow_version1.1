"""Multi-agent supervisor workflow using prebuilt components from LangGraph"""

import os
from typing import Annotated

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
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

    # Create supervisor agent using create_react_agent
    supervisor_agent = create_react_agent(
        model=model,
        tools=[transfer_to_chat_assistant, transfer_to_margin_assistant],
        prompt=SUPERVISOR_PROMPT,
        name="supervisor"
    )
    
    return supervisor_agent, chat_assistant, margin_assistant


# Create agents - this will be done on module import
# Note: This requires API key to be set before import
try:
    supervisor_agent, chat_assistant, margin_assistant = create_agents()
    
    # Build multi-agent supervisor graph
    builder = StateGraph(MessagesState)
    builder.add_node(supervisor_agent, destinations=("chat_assistant", "margin_assistant", END))
    builder.add_node(chat_assistant)
    builder.add_node(margin_assistant)
    builder.add_edge(START, "supervisor")
    # Worker agents always return to supervisor
    builder.add_edge("chat_assistant", "supervisor")
    builder.add_edge("margin_assistant", "supervisor")
    
    # Compile default graph
    graph = builder.compile()
    
except Exception as e:
    # If API key is not available, create placeholder objects
    print(f"Warning: Could not create agents during module import: {e}")
    builder = None
    graph = None
    


def build_graph(checkpointer, store=None):
    """
    Compiles the graph with the given checkpointer and memory store.
    
    Args:
        checkpointer: AsyncPostgresSaver instance for checkpointing
        store: AsyncPostgresStore instance for memory storage (optional)
    
    Returns:
        Compiled graph instance
    """
    return builder.compile(
        checkpointer=checkpointer,
        store=store
    )