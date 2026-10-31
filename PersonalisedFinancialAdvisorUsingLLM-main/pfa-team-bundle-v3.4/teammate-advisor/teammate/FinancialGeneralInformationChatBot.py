from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import (BaseMessage, SystemMessage, ToolMessage,
                                     AIMessage, convert_to_messages)
import operator
from langgraph.graph import StateGraph, START, END
from datetime import datetime
import json
from RagChainForNumericalData import QueryRagInit, QueryRag
import os
from dotenv import load_dotenv
from GaurdRails import LLMWithGuardrails


class GetRequiredBankDepositDataFromTheRagToolReturnSchema(BaseModel):
    answer: str = Field(
        description="Response for the query in natural language")


class GetRequiredBankDepositDataFromTheRagToolArgsSchema(BaseModel):
    NaturalLanguageFinancialQuery: str = Field(
        description="Query regarding Bank deposits in Natural language")


@tool(args_schema=GetRequiredBankDepositDataFromTheRagToolArgsSchema)
def GetRequiredBankDepositDataFromTheRagTool(
        NaturalLanguageFinancialQuery: str
) -> GetRequiredBankDepositDataFromTheRagToolReturnSchema:
    """Queries the rag database for Bank deposits information and
    returns the answer
    Args:
        readDataQuerry: Query regarding Bank deposits in Natural
            language
    Returns:
        answer in natural language
    """
    answer, _context = QueryRag(NaturalLanguageFinancialQuery,
                                ragHandleBankDeposits[0],
                                ragHandleBankDeposits[1])
    return answer


class GetRequiredMutualFundDataFromTheRagToolReturnSchema(BaseModel):
    answer: str = Field(
        description="Response for the query in natural language")


class GetRequiredMutualFundDataFromTheRagToolArgsSchema(BaseModel):
    NaturalLanguageFinancialQuery: str = Field(
        description="Query regarding Mutual funds in Natural language")


@tool(args_schema=GetRequiredMutualFundDataFromTheRagToolArgsSchema)
def GetRequiredMutualFundDataFromTheRagTool(
        NaturalLanguageFinancialQuery: str
) -> GetRequiredMutualFundDataFromTheRagToolReturnSchema:
    """Queries the rag database for any Mutual fund related
    information and returns the answer
    Args:
        readDataQuerry: Query regarding Mutual funds in Natural language
    Returns:
        answer in natural language
    """
    answer, _context = QueryRag(NaturalLanguageFinancialQuery,
                                ragHandleMutualFund[0],
                                ragHandleMutualFund[1])
    return answer


class AdminAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


def AdminAgentNode(state: AdminAgentState):
    # prepend a system instruction once, then ask the model
    current_time2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state_messages = convert_to_messages(state["messages"])
    if not any(m.type == "system" for m in state_messages):
        sys = SystemMessage(content=f"""You are a helpful Financial AI
            assistant for the database administrator.
            Your activities may include:
            1. Getting user requested Bank deposits data using the
               'GetRequiredBankDepositDataFromTheRagTool'.
            2. Getting user requested Mutual funds data using the
               'GetRequiredMutualFundDataFromTheRagTool'.

            hints:
            1. If the request is ambiguous, prompt the user to be specific.
            2. Always refer rag database, for financial questions. Do not use
               LLMs knowledge.
            4. For non financial actions suggested by admin, say that "I am not
               able to the action prescribed."
            6. Do not make an extra tool call if the required data is already
               there in the context.
            7. If non financial questions, answer as "I dont know the answer."

            Please note that the current time is {current_time2}"""
                            )
        msgs = [sys] + list(state_messages)
    else:
        msgs = state_messages

    response = llm_with_tools.invoke(msgs)
    return {"messages": [response]}


def ToolsNode(state: AdminAgentState):
    messages = convert_to_messages(state['messages'])
    # this has the query we need to send to the tool provided by the
    # agent
    last_message = messages[-1]
    function_messages = []
    tool_calls = (getattr(last_message, "tool_calls", None)
                  or last_message.additional_kwargs.get("tool_calls", []))
    for everyTool in tool_calls:
        if isinstance(everyTool, dict) and "function" in everyTool:
            parsed_tool_input = everyTool['function']['arguments']
            tool_name = everyTool['function']['name']
            tool_input = json.loads(parsed_tool_input) if isinstance(
                parsed_tool_input, str) else parsed_tool_input
            tool_call_id = everyTool['id']
        else:
            tool_name = everyTool['name']
            tool_input = everyTool.get('args', {})
            tool_call_id = everyTool['id']
        tool_response = invoke_tool(tool_name, tool_input)
        function_messages.append(ToolMessage(content=str(tool_response),
                                             name=tool_name,
                                             tool_call_id=tool_call_id))
    return {"messages": function_messages}


def invoke_tool(toolName: str, raw_args: dict):
    """Looks up the tool by name in the registry and invokes it.

    The tool is invoked with the given args.
    """
    if TOOL_REGISTRY[toolName] is not None:
        return TOOL_REGISTRY[toolName].invoke(raw_args)
    raise ValueError(f"Unknown tool: {toolName}")


def where_to_go(state: AdminAgentState):
    last_msg = convert_to_messages(state["messages"])[-1]
    # If the assistant asked to call tools, LangChain exposes them as
    # `tool_calls`
    if (isinstance(last_msg, AIMessage)
            and getattr(last_msg, "tool_calls", None)):
        return "continue"
    return "end"


def inputGuardRailCondition(state: AdminAgentState):
    last_msg = convert_to_messages(state["messages"])[-1]
    if gRAils.invoke(last_msg.content):
        return "continue"
    return "end"


def ExitGuardRailNode(state: AdminAgentState):
    state_messages = convert_to_messages(state["messages"])
    last_msg = state_messages[-1]
    human_messages = [m for m in state_messages if m.type == "human"]
    last_human_content = human_messages[-1].content if human_messages else ""
    passed, _ = gRAils.checkOutput(last_human_content, last_msg.content)
    if not passed:
        return {"messages": [AIMessage(
            content=("I'm sorry, I can't share that response as it "
                     "violates content policy."))]}
    print(last_msg.content)
    return {"messages": []}


def buildAdminAgentGraph():
    global llm_with_tools
    global TOOL_REGISTRY
    global ragHandleBankDeposits
    global ragHandleMutualFund
    global gRAils
    gRAils = LLMWithGuardrails()

    ragHandleBankDeposits = QueryRagInit("Deposit")
    ragHandleMutualFund = QueryRagInit("MutualFund")

    TOOL_REGISTRY = {
        "GetRequiredBankDepositDataFromTheRagTool":
            GetRequiredBankDepositDataFromTheRagTool,
        "GetRequiredMutualFundDataFromTheRagTool":
            GetRequiredMutualFundDataFromTheRagTool
    }
    load_dotenv()
    llm = ChatOpenAI(
        model="gpt-4.1",
        temperature=0,
        api_key=os.environ["OPENAI_API_KEY"])
    llm_with_tools = llm.bind_tools(
        TOOL_REGISTRY.values(), parallel_tool_calls=False)

    # define the graph
    workflow = StateGraph(AdminAgentState)
    # Add nodes
    workflow.add_node("AdminAgent", AdminAgentNode)
    workflow.add_node("tool", ToolsNode)
    workflow.add_node("ExitGuardrail", ExitGuardRailNode)
    # Add edges
    workflow.add_conditional_edges(START, inputGuardRailCondition, {
        "continue": "AdminAgent", "end": END})
    workflow.add_conditional_edges("AdminAgent", where_to_go, {
        "continue": "tool", "end": "ExitGuardrail"})
    workflow.add_edge('tool', 'AdminAgent')
    workflow.add_edge("ExitGuardrail", END)

    # compile graph
    app = workflow.compile()

    return app


graph = buildAdminAgentGraph()
