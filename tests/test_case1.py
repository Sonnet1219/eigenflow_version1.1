from src.agent.schemas import IntentContext
from langchain.schema import HumanMessage, SystemMessage
from src.agent.graph import build_graph


async def async_main():
    thread_id = "test_thread_1"
    messages = HumanMessage("帮我生成lp的风险报告\n")
    config = {"configurable": {"thread_id": thread_id}}
    intent_context = IntentContext(
        intent="lp_margin_check_report",
        confidence=1.0,
        #slots={"lp": lp_name},  # Pass lp_name for direct filtering
        traceId=thread_id,
    )

    initial_state = {
        "messages": messages,
        "intentContext": intent_context
    }

    graph = await build_graph(checkpointer=None)
    result = await graph.ainvoke(initial_state, config=config)
    print("Final Result:", result)


if __name__ == "__main__":
    import asyncio
    asyncio.run(async_main())
