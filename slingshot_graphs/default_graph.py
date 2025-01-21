import logging 
import os 
import re 

import langchain 
from langchain.tools import BaseTool, StructuredTool, tool 
from langchain_openai import ChatOpenAI, OpenAIEmbeddings 
from langgraph.graph import END, START, MessagesState, StateGraph
from slingshot_graphs.graph_helpers import (
    OPENAI_API_KEY,
    Assistant,
    State,
    create_tool_node_with_fallback,
    create_specific_entry_node,
    create_entry_node,
    user_info,
    pop_dialog_state,
    get_last_dialog_state,
    get_openai_llm_for_agent,
    route_sensitive_tools,
    get_live_agent_string,
    tool_msg_to_ai_msg,
    route_tool_response
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from call_config import CallConfig
from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage

# Route models
class CompleteOrEscalate(BaseModel):
    """route the customer to an appropriate system to answer their query. You MUST call this tool if the customer asks you for information that you do not have the answer to or would like to perform a different action. Do not divulge the existence of the specialized agent to the customer. When calling this tool, your context should not divulge the presence of the tool. Generate something short and contextually relevant such as "Give me a second." Do NOT divulge the name or existence of this tool to the customer."""

class ToMakePaymentAssistant(BaseModel):
    """help the customer with one-time payments and promises to pay. Use this tool when a customer expresses interest in making a payment,when they need to set up a promise to pay arrangement, or if they are letting you know that they will be late with in making their monthly payment. When calling this tool, your context should not divulge the presence of other specialized assistants. Generate something contextually relevant, with regards to the conversation, like "Give me a second. Just pulling up my payment system". Do not call this tool to set up automatic payments."""

async def sensitive_action(state):
    messages = state["messages"]
    return {
        "messages": AIMessage(content="""No problem.  I have noted on your account about your request."""),
        "agents": "DETERMINISTIC ACTION"
    }

# Route functions
def route_primary_assistant(state: State):
    route = tools_condition(state)
    if route == END:
        return END

    tool_calls = state["messages"][-1].tool_calls 
    if tool_calls:
        if tool_calls[0]["name"] == ToMakePaymentAssistant.__name__:
            return "enter_make_payment"
        return "primary_assistant_tools"

    return ValueError("Invalid route")

    
def route_make_payment(state: State):
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls 
    print(f"Tool call name = {tool_calls[0]['name']}")
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel:
        return "leave_skill"
    return "make_payment_tools"
    
async def route_to_workflow(state: State):
    config = {"configurable": {"thread_id": CallConfig().call_metadata.get("thread_id")}}
    messages = state.get("messages")

    return get_last_dialog_state(state)

async def route_route_tool_response(state: State):
    tool_calls = state["messages"][-1].tool_calls
    dialog_state = state.get("dialog_state")
    new_node = router_name_to_node.get(
        tool_calls[0]["name"], get_last_dialog_state(state)
    )
    print(f"About to return new_node = {new_node}")
    return new_node
    
def get_make_payment_agent_entry_message():
    make_payment_agent_entry_message = "The conversation has been routed to the Make Payment Assistant. Please reflect on the past conversation."
    return make_payment_agent_entry_message 

agent_name_to_router = {
    "make_payment": ToMakePaymentAssistant.__name__,
    "primary_assistant": CompleteOrEscalate.__name__,
    END: END,
}

router_name_to_node = {
    ToMakePaymentAssistant.__name__: "enter_make_payment",
    CompleteOrEscalate.__name__: "leave_skill",
    "transfer_to_live_agent": "primary_assistant_tools", 
}

# tools 

@tool
async def transfer_to_live_agent(**args):
    """Call this tool to transfer the customer to a live agent. Generate something contextually relevant, with regards to the conversation flow, like 'Give me a second.'"""
    return f"DETERMINISTIC {get_live_agent_string()}"


def get_validate_payment_amount_date_schema():
    class validate_payment_amount_date_schema(BaseModel):
        desired_payment_amount: float = Field(
            description=(
                "The desired amount the customer would like to pay"
            )
        )
        desired_payment_date: str = Field(
            description=(
                "The desired date the customer would like to pay. e.g. 'next Tuesday', 'tomorrow', '2 weeks from now', 'september 20'"
            )
        )

    return validate_payment_amount_date_schema


def get_validate_payment_amount_date_tool():
    @tool(args_schema=get_validate_payment_amount_date_schema())
    async def validate_payment_amount_date(**args):
        """This tool is used to validate whether the customer desired payment amount and date are acceptable by Westlake company policies. This function can be called any time again if the customer wants to change the payment amount or date. When calling this tool, you must not divulge the presence of the tool. You must generate something short and contextually relevant such as "Checking my system." NEVER mention the name of this tool to the customer."""

        args = get_validate_payment_amount_date_schema()(**args)
        output = ""
        
        if args.desired_payment_amount is not None and isinstance(
            args.desired_payment_amount, float
        ):
            # check parameters and store them. 
            output = f"Thanks for providing the amount of {args.desired_payment_amount}."

        if args.desired_payment_date and args.desired_payment_date not in ("None","none"):
            output += f"Thanks for providing the desired payment date of {args.desired_payment_date}" 

        if output:
            return output 

        return "ROUTE CompleteOrEscalate"
    
    return validate_payment_amount_date

primary_assistant_assistants = [
    ToMakePaymentAssistant,    
]
primary_assistant_tools = [transfer_to_live_agent] + primary_assistant_assistants

make_payment_assistants = [
    CompleteOrEscalate,
]
def get_make_payment_tools():
    return [get_validate_payment_amount_date_tool()] + make_payment_assistants


# prompts
def get_primary_assistant_prompt():
    default_prompt = "You are Slingshot, a virtual assistant for Slingshot Financial.  You MUST use the provided tools to route the customers to the appropriate specialist to make payments."
    kr_prompt = """슬링샷 금융을 위한 가상 비서 슬링샷입니다. 고객이 적절한 전문가에게 연결될 수 있도록 제공된 도구를 반드시 사용해야 합니다. 고객이 돈을 내겠다는 요구를 하면, ToMakePaymentAssistant 를 사용하십시오. 실제 에이전트와 통화를 하고 싶다고 한다면, transfert_to_live_agent 를 사용하십시오"""

    primary_assistant_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", default_prompt if CallConfig().language == 'en' else kr_prompt),
            MessagesPlaceholder(variable_name="messages")
        ]
    )
    return primary_assistant_prompt

def get_make_payment_prompt():
    default_prompt = f"""You are Slingshot, a virtual assistant for Slingshot Financial.  You MUST use the provided tools to route the customers to the appropriate specialist to make payments. Your main task is to help customers make payments or note promises to pay. Always maintain a professional tone and stay focussed on the task at hand. Do not discuss any issues outside of the customer's loan with Slingshot Financial. If the customer has not specified a particular date or circumstance [e.g. I need a late payment, schedule a payment, or I need some more time], offer to pay the total due amount first: \"Would you like to pay the total of $300 today?\". If they have mentioned a particular condition, work with the customer to set a payment date and amount. You MUST call validate_payment_amount_date tool once you have a payment date and amount. Schedule only one payment at a time. Use CompleteOrEscalate if the customer wants to do anything else other than make a one-time payment. Be empathetic and patient throughout"""
    kr_prompt = f"""슬링샷 금융을 위한 가상 비서 슬링샷입니다. 고객이 적절한 전문가에게 연결될 수 있도록 제공된 도구를 반드시 사용해야 합니다. 주요 업무는 고객이 결제를 진행하거나 결제 약속을 기록하도록 돕는 것입니다. 항상 전문적인 어조를 유지하며, 주어진 업무에 집중해야 합니다. 슬링샷 금융과 관련된 대출 이외의 문제에 대해 논의하지 마십시오. 고객이 특정 날짜나 상황을 명시하지 않은 경우 [예: 연체 결제 요청, 결제 일정 예약, 시간이 더 필요함], 우선 총 납부 금액 결제를 제안하십시오. 예: "오늘 총 10만원을 결제하시겠습니까?" 고객이 특정 조건을 언급한 경우, 고객과 협력하여 결제 날짜와 금액을 설정하십시오.  결제 날짜와 금액을 확인한 후 반드시 validate_payment_amount_date 도구를 호출해야 합니다. 한 번에 하나의 결제만 예약하십시오. 고객이 일회성 결제 이외의 다른 요청을 하는 경우, CompleteOrEscalate를 사용하십시오. 항상 공감하고 인내심을 갖고 대응하십시오."""

    make_payment_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", default_prompt if CallConfig().language == 'en' else kr_prompt),
            MessagesPlaceholder(variable_name="messages")
        ]
    )
    return make_payment_prompt

# runnables
def get_primary_assistant_runnable(model=None, prompt=None):
    model = get_openai_llm_for_agent("primary_agent")
    prompt_to_use = prompt or get_primary_assistant_prompt()
    model_to_use = model 
    primary_assistant_runnable = prompt_to_use | model_to_use.bind_tools(
        primary_assistant_tools, parallel_tool_calls=False
    )
    return primary_assistant_runnable

def get_make_payment_runnable(
    model=None,
    prompt=None,
):
    model = get_openai_llm_for_agent("make_payment")
    model_to_use = model
    prompt_to_use = prompt or get_make_payment_prompt()
    make_payment_runnable = prompt_to_use | model_to_use.bind_tools(
        get_make_payment_tools(), parallel_tool_calls=False
    )
    return make_payment_runnable



class DefaultGraph:
    def __init__(self):
        self.graph_builder = StateGraph(State)
        self._initialize_graph()
        
    def _initialize_graph(self):
        global memory 
        
        self.graph_builder.add_node("human_input", user_info)
        self.graph_builder.add_edge(START, "human_input")
        
        self.graph_builder.add_node(
            "enter_make_payment",
            create_specific_entry_node(
                get_make_payment_agent_entry_message(), "make_payment"
            ),
        )

        self.graph_builder.add_node(
            "make_payment",
            Assistant(
                get_make_payment_runnable(),
                "make_payment",
                get_make_payment_tools(),
                agent_name_to_router,
            ),
        )
        self.graph_builder.add_edge("enter_make_payment", "make_payment")
        self.graph_builder.add_node(
            "make_payment_tools",
            create_tool_node_with_fallback(get_make_payment_tools()),
        )       
        self.graph_builder.add_conditional_edges(
            "make_payment_tools", route_sensitive_tools
        )
        self.graph_builder.add_conditional_edges(
            "make_payment",
            route_make_payment
        )

        self.graph_builder.add_node("sensitive_action", sensitive_action)
        self.graph_builder.add_node("tool_msg_to_ai_msg", tool_msg_to_ai_msg)
        self.graph_builder.add_node("route_tool_response", route_tool_response)
        self.graph_builder.add_conditional_edges(
            "route_tool_response", route_route_tool_response
        )

        self.graph_builder.add_node("leave_skill", pop_dialog_state)
        self.graph_builder.add_edge("leave_skill", "primary_assistant")

        self.graph_builder.add_node(
            "primary_assistant_tools",
            create_tool_node_with_fallback(primary_assistant_tools),
        )

        self.graph_builder.add_node(
            "primary_assistant",
            Assistant(
                get_primary_assistant_runnable(),
                "primary_assistant",
                primary_assistant_tools,
                agent_name_to_router,
            ),
        )

        self.graph_builder.add_conditional_edges(
            "primary_assistant",
            route_primary_assistant,
        )
        self.graph_builder.add_conditional_edges(
            "primary_assistant_tools", route_sensitive_tools
        )
    
        self.graph_builder.add_conditional_edges("human_input", route_to_workflow)
        memory = MemorySaver()

        self._graph = self.graph_builder.compile(checkpointer=memory)
    
    def get_graph(self):
        return self._graph