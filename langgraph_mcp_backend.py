from typing import TypedDict, Annotated
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio
import threading
import requests
import aiosqlite
import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage
from langchain_core.tools import tool, BaseTool
from langchain_community.tools.tavily_search import TavilySearchResults

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from langchain_mcp_adapters.client import MultiServerMCPClient
from rag.rag_tool import create_rag_tool

from langgraph.types import interrupt,Command

load_dotenv()

# ======================================================
# Background Async Loop
# ======================================================

_ASYNC_LOOP = asyncio.new_event_loop()
threading.Thread(
    target=_ASYNC_LOOP.run_forever,
    daemon=True
).start()


def _submit_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, _ASYNC_LOOP)


def run_async(coro):
    return _submit_async(coro).result()


# ======================================================
# LLM
# ======================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0.5,
)

# ======================================================
# Local Tools
# ======================================================

search_tool = TavilySearchResults(max_results=3)


@tool
def calculator(first_num: float, second_num: float, operation: str):
    """
    Perform add, sub, mul or div.
    """

    if operation == "add":
        result = first_num + second_num

    elif operation == "sub":
        result = first_num - second_num

    elif operation == "mul":
        result = first_num * second_num

    elif operation == "div":

        if second_num == 0:
            return {"error": "Division by zero"}

        result = first_num / second_num

    else:
        return {"error": "Invalid operation"}

    return {
        "result": result
    }


@tool
def current_datetime():
    """
    Returns current Indian date and time.
    """

    now = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    return now.strftime("%A, %d %B %Y, %I:%M:%S %p IST")


# ======================================================
# MCP Servers
# ======================================================

SERVERS = {
    "expense": {
        "transport": "streamable_http",
        "url": "https://expense-tracker-mcp-production.up.railway.app/mcp",
    }
}

client = MultiServerMCPClient(SERVERS)


def load_mcp_tools() -> list[BaseTool]:

    try:
        return run_async(client.get_tools())

    except Exception as e:

        print(e)
        return []


#mcp_tools = load_mcp_tools()
mcp_tools=[]

# ======================================================
# State
# ======================================================

class ChatState(TypedDict):
    messages: Annotated[
        list[BaseMessage],
        add_messages
    ]
    approved: bool

SENSITIVE_TOOLS = {
    "update_expense",
    "delete_expense",
}


def route_tools(state: ChatState):

    last_message = state["messages"][-1]

    # No tool calls → END
    if not last_message.tool_calls:
        return END

    # Check every requested tool
    for tool_call in last_message.tool_calls:

        if tool_call["name"] in SENSITIVE_TOOLS:
            return "approval"

    # Safe tools
    return "tools"

# ======================================================
# SQLite Checkpointer
# ======================================================

async def create_checkpointer():

    conn = await aiosqlite.connect("chatbot.db")

    return AsyncSqliteSaver(conn)


checkpointer = run_async(
    create_checkpointer()
)

# ======================================================
# Chatbot Factory
# ======================================================

def create_chatbot(retriever=None):

    tools = [
        search_tool,
        calculator,
        current_datetime,
        *mcp_tools
    ]

    # Add RAG tool only if a retriever exists
    if retriever is not None:
        tools.append(
            create_rag_tool(retriever)
        )

    llm_with_tools = llm.bind_tools(tools)

    tool_node = ToolNode(tools)

    async def chat_node(state: ChatState):

        response = await llm_with_tools.ainvoke(
            state["messages"]
        )

        return {
            "messages": [response]
        }

    async def approval_node(state: ChatState):

        last_message = state["messages"][-1]
        tool_call = last_message.tool_calls[0]

        approval = interrupt(
            {
                "tool": tool_call["name"],
                "args": tool_call["args"],
                "message": f"Approve execution of '{tool_call['name']}'?"
            }
        )


        return {
            "approved": approval
        }

    def route_after_approval(state: ChatState):

        if state["approved"]:
            return "tools"

        return END

    #Build the graph:
    
    graph = StateGraph(ChatState)

    graph.add_node(
        "chat_node",
        chat_node
    )

    graph.add_node(
        "tools",
        tool_node
    )

    graph.add_node(
    "approval",
    approval_node
)

    graph.add_edge(
        START,
        "chat_node"
    )

    graph.add_conditional_edges(
        "chat_node",
        route_tools,
        {
            "tools": "tools",
            "approval": "approval",
            END: END,
        },
    )
    
    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "tools": "tools",
            END: END,
        },
    )

    graph.add_edge(
        "tools",
        "chat_node"
    )

    return graph.compile(
        checkpointer=checkpointer
    )

chatbot = create_chatbot()

# ======================================================
# Thread Helper
# ======================================================

async def _alist_threads():

    latest_threads = {}

    async for checkpoint in checkpointer.alist(None):

        thread_id = checkpoint.config["configurable"]["thread_id"]

        # Keep the latest checkpoint for each thread
        if thread_id not in latest_threads:
            latest_threads[thread_id] = checkpoint

    return list(latest_threads.keys())


def retrieve_all_threads():

    return run_async(
        _alist_threads()
    )

