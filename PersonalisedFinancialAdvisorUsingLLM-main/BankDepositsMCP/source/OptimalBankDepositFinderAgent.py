import os
import sys

# `langgraph dev` loads this file without its folder on sys.path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import sqlite3
from langchain.prompts import PromptTemplate
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import (BaseMessage, SystemMessage, HumanMessage, ToolMessage,
                                     AIMessage, convert_to_messages)
import operator
from langgraph.graph import StateGraph, START, END
from datetime import datetime
import json
from StateActionState import (OptimalActionFixedDepositTool,
                              OptimalActionRecurringDepositTool, GetFinalValueConsideringInflation, WriteMermaidDiagramPage)
from dotenv import load_dotenv
from GaurdRails import LLMWithGuardrails
import requests


class get_india_inflationReturnSchema(BaseModel):
    inflation: float = Field(
        description="float data of present inflation of India")


class get_india_inflationArgsSchema(BaseModel):
    """Arguments schema for the get_india_inflation tool.

    This tool takes no arguments.
    """
    pass


@tool(args_schema=get_india_inflationArgsSchema)
def get_india_inflation() -> get_india_inflationReturnSchema:
    url = "https://api.worldbank.org/v2/country/IND/indicator/FP.CPI.TOTL.ZG"
    data = requests.get(
        url, params={"format": "json", "per_page": 100}).json()[1]
    rows = sorted((int(d["date"]), round(d["value"], 2))
                  for d in data if d["value"] is not None)
    return rows[-1][1]


class GetSqlLiteTablesStructureReturnSchema(BaseModel):
    status: bool = Field(
        description=("bool data where 'True' represents successful "
                     "execution, 'False' represents unsuccessful execution"))
    tables: list[str] = Field(description="List of tables in the database")
    tablesColumnProfiles: list[list[str]] = Field(
        description="List of column profiles of tables")


class GetSqlLiteTablesStructureArgsSchema(BaseModel):
    pass


@tool(args_schema=GetSqlLiteTablesStructureArgsSchema)
def GetSqlLiteTablesStructure() -> GetSqlLiteTablesStructureReturnSchema:
    """
    Reads the table structure
    Args: None
    Returns:
        sturcture containing status, table list and a list of column profiles
        of tables.
    """
    try:
        conn = sqlite3.connect("memory.db", check_same_thread=False)
        cursor = conn.cursor()
        GetTableNamesQuerry = (
            "SELECT name FROM sqlite_master WHERE type='table'")
        GetColumnProfilesQuerry = PromptTemplate(
            input_variables=["table_name"],
            template="PRAGMA table_info({table_name})"
        )
        cursor.execute(GetTableNamesQuerry)
        tables = [row[0] for row in cursor.fetchall()]
        tablesColumnProfiles = []
        for table in tables:
            querry = GetColumnProfilesQuerry.format(table_name=table)
            cursor.execute(querry)
            columnProfile = [row[1] for row in cursor.fetchall()]
            tablesColumnProfiles.append(columnProfile)
        conn.close()
    except sqlite3.Error as e:
        # Return the error message directly to the LLM so it can debug itself
        print(f"Database Error: {e}. Please check your column and table "
              "names and try again.")
        return False, [], []
    return True, tables, tablesColumnProfiles


class GetSqlLiteTableDataReturnSchema(BaseModel):
    status: bool = Field(
        description=("bool data where 'True' represents successful "
                     "execution, 'False' represents unsuccessful execution"))
    dataRows: list[tuple] = Field(description="list of tuples of rows")


class GetSqlLiteTableDataArgsSchema(BaseModel):
    readDataQuery: str = Field(description="sql query to read the table data")


@tool(args_schema=GetSqlLiteTableDataArgsSchema)
def GetSqlLiteTableData(readDataQuery) -> GetSqlLiteTableDataReturnSchema:
    """Reads the table data using the given querry
    Args:
        readDataQuerry: Querry to read the data inside the table
    Returns:
        List of tuples of rows of a table
    """
    conn = sqlite3.connect("memory.db", check_same_thread=False)
    cursor = conn.cursor()
    try:
        cursor.execute(readDataQuery)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        # Return the error message directly to the LLM so it can debug itself
        print(f"Database Error: {e}. Please check your column and table "
              "names and try again.")
        return False, []
    conn.close()
    return True, rows


class AdminAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


def AdminAgentNode(state: AdminAgentState):
    # prepend a system instruction once, then ask the model
    current_time2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state_messages = convert_to_messages(state["messages"])
    if not any(m.type == "system" for m in state_messages):
        sys = SystemMessage(content=f"""You are a helpful Financial AI
                    assistant for the database administrator.
                    Activity sequence:
                    1. Get the initial(balance) and the goal states from the
                       user. Even if user does it give the goal state balance, 
                       Please fill it with very large positive number, as optimal 
                       sequence finding does not need to know goal balance.
                       Goal time is enough to know.
                       Please do not probe the user for the goal amount.
                    2. Get the sqlite database meta data.
                    3. Read the sqlite database data for the list of fixed
                       deposit schemes presently available. Scheme type may not
                       be readily found, use a pattern match instead of exact
                       match. Use the age of the user to query for the 
                       deposits specific to 'senior citizen' category and 
                       'super senior citizen' category.
                    4. Make the structured data out of the initial state(with
                       initial balance or lumpsum available), goal state, fixed
                       deposit schemes list taken from the sqlite.
                    5. Give the structured data to
                       'OptimalActionFixedDepositTool'
                    6. Please extract the optimal sequence of fixed deposit
                       actions and find the remaining amount to reach the goal
                       from the return structure of the tool call.
                    7. Get the initial installment amount planned and the
                       initial time and the recalculated goal state(with the
                       remaining amount to reach the goal) that has to be
                       achieved by the user using the recurring deposits.
                    8. Read the sqlite database data for the list of recurring
                       deposit schemes and fixed deposit schemes presently available.
                       Scheme type may not be readily found, use a pattern match instead of exact
                       match. Use the age of the user to query for the 
                       deposits specific to 'senior citizen' category and 
                       'super senior citizen' category.
                    9. Make the structured data out of the initial
                       state(installment amount planned), goal state, recurring
                       deposit schemes and fixed deposit schemes list taken from the sqlite.
                    10. Give the structured data to
                        'OptimalActionRecurringDepositTool'
                    11. Please extract the recurring deposit action sequence
                        and the reinvestments done after fruitions of the 
                        recurring deposits for the user.
                    12. Output both the fixed deposit schemes from the step 6 and recurring
                        deposit schemes and their reinvestment fixed deposit 
                        schemes from step 11 in a single json format.
                        bank name, deposit name, interest rate, start time, end time,
                        start balance|installment, end balance, back-to-back repetition count.
                    13. Output the digraph image using the mermaid textual
                        decriptions got from step 6 and step 7 in a single
                        diagram using the tool WriteMermaidDiagramPage.
                    14. Output the final value of the balance on goal date
                        considering inflation.
                    

                    Description of the tools needed:
                    1. Read a deposit_schemes table's metadata using the tool
                       'GetSqlLiteTablesStructure'.
                    2. Read a deposit_schemes table's content using the tool
                       'GetSqlLiteTableData'. Each row corresponds to one
                       deposit scheme.
                    3. Find the optimal list of fixed deposit actions actions
                       to be taken using the tool
                       'OptimalActionFixedDepositTool'
                    4. Find the optimal list of recurring deposit actions to be
                       taken using the tool 'OptimalActionRecurringDepositTool'
                    5. Get the present inflation rate using the tool
                       'get_india_inflation'
                    6. Get the value of money at the future date considering 
                       inflation using 'GetFinalValueConsideringInflation'
                    7. Render the image of the digraph of the bank deposits
                        using the tool, WriteMermaidDiagramPage.
                    
                    hints:
                    1. If the request is ambiguous, prompt the admin to be
                       specific.
                    2. Always refer to sql database, for financial questions.
                       Do not use LLMs knowledge.
                    3. For non financial actions suggested by admin, say that
                       "I am not able to do the action prescribed."
                    4. Please ignore any redundant actions prescribed by admin,
                       if already completed in the past.
                    5. Do not make an extra tool call if the required data is
                       already there in the context.
                    6. If non financial questions are asked, answer as "I dont
                       know the answer."
                    7. if the tool 'OptimalActionFixedDepositTool' empty lists,
                       then answer as "Not possible with current fixed deposits
                       interest rates."
                    8. if the tool 'OptimalActionRecurringDepositTool' empty
                       lists, then answer as "Not possible with current
                       recurring deposits interest rates."
                    9. Do not use the numerical capability of the llm. Always
                       use OptimalActionFixedDepositTool or
                       OptimalActionRecurringDepositTool once you get the
                       deposit schemes list from the sqlite database.
                    10. Take the inflation from the tool 'get_india_inflation'
                        if not mentioned by the user.
                    11. Every deposit schedule element in the table shall have exact start and end
                        dates.
                    Please note that the current time is {current_time2}"""
                            )
        msgs = [sys] + list(state_messages)
    else:
        msgs = state_messages

    response = llm_with_tools.invoke(msgs)
    return {"messages": [response]}


def ToolsNode(state: AdminAgentState):
    messages = convert_to_messages(state['messages'])
    # this has the query we need to send to the tool provided by the agent
    last_message = messages[-1]
    function_messages = []
    tool_calls = (getattr(last_message, "tool_calls", None)
                  or last_message.additional_kwargs.get("tool_calls", []))
    for everyTool in tool_calls[:]:
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
    """Looks up the tool by name in the registry and invokes it with args."""
    result = None
    if TOOL_REGISTRY[toolName] is not None:
        result = TOOL_REGISTRY[toolName].invoke(raw_args)
        return result
    raise ValueError(f"Unknown tool: {toolName}")
    return result


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
    return {"messages": []}


def buildAdminAgentGraph():
    global llm_with_tools
    global TOOL_REGISTRY
    global gRAils
    gRAils = LLMWithGuardrails()
    TOOL_REGISTRY = {
        "GetSqlLiteTablesStructure": GetSqlLiteTablesStructure,
        "GetSqlLiteTableData": GetSqlLiteTableData,
        "OptimalActionFixedDepositTool": OptimalActionFixedDepositTool,
        "OptimalActionRecurringDepositTool": OptimalActionRecurringDepositTool,
        "get_india_inflation": get_india_inflation,
        "GetFinalValueConsideringInflation": GetFinalValueConsideringInflation,
        "WriteMermaidDiagramPage" : WriteMermaidDiagramPage}
    
    load_dotenv()
    llm = ChatOpenAI(
        model="gpt-5",
        temperature=0,
        api_key=os.environ["OPENAI_API_KEY"])
    llm_with_tools = llm.bind_tools(
        TOOL_REGISTRY.values(), parallel_tool_calls=False)

    workflow = StateGraph(AdminAgentState)
    workflow.add_node("AdminAgent", AdminAgentNode)
    workflow.add_node("tool", ToolsNode)
    workflow.add_node("ExitGuardrail", ExitGuardRailNode)
    workflow.add_conditional_edges(START, inputGuardRailCondition, {
        "continue": "AdminAgent", "end": END})
    workflow.add_conditional_edges("AdminAgent", where_to_go, {
        "continue": "tool", "end": "ExitGuardrail"})
    workflow.add_edge('tool', 'AdminAgent')
    workflow.add_edge("ExitGuardrail", END)

    app = workflow.compile().with_config({"recursion_limit": 50})

    return app


graph = buildAdminAgentGraph()

if __name__ == "__main__":
    result = graph.invoke({"messages": [HumanMessage(content="""My age is 48 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month.
Please give the optimal deposit actions to for a period of 16 years from now.""")]})
    print(result["messages"][-1].content)
