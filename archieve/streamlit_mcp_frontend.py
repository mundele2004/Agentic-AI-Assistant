import streamlit as st
import uuid
from langchain_core.messages import HumanMessage, AIMessage,ToolMessage

from langgraph_mcp_backend import (
    create_chatbot,
    retrieve_all_threads,
    run_async,
)
from langgraph_mcp_backend import chatbot
from rag.utils import save_uploaded_file
from rag.loader import load_pdf
from rag.splitter import split_documents
from rag.embeddings import get_embeddings
from rag.vector_store import create_vector_store
from rag.retriever import get_retriever
from rag.rag_tool import create_rag_tool

# ======================================================
# Utility Functions
# ======================================================

def generate_thread_id():
    return str(uuid.uuid4())


def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def chat_reset():
    thread_id = generate_thread_id()

    st.session_state["thread_id"] = thread_id
    st.session_state["messages"] = []

    add_thread(thread_id)


def load_conversation(thread_id):

    active_chatbot = (
        create_chatbot(st.session_state.retriever)
        if st.session_state.retriever is not None
        else chatbot
    )

    state = run_async(
        active_chatbot.aget_state(
            config={
                "configurable": {
                    "thread_id": thread_id
                }
            }
        )
    )

    return state.values.get("messages", [])


# ======================================================
# Streamlit Config
# ======================================================

st.set_page_config(
    page_title="LangGraph Chatbot",
    page_icon="🤖",
    layout="centered"
)

# ======================================================
# Session State
# ======================================================


if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = retrieve_all_threads()

add_thread(st.session_state["thread_id"])

if "retriever" not in st.session_state:
    st.session_state.retriever = None

if "uploaded_pdf" not in st.session_state:
    st.session_state.uploaded_pdf = None


# ======================================================
# Sidebar
# ======================================================

st.sidebar.title("💬 Chats")

uploaded_file = st.sidebar.file_uploader(
    "Upload a PDF",
    type=["pdf"],
)

if (
    uploaded_file is not None
    and uploaded_file.name != st.session_state.uploaded_pdf
):

    path = save_uploaded_file(uploaded_file)

    documents = load_pdf(path)

    chunks = split_documents(documents)

    embeddings = get_embeddings()

    vector_store = create_vector_store(chunks, embeddings)

    retriever = get_retriever(vector_store)

    st.session_state.retriever = retriever
    st.session_state.uploaded_pdf = uploaded_file.name
    # st.session_state.chatbot = create_chatbot(retriever)

    st.sidebar.success("PDF indexed successfully!")
    

if st.sidebar.button("➕ New Chat"):
    chat_reset()

st.sidebar.header("My Conversations")

for thread_id in st.session_state["chat_threads"]:

    if st.sidebar.button(thread_id):

        st.session_state["thread_id"] = thread_id

        history = load_conversation(thread_id)

        temp_messages = []

        for msg in history:

            if isinstance(msg, HumanMessage):

                temp_messages.append(
                    {
                        "role": "user",
                        "content": msg.content,
                    }
                )

            elif isinstance(msg, AIMessage):

                content = msg.content

                if isinstance(content, str):
                    text = content

                elif isinstance(content, list):
                    text = ""

                    for block in content:
                        if (
                            isinstance(block, dict)
                            and block.get("type") == "text"
                        ):
                            text += block.get("text", "")

                else:
                    text = str(content)

                temp_messages.append(
                    {
                        "role": "assistant",
                        "content": text,
                    }
                )
        st.session_state["messages"] = temp_messages


# ======================================================
# Main Page
# ======================================================

st.title("🤖 LangGraph Chatbot")

st.caption(
    "Powered by LangGraph + Gemini + MCP"
)

# ======================================================
# Previous Messages
# ======================================================

for message in st.session_state["messages"]:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ======================================================
# LangGraph Config
# ======================================================

CONFIG = {
    "configurable": {
        "thread_id": st.session_state["thread_id"]
    }
}

# ======================================================
# Chat Input
# ======================================================

if prompt := st.chat_input("Ask anything..."):

    # ---------------- User Message ---------------- #

    st.session_state["messages"].append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    with st.chat_message("user"):
        st.markdown(prompt)

# ---------------- Assistant ---------------- #

    with st.chat_message("assistant"):

        active_chatbot = (
        create_chatbot(st.session_state.retriever)
        if st.session_state.retriever is not None
        else chatbot
    )

        async def async_stream():

            async for message_chunk, metadata in active_chatbot.astream(
                {
                    "messages": [
                        HumanMessage(content=prompt)
                    ]
                },
                config=CONFIG,
                stream_mode="messages",
            ):
                if isinstance(message_chunk, AIMessage):

                    content = message_chunk.content

                    if isinstance(content, str):
                        yield content

                    elif isinstance(content, list):

                        for block in content:

                            if isinstance(block, dict):

                                if block.get("type") == "text":
                                    yield block.get("text", "")

        def sync_stream():

            agen = async_stream()

            while True:

                try:
                    token = run_async(
                        agen.__anext__()
                    )

                    yield token

                except StopAsyncIteration:
                    break

        assistant_reply = st.write_stream(
            sync_stream()
        )

# ---------------- Save Assistant Message ---------------- #

    st.session_state["messages"].append(
        {
            "role": "assistant",
            "content": assistant_reply,
        }
    )