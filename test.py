from langchain_core.messages import HumanMessage
from langgraph.types import Command

from langgraph_mcp_backend import chatbot, run_async


config = {
    "configurable": {
        "thread_id": "reject-test"
    }
}


async def main():

    print("\n========== FIRST RUN ==========\n")

    async for event in chatbot.astream(
        {
            "messages": [
                HumanMessage(
                    content="Delete expense id 2 immediately"
                )
            ]
        },
        config=config,
    ):
        print(event)

    print("\n========== REJECT ==========\n")

    async for event in chatbot.astream(
        Command(resume=False),
        config=config,
    ):
        print(event)


run_async(main())