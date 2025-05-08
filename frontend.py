import uuid
import streamlit as st

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
)
from langgraph.types import Command

from langgraph_mcp_backend import (
    chatbot,
    create_chatbot,
    retrieve_all_threads,
    run_async,
)

from rag.utils import save_uploaded_file
from rag.loader import load_pdf
from rag.splitter import split_documents
from rag.embeddings import get_embeddings
from rag.vector_store import create_vector_store
from rag.retriever import get_retriever

from database_backend import (
    initialize_database,
    save_chat_title,
    load_all_titles,
    delete_chat_title,
)

st.set_page_config(
    page_title="LangGraph Chatbot",
    page_icon="🤖",
    layout="centered",
)

# ======================================================
# Utility Functions
# ======================================================

def generate_thread_id():
    """Generate a unique thread ID for each conversation."""
    return str(uuid.uuid4())


def add_thread(thread_id: str):
    """Add a thread to the sidebar if it doesn't already exist."""
    if thread_id not in st.session_state.chat_threads:
        st.session_state.chat_threads.append(thread_id)


def chat_reset():
    """Start a brand new conversation."""
    thread_id = generate_thread_id()

    st.session_state.thread_id = thread_id
    st.session_state.messages = []

    add_thread(thread_id)

def delete_chat(thread_id: str):
    """
    Delete a chat from the UI and database.
    """

    # Remove from SQLite
    delete_chat_title(thread_id)

    # Remove from session titles
    st.session_state.chat_titles.pop(thread_id, None)

    # Remove from sidebar thread list
    if thread_id in st.session_state.chat_threads:
        st.session_state.chat_threads.remove(thread_id)

    # If deleting the currently open chat,
    # create a fresh empty chat.
    if thread_id == st.session_state.thread_id:

        st.session_state.thread_id = generate_thread_id()
        st.session_state.messages = []

        add_thread(st.session_state.thread_id)


def generate_chat_title(message: str, max_length: int = 30):
    """
    Generate a short title from the first user message.
    """

    title = message.strip()

    if len(title) > max_length:
        title = title[:max_length] + "..."

    return title

# ======================================================
# Session State
# ======================================================

def initialize_session_state():
    """Initialize all Streamlit session state variables."""

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = generate_thread_id()

    if "chat_threads" not in st.session_state:
        st.session_state.chat_threads = retrieve_all_threads()

    # Ensure current thread exists in sidebar
    add_thread(st.session_state.thread_id)

    if "retriever" not in st.session_state:
        st.session_state.retriever = None

    if "uploaded_pdf" not in st.session_state:
        st.session_state.uploaded_pdf = None

    # Human-in-the-loop state
    if "pending_interrupt" not in st.session_state:
        st.session_state.pending_interrupt = None

    if "waiting_for_approval" not in st.session_state:
        st.session_state.waiting_for_approval = False

    if "approval_decision" not in st.session_state:
        st.session_state.approval_decision = None

    if "chat_titles" not in st.session_state:
        st.session_state.chat_titles = load_all_titles()



# ======================================================
# Conversation Loader
# ======================================================

def load_conversation(thread_id: str):
    """
    Load a conversation from LangGraph persistence and
    convert it into a Streamlit-friendly format.
    """

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

    history = state.values.get("messages", [])

    ui_messages = []

    for msg in history:

        if isinstance(msg, HumanMessage):

            ui_messages.append(
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

            ui_messages.append(
                {
                    "role": "assistant",
                    "content": text,
                }
            )

    return ui_messages

# ======================================================
# Sidebar
# ======================================================

def render_sidebar():

    st.sidebar.title("💬 Chats")

    # ---------------- PDF Upload ---------------- #

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

        vector_store = create_vector_store(
            chunks,
            embeddings,
        )

        retriever = get_retriever(vector_store)

        st.session_state.retriever = retriever
        st.session_state.uploaded_pdf = uploaded_file.name

        st.sidebar.success("✅ PDF uploaded successfully!")

    # ---------------- New Chat ---------------- #

    if st.sidebar.button("➕ New Chat", use_container_width=True):
        chat_reset()
        st.rerun()

    st.sidebar.divider()

    st.sidebar.subheader("My Conversations")

    # ---------------- Chat List ---------------- #

    for thread_id in st.session_state.chat_threads:

        title = st.session_state.chat_titles.get(
            thread_id,
            "💬 New Chat"
        )

        col1, col2 = st.sidebar.columns([5, 1])

        with col1:
            if st.button(
                title,
                key=f"chat_{thread_id}",
                use_container_width=True,
            ):
                st.session_state.thread_id = thread_id
                st.session_state.messages = load_conversation(thread_id)
                st.rerun()

        with col2:
            if st.button(
                "🗑️",
                key=f"delete_{thread_id}",
                use_container_width=True,
            ):
                delete_chat(thread_id)
                st.rerun()

# ======================================================
# Chat History
# ======================================================

def render_chat_history():
    """Render all messages in the current conversation."""

    st.title("🤖 LangGraph Chatbot")

    st.caption(
        "Powered by LangGraph + Gemini + MCP"
    )

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])


# ======================================================
# Approval UI
# ======================================================

def render_pending_approval():

    if not st.session_state.waiting_for_approval:
        return

    interrupt = st.session_state.pending_interrupt

    if interrupt is None:
        return

    info = interrupt.value

    st.warning(info["message"])

    st.write(f"**Tool:** {info['tool']}")

    st.json(info["args"])

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "✅ Approve",
            use_container_width=True,
        ):
            resume_graph(True)

    with col2:

        if st.button(
            "❌ Reject",
            use_container_width=True,
        ):
            resume_graph(False)



# ======================================================
# Active Chatbot
# ======================================================

def get_active_chatbot():
    """
    Return the chatbot instance.
    If a PDF has been uploaded, return the chatbot
    with the RAG tool attached.
    """

    retriever = st.session_state.get("retriever")

    if retriever is not None:
        return create_chatbot(retriever)

    return chatbot

# ======================================================
# LangGraph Config
# ======================================================

def get_graph_config():

    return {
        "configurable": {
            "thread_id": st.session_state.thread_id
        }
    }


# ======================================================
# Graph Streaming
# ======================================================

async def stream_graph(
    prompt: str,
    active_chatbot,
    config,
):

    async for event in active_chatbot.astream(
        {
            "messages": [
                HumanMessage(content=prompt)
            ]
        },
        config=config,
        stream_mode=["updates", "messages"],
    ):
        yield event

def stream_graph_sync(
    prompt: str,
    active_chatbot,
    config,
):

    agen = stream_graph(
        prompt,
        active_chatbot,
        config,
    )

    while True:

        try:
            yield run_async(
                agen.__anext__()
            )

        except StopAsyncIteration:
            break

# ======================================================
# Resume Graph
# ======================================================

async def resume_stream(
    active_chatbot,
    config,
    approved,
):

    async for event in active_chatbot.astream(
        Command(resume=approved),
        config=config,
        stream_mode=["updates", "messages"],
    ):
        yield event


def resume_stream_sync(
    active_chatbot,
    config,
    approved,
):

    agen = resume_stream(
        active_chatbot,
        config,
        approved,
    )

    while True:

        try:
            yield run_async(
                agen.__anext__()
            )

        except StopAsyncIteration:
            break

def extract_chunk_text(chunk):   #helper 
    """
    Extract text from an AIMessageChunk.
    """

    text = ""

    content = chunk.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):

        for block in content:

            if (
                isinstance(block, dict)
                and block.get("type") == "text"
            ):
                text_piece= block.get("text", "")
                if text_piece:
                    text += text_piece

    return text


def process_stream_events(
    event_iterator,
    placeholder,
):
    """
    Process LangGraph stream events.

    Returns:
        assistant_response
    """

    assistant_response = ""

    for mode, data in event_iterator:

        # ---------------- Token Streaming ---------------- #

        if mode == "messages":

            chunk, metadata = data

            # Ignore ToolMessage output from the tools node
            if isinstance(chunk, ToolMessage):
                continue

            text = extract_chunk_text(chunk)

            if text:
                assistant_response += text
                placeholder.markdown(assistant_response)

            continue

        # ---------------- Graph Updates ---------------- #

        if mode == "updates":

            # Handle interrupt
            if "__interrupt__" in data:

                st.session_state.pending_interrupt = (
                    data["__interrupt__"][0]
                )

                st.session_state.waiting_for_approval = True

                st.rerun()

    return assistant_response


def resume_graph(approved: bool):

    active_chatbot = get_active_chatbot()

    config = {
        "configurable": {
            "thread_id": st.session_state.thread_id
        }
    }

    # Stream the assistant response inside a chat bubble
    with st.chat_message("assistant"):

        placeholder = st.empty()

        assistant_response = process_stream_events(
            resume_stream_sync(
                active_chatbot,
                config,
                approved,
            ),
            placeholder,
        )

    # Save assistant response to chat history
    if assistant_response:

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": assistant_response,
            }
        )

    # Clear interrupt state
    st.session_state.waiting_for_approval = False
    st.session_state.pending_interrupt = None
    st.session_state.approval_decision = None

    st.rerun()

# ======================================================
# User Input
# ======================================================

def handle_user_prompt():

    prompt = st.chat_input("Ask anything...")

    if not prompt:
        return

    # ---------------- Save User Message ---------------- #

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    # ---------------- Generate Chat Title ---------------- #
    if st.session_state.thread_id not in st.session_state.chat_titles:

        title = generate_chat_title(prompt)

        st.session_state.chat_titles[
            st.session_state.thread_id
        ] = title

        save_chat_title(
            st.session_state.thread_id,
            title,
        )
    # if st.session_state.thread_id not in st.session_state.chat_titles:

    #     st.session_state.chat_titles[
    #         st.session_state.thread_id
    #     ] = generate_chat_title(prompt)

    # ---------------- Display User Message ---------------- #

    with st.chat_message("user"):
        st.markdown(prompt)

    # ---------------- Assistant ---------------- #

    assistant_response = ""

    active_chatbot = get_active_chatbot()
    config = {
    "configurable": {
        "thread_id": st.session_state.thread_id
        }
    }
    with st.chat_message("assistant"):

        placeholder = st.empty()

        assistant_response = process_stream_events(
            stream_graph_sync(
                prompt,
                active_chatbot,
                config,
            ),
            placeholder,
        )
    

    # ---------------- Save Assistant ---------------- #

    if assistant_response:

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": assistant_response,
            }
        )



def main():

    initialize_database()

    initialize_session_state()

    render_sidebar()

    render_chat_history()

    render_pending_approval()

    handle_user_prompt()

if __name__ == "__main__":
    main()