import streamlit as st
from archieve.langgraph_tool_backend import chatbot,retrieve_all_threads
from langchain_core.messages import HumanMessage,AIMessage
import uuid

#**********************utility function***********************

def generate_thread_id():
    thread_id=uuid.uuid4()
    return str(thread_id)

def chat_reset():
    thread_id=generate_thread_id()
    st.session_state["thread_id"]=thread_id
    add_thread(st.session_state["thread_id"])
    st.session_state["messages"]=[]

def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)

def load_conversation(thread_id):
    state=chatbot.get_state(config={
    "configurable": {
        "thread_id": thread_id
    }
})
    return state.values.get("messages",[])

# ---------------- Session Setup ---------------- #

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"]=generate_thread_id()
if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"]=retrieve_all_threads()

add_thread(st.session_state['thread_id'])

#********************Sidebar UI*********************************

st.sidebar.title("💬 Chats")
if st.sidebar.button("➕ New Chat"):
    chat_reset()

st.sidebar.header("My Conversations")

for thread_id in st.session_state["chat_threads"][::-1]:    
    if st.sidebar.button(thread_id):
        st.session_state["thread_id"]=thread_id
        msg=load_conversation(thread_id)

        temp_messages=[]

        for message in msg :
            if isinstance(message,HumanMessage):
                role="user"
            elif isinstance(message,AIMessage):
                role="assistant"
            else:
                continue
            temp_messages.append({'role': role, 'content': message.content})

        st.session_state["messages"]=temp_messages   


# ---------------- Page Config ---------------- #
st.set_page_config(
    page_title="LangGraph Chatbot",
    page_icon="🤖",
    layout="centered"
)


st.title("🤖 LangGraph Chatbot")
st.caption("Powered by LangGraph + Gemini")




# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


#*****config thread_id******
CONFIG= {
    "configurable": {
        "thread_id": st.session_state["thread_id"]
    }
}

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
        def ai_only_stream():
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=prompt)]},
                config=CONFIG,
                stream_mode="messages"
            ):
                if isinstance(message_chunk, AIMessage):
                    # yield only assistant tokens
                    yield message_chunk.content

        assistant_reply = st.write_stream(ai_only_stream())

    # Save assistant response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": assistant_reply
        }
    )