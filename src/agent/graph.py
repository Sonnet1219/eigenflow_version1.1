"""Multi-agent supervisor workflow using prebuilt components from LangGraph with main graph + subgraph architecture"""

import os
import json
from typing import Annotated

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph_supervisor.handoff import create_forward_message_tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from langchain_core.messages import HumanMessage

from src.agent.state import OverallState, SupervisorState, IntentContext
from src.agent.schemas import IntentClassification
from src.agent.prompts import (
    CHAT_ASSISTANT_PROMPT,
    MARGIN_CHECK_ASSISTANT_PROMPT,
    SUPERVISOR_PROMPT,
    INTENT_CLASSIFICATION_PROMPT
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


async def classify_intent(state: OverallState) -> OverallState:
    """Classify user intent using LLM with enhanced structured output."""
    try:
        model = get_model()
        
        # Get the latest user message
        messages = state.get("messages", [])
        if not messages:
            # Return default intent context for empty messages
            default_context = IntentContext()
            return {"intentContext": default_context}
            
        latest_message = messages[-1]
        user_input = latest_message.content if hasattr(latest_message, 'content') else str(latest_message)
        
        # Use structured output for intent classification
        structured_model = model.with_structured_output(IntentClassification)
        
        # Use the predefined prompt from prompts.py with user input formatting
        formatted_prompt = INTENT_CLASSIFICATION_PROMPT.format(user_input=user_input)
        
        result = await structured_model.ainvoke([HumanMessage(content=formatted_prompt)])
        
        # Convert Pydantic model to IntentContext dataclass
        intent_context = IntentContext(
            schemaVer=result.schemaVer,
            intent=result.intent,
            confidence=result.confidence,
            slots=result.slots.dict() if result.slots else {},
            traceId=result.traceId,
            occurredAt=result.occurredAt
        )
        
        return {"intentContext": intent_context}
        
    except Exception as e:
        print(f"Error in intent classification: {e}")
        # Return default chat intent context on error
        default_context = IntentContext(intent="chat", confidence=0.5)
        return {"intentContext": default_context}


async def call_supervisor(state: OverallState) -> OverallState:
    """Call supervisor subgraph with transformed state."""
    try:
        # Transform OverallState to SupervisorState
        supervisor_input = {
            "messages": state.get("messages", []),
            "intentContext": state.get("intentContext", IntentContext())
        }
        
        # Invoke supervisor subgraph
        result = await supervisor_subgraph.ainvoke(supervisor_input)
        
        # Transform result back to OverallState
        return {"messages": result.get("messages", [])}
        
    except Exception as e:
        print(f"Error calling supervisor subgraph: {e}")
        # Return original messages if subgraph fails
        return {"messages": state.get("messages", [])}


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


# Worker agents and supervisor subgraph creation
def create_supervisor_subgraph():
    """Create supervisor subgraph with worker agents."""
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

    forwarding_tool = create_forward_message_tool("supervisor")

    # Create supervisor subgraph and compile it
    supervisor = create_supervisor(
        [chat_assistant, margin_assistant],
        model=model,
        prompt=SUPERVISOR_PROMPT,
        add_handoff_messages=False,   # Don't add handoff messages to conversation history
        output_mode="last_message",   # Return only the last message from the active agent
        tools=[forwarding_tool]       # Supervisor can use forwarding tool to pass messages between agents
    )
    
    # Compile the supervisor subgraph so it has ainvoke method
    return supervisor.compile()


def create_main_graph():
    """Create main graph with intent classification and supervisor subgraph."""
    # Create the main graph with OverallState
    builder = StateGraph(OverallState)
    
    # Add intent classification node
    builder.add_node("classify_intent", classify_intent)
    
    # Add supervisor subgraph call node  
    builder.add_node("call_supervisor", call_supervisor)
    
    # Define the flow: START -> classify_intent -> call_supervisor -> END
    builder.add_edge(START, "classify_intent")
    builder.add_edge("classify_intent", "call_supervisor")
    builder.add_edge("call_supervisor", END)
    
    return builder


# Initialize components when module loads
try:
    model = get_model()
    supervisor_subgraph = create_supervisor_subgraph()
    graph = create_main_graph()

except Exception as e:
    # If API key is not available, create placeholder objects
    print(f"Warning: Could not create graphs during module import: {e}")
    supervisor_subgraph = None
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