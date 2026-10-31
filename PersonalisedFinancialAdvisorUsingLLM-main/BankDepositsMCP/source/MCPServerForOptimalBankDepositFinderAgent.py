from mcp.server.fastmcp import FastMCP
from pydantic import Field
from OptimalBankDepositFinderAgent import graph
from langchain_core.messages import HumanMessage
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# use MCP_HOST=0.0.0.0 inside docker so the port is reachable from the host
HOST = os.environ.get("MCP_HOST", "127.0.0.1")
# new port (override with MCP_PORT env var)
PORT = int(os.environ.get("MCP_PORT", 8090))

mcp = FastMCP("DocumentMCP", log_level="ERROR", host=HOST, port=PORT)


@mcp.tool(
    name="GetBestBankDepositSchemeSequence",
    description=("Gets the best bank deposit scheme sequence given the "
                 "present and goal state")
)
def GetBestBankDepositScheme(request: str = Field(
        description=("The request specifies the user's initial state and "
                     "goal state"))):
    result = graph.invoke({"messages": [HumanMessage(content=request)]})
    return result["messages"][-1].content


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
