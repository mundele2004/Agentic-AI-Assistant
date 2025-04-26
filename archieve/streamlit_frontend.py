import streamlit as st
from backend import chatbot
from langchain_core.messages import HumanMessage


thread_id = "1"

CONFIG= {
    "configurable": {
        "thread_id": thread_id
    }
}

# ---------------- Page Config ---------------- #
st.set_page_config(
    page_title="LangGraph Chatbot",
    page_icon="🤖",
    layout="centered"
)


st.title("🤖 LangGraph Chatbot")
st.caption("Powered by LangGraph + Gemini")

# ---------------- Chat History ---------------- #
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---------------- User Input ---------------- #
if prompt := st.chat_input("Ask anything..."):

    # Store user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # ---------------- LangGraph Response ---------------- #


    with st.chat_message("assistant"):
        assistant_reply=st.write_stream(
            message_chunk.content for message_chunk,metadata in chatbot.stream(
                    {'messages':[HumanMessage(content=prompt)]},
    config = CONFIG,
stream_mode="messages"
            )
        )

    # Save assistant response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": assistant_reply
        }
    )