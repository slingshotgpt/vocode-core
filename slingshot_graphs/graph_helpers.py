import asyncio 
import os 
from typing import Annotated, Optional, TypedDict, Callable
from call_config import CallConfig
from langgraph.graph.message import add_messages
from langchain_core.messages.utils import convert_to_openai_messages
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_core.tools import tool
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.tool import ToolCall, tool_call
from langgraph.prebuilt import ToolNode, tools_condition
import uuid
from langchain_openai import ChatOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

## Langgraph state management ##
def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    print(f"Inside update_dialog_stack: left={left}; right={right}")
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]


def reducer(a: list, b: str) -> list:
    print(f"Inside reducer: a={a}; b={b}")
    if b is not None:
        return a + [b]
    return a

def add_and_persist_messages(left, right):
    new_messages = add_messages(left, right)
    CallConfig().get_call_metadata()["current_messages"] = convert_to_openai_messages(
        new_messages
    )
    return new_messages


class State(TypedDict):
    messages: Annotated[list, add_and_persist_messages]
    agents: Annotated[list, reducer]
    user_info: str
    dialog_state: Annotated[
        list[str],
        update_dialog_stack,
    ]

def pop_dialog_state(state: State) -> dict:
    """Pop the dialog stack and return to the main assistant.

    This lets the full graph explicitly track the dialog flow and delegate control
    to specific sub-graphs.
    """
    messages = []
    if state["messages"][-1].tool_calls:
        # Note: Doesn't currently handle the edge case where the llm performs parallel tool calls
        messages.append(
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation. First, call a function if appropriate. If not, respond to the user.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    return {
        "dialog_state": "primary_assistant",
        "messages": messages,
    }


def handle_tool_error(state) -> dict:
    print(f"Inside handle_tool_error, state = {state}")
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }
    
def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


def create_specific_entry_node(
    assistant_entry_message: str, new_dialog_state: str
) -> Callable:
    def entry_node(state: State) -> dict:
        print(f"INSIDE CUSTOM entry_node, state = {state}")
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=assistant_entry_message,
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }

    return entry_node


def user_info(state: State):
    return {"user_info": ""}

def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: State) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    # content="",
                    content=f"The conversation has been routed to the {assistant_name}.",
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }

    return entry_node


def get_default_dialog_state():
    return "primary_assistant"


def get_last_dialog_state(state: State):
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return get_default_dialog_state()
    return dialog_state[-1]


class State(TypedDict):
    messages: Annotated[list, add_and_persist_messages]
    agents: Annotated[list, reducer]
    user_info: str
    dialog_state: Annotated[ 
                            list[str],
                            update_dialog_stack,
    ]

class Assistant:
    def __init__(self, runnable: Runnable, agent_name, tools, agent_name_to_router):
        self.runnable = runnable
        self.agent_name = agent_name 
        self.tools = tools 
        self.agent_name_to_router = agent_name_to_router 
        
    async def __call__(self, state: State, config: RunnableConfig):
        while True:

            try:
                runnable_with_retries = self.runnable.with_retry()
                print(f"About to invoke LLM")
                result = await runnable_with_retries.ainvoke(
                    state,
                    config={'recursion_limit': 5, **config},
                    parallel_tool_calls=False, 
                )
            except Exception as e:
                print(f"Exception: {e}")
                return {
                    "messages": ("assistant", "Apologies.  There are some errors in our end"),
                    "agents": self.agent_name
                }

            # TODO handle tools
            break
        
        return {
            "messages": result,
            "agents": self.agent_name,
        }

def get_openai_llm_for_agent(agent_name):
    model_name = "gpt-4o"

    llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model=model_name,
            temperature=0,
            streaming=True,
            max_retries=5,
        )
    print(f"Using model={model_name} for agent={agent_name}")

    #llm.async_client = Wrapper(llm.async_client)
    return llm

async def route_tool_response(state: State):
    print(f"Inside route_tool_response, state = {state}")
    last_message_content = state["messages"][-1].content
    tool_name = last_message_content.split("ROUTE ")[-1]
    return {
        "messages": [
            AIMessage(
                content="",
                id=str(uuid.uuid4()),
                tool_calls=[
                    tool_call(
                        name=tool_name,
                        id=str(uuid.uuid4()),
                        args={},
                    )
                ],
            )
        ]
    }

async def tool_msg_to_ai_msg(state):
    # print(f"Inside tool_msg_to_ai_msg, state = {state}")
    last_message_content = state["messages"][-1].content
    return {
        "messages": AIMessage(
            content=last_message_content,
            id=str(uuid.uuid4()),
        )
    }

async def route_sensitive_tools(
    state: State,
):
    last_message_content = state["messages"][-1].content
    print(
        f"Inside route_sensitive_tools, last_message_content = {last_message_content}"
    )
    dialog_state = state.get("dialog_state")
    if "DETERMINISTIC" in last_message_content:
        print(f"About to return tool_msg_to_ai_msg")
        #AppConfig().get_call_metadata()["current_agent"] = ""
        return "tool_msg_to_ai_msg"
    if "ROUTE" in last_message_content:
        print(f"About to return route_tool_response")
        return "route_tool_response"

    print(f"About to return last dialog state: {get_last_dialog_state(state)}")
    return get_last_dialog_state(state)

def get_live_agent_string():
    return """A live agent will call you back. Thank you, and goodbye.""" if CallConfig().language == 'en' else """라이브 상담원이 다시 전화드릴 예정입니다. 이용해 주셔서 감사합니다. 안녕히 계세요."""