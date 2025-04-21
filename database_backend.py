from langgraph.graph import StateGraph,START,END
from typing import TypedDict,Literal,Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage,HumanMessage
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv
import sqlite3

load_dotenv()


class ChatState(TypedDict):
    messages:Annotated[list[BaseMessage],add_messages]   #to apend messages of all kind

llm=ChatGoogleGenerativeAI(
model="gemini-2.5-flash",
temperature=0.5
)

def chat_node(state:ChatState):

    #take the query from state and give it to llm
    messages=state["messages"]
    response=llm.invoke(messages)
    #store the response in state

    return {"messages":[response]}

conn=sqlite3.connect(database='chatbot.db',check_same_thread=False)
#Checkpointer:
checkpointer=SqliteSaver(conn=conn)


graph=StateGraph(ChatState)

graph.add_node("chat_node",chat_node)

graph.add_edge(START,"chat_node")
graph.add_edge("chat_node",END)

chatbot=graph.compile(checkpointer=checkpointer)

def retrieve_all_threads():
    all_threads=set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(all_threads)