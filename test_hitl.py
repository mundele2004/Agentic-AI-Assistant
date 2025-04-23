from langchain_core.messages import HumanMessage
from langgraph_mcp_backend import chatbot, run_async

config = {
    "configurable": {
        "thread_id": "hitl-test-3"
    }
}


async def main():

    async for chunk in chatbot.astream(
        {
            "messages": [
                HumanMessage(
                    content="Delete expense 1"
                )
            ]
        },
        config=config,
    ):
        print(chunk)


run_async(main())