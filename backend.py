from langgraph.graph import StateGraph,START,END
from typing import TypedDict,Literal,Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage,HumanMessage
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv

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


checkpointer=InMemorySaver()

graph=StateGraph(ChatState)

graph.add_node("chat_node",chat_node)

graph.add_edge(START,"chat_node")
graph.add_edge("chat_node",END)

chatbot=graph.compile(checkpointer=checkpointer)

