from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
import json
from datetime import datetime
from langchain_core.messages import (BaseMessage, SystemMessage, ToolMessage,
                                     AIMessage, HumanMessage,
                                     convert_to_messages)
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import sqlite3
from langchain.prompts import PromptTemplate
import os
from dotenv import load_dotenv
import signal

if not hasattr(signal, "SIGALRM"):
    signal.SIGALRM = signal.SIGTERM  # dummy value so the attribute exists
    # no-op, since Windows can't do real timers via signal anyway
    signal.alarm = lambda seconds: None


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


class UpdateSqlLiteTableDataReturnSchema(BaseModel):
    status: bool = Field(
        description=("bool data where 'True' represents successful "
                     "execution, 'False' represents unsuccessful execution"))


class UpdateSqlLiteTableDataArgsSchema(BaseModel):
    updateDataQuerry: str = Field(
        description="sql querry to update the table data")


@tool(args_schema=UpdateSqlLiteTableDataArgsSchema)
def UpdateSqlLiteUserDataTable(
        updateDataQuerry) -> UpdateSqlLiteTableDataReturnSchema:
    """Updates the table data. using the given querry
    Args:
        updateDataQuerry: Querry to update the data
    Returns:
        None
    """
    try:
        conn = sqlite3.connect("memory.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(updateDataQuerry)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        # Return the error message directly to the LLM so it can debug itself
        print(f"Database Error: {e}. Please check your column and table "
              "names and try again.")
        return False
    return True


class GetSqlLiteTableDataReturnSchema(BaseModel):
    status: bool = Field(
        description=("bool data where 'True' represents successful "
                     "execution, 'False' represents unsuccessful execution"))
    dataRows: list[tuple] = Field(description="list of tuples of rows")


class GetSqlLiteTableDataArgsSchema(BaseModel):
    readDataQuery: str = Field(description="sql query to read the table data")


@tool(args_schema=GetSqlLiteTableDataArgsSchema)
def GetSqlLiteUserDataTable(readDataQuery) -> GetSqlLiteTableDataReturnSchema:
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


class UserChatAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


def UserChatAgentNode(state: UserChatAgentState):
    # prepend a system instruction once, then ask the model
    current_time2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state_messages = convert_to_messages(state["messages"])
    if not any(m.type == "system" for m in state_messages):
        sys = SystemMessage(content=f"""You are a helpful Financial AI
            assistant who can query the data from the user and fill the user
            data table.
            Your activities may include:
            1. Get the column names from the user_data table to probe the
               information from the user.
            1. Probe the user to fill the entry in the table user_data.
               Regarding which fields to query, please look at the column names
               of the user data table.
            2. Add and modify the user data table's data using the tool
               'UpdateSqlLiteUserDataTable'
            3. Read the user data  table's content using the tool
               'GetSqlLiteUserDataTable'

            CRITICAL ROUTING RULES:
            1. if tool call is not needed and user probing is needed, you MUST
               output the exact tag "[NEEDS_PROBING]" at the very beginning of
               your response, followed by a description of what is missing.
            2. If you have all the information, do NOT include the tag.

            hints:
            1. Please introduce yourself as "I am a financial advisor who can
               give action points to you based on your present profile and the
               goal profile.
            2. Please inform the user to enter all the data needed to fill a
               single row of the user data table. Prompt for exact field names.
            3. List down only the pending items to be given by the user at any
               point of time. Iterate all untill all the data is given by the
               user.
            3. All this work can be done by finding out the required Sql
               Queries and passing them to the tool, when the user supplied the
               data.
            5. Please ignore any redundant actions prescribed by user, if
               already completed in the past. Ask for the confirmation, when in
               doubt.
            6. Do not make an extra tool call if the required data is already
               there in the context.
            7. If the user questions or responds about unrelated user's profile
               or goal profile data, answer as "Only the action points will be
               revealed once all the data is inputed, no intermediary questons
               will be answered"

            Please note that the current time is {current_time2}"""
                            )
        msgs = [sys] + list(state_messages)
    else:
        msgs = state_messages

    response = llm_with_tools.invoke(msgs)
    return {"messages": [response]}


def UserInputNode(state: UserChatAgentState):
    messages = state['messages']
    last_message = messages[-1]
    userInput = input(last_message.content)
    hum = HumanMessage(content=userInput)
    return {"messages": [hum]}


def invoke_tool(toolName: str, raw_args: dict):
    """Looks up the tool by name in the registry and invokes it with args."""
    result = None
    if TOOL_REGISTRY[toolName] is not None:
        result = TOOL_REGISTRY[toolName].invoke(raw_args)
        return result
    raise ValueError(f"Unknown tool: {toolName}")


def ToolsNode(state: UserChatAgentState):
    messages = state['messages']
    # this has the query we need to send to the tool provided by the agent
    last_message = messages[-1]
    function_messages = []
    for everyTool in last_message.additional_kwargs['tool_calls'][:]:
        parsed_tool_input = everyTool['function']['arguments']
        tool_name = everyTool['function']['name']
        tool_input = (json.loads(parsed_tool_input))
        tool_call_id = everyTool['id']
        tool_response = invoke_tool(tool_name, tool_input)
        function_messages.append(ToolMessage(content=str(tool_response),
                                             name=tool_name,
                                             tool_call_id=tool_call_id))
    return {"messages": function_messages}


def where_to_go(state: UserChatAgentState):
    last_msg = state["messages"][-1]
    # If the assistant asked to call tools, LangChain exposes them as
    # `tool_calls`
    if isinstance(last_msg, AIMessage):
        if getattr(last_msg, "tool_calls", None):
            return "toTool"
        elif "NEEDS_PROBING" in last_msg.content:
            return "toProbe"
        else:
            return "end"

    return "end"


def buildUserChatAgentGraph():
    global llm_with_tools
    global TOOL_REGISTRY
    TOOL_REGISTRY = {"GetSqlLiteTablesStructure": GetSqlLiteTablesStructure,
                     "UpdateSqlLiteUserDataTable": UpdateSqlLiteUserDataTable,
                     "GetSqlLiteUserDataTable": GetSqlLiteUserDataTable}
    load_dotenv()
    llm = ChatOpenAI(model="gpt-4.1", temperature=0,
                     api_key=os.environ["OPENAI_API_KEY"])

    workflow = StateGraph(UserChatAgentState)
    workflow.add_node("UserChatAgent", UserChatAgentNode)
    workflow.add_node("tool", ToolsNode)
    workflow.add_node("User input", UserInputNode)
    workflow.add_edge(START, "UserChatAgent")
    workflow.add_conditional_edges("UserChatAgent", where_to_go, {
        "toTool": "tool", "toProbe": "User input", "end": END})
    workflow.add_edge('tool', 'UserChatAgent')
    workflow.add_edge('User input', 'UserChatAgent')

    app = workflow.compile().with_config({"recursion_limit": 50})

    return app


graph = buildUserChatAgentGraph()

result = graph.invoke({"messages": []})
print(result["messages"][-1].content)
