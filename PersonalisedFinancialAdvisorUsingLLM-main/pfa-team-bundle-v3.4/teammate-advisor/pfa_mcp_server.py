"""MCP server that puts the teammate's project (PersonalisedFinancialAdvisorUsingLLM) inside the PFA flow.

Their code in teammate/ is used as-is:
  - RagChainForNumericalData.QueryRag      hybrid RAG (BM25 on headings + Chroma vectors, cross-encoder rerank)
                                            over their bank-deposit and mutual-fund documents, answered by gpt-4.1
  - GaurdRails.LLMWithGuardrails            their llm_guard input/output scanners
  - FinancialGeneralInformationChatBot      their guarded LangGraph chatbot (agent + both RAG tools)
  - OptimalBankDepositFinderAgent           their LangGraph deposit agent (the tool their own MCP server publishes)

n8n's chat agents call this server over MCP (streamable HTTP) with the same bearer token as the n8n MCP servers.
Every call is traced to Phoenix (project "pfa-teammate-advisor") with LangChain/LangGraph spans: prompts,
retrieved context, tokens and model.

Two runtime-only changes, both outside their files:
  - the spaCy model and cross-encoder are loaded once and reused (their QueryRag reloads them on every call);
  - the RAG tools run their guardrail scanners directly. LLMWithGuardrails.invoke() also sends the question to
    gpt-4.1 and only prints the reply, which would double the cost of every question for no output.
"""
import concurrent.futures
import functools
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "teammate"))
sys.path.insert(0, os.getcwd())

PHOENIX = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix:6006/v1/traces")
PROJECT = os.environ.get("PHOENIX_PROJECT_NAME", "pfa-teammate-advisor")
TOKEN = os.environ.get("MCP_BEARER_TOKEN", "")
HOST, PORT = os.environ.get("MCP_HOST", "0.0.0.0"), int(os.environ.get("MCP_PORT", "8090"))
TOOL_TIMEOUT = float(os.environ.get("TOOL_TIMEOUT_SECONDS", "120"))

# ---------------------------------------------------------------- tracing (before LangChain is imported)
from opentelemetry import context as otel_context                                  # noqa: E402
from opentelemetry import trace                                                    # noqa: E402
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # noqa: E402
from opentelemetry.sdk.resources import Resource                                   # noqa: E402
from opentelemetry.sdk.trace import TracerProvider                                 # noqa: E402
from opentelemetry.sdk.trace.export import BatchSpanProcessor                      # noqa: E402
from opentelemetry.trace import Status, StatusCode                                 # noqa: E402
from openinference.instrumentation.langchain import LangChainInstrumentor          # noqa: E402

provider = TracerProvider(resource=Resource.create({
    "service.name": "pfa-teammate-advisor", "openinference.project.name": PROJECT}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=PHOENIX)))
LangChainInstrumentor().instrument(tracer_provider=provider)
tracer = provider.get_tracer("pfa-teammate-advisor")

# ---------------------------------------------------------------- the teammate's modules
import spacy                                                                       # noqa: E402
from sentence_transformers import CrossEncoder                                     # noqa: E402
import RagChainForNumericalData as rag                                             # noqa: E402

rag.spacy = types.SimpleNamespace(load=functools.lru_cache(maxsize=None)(spacy.load))
rag.CrossEncoder = functools.lru_cache(maxsize=None)(CrossEncoder)

from langchain_core.messages import HumanMessage                                   # noqa: E402
from llm_guard import scan_output, scan_prompt                                     # noqa: E402
import FinancialGeneralInformationChatBot as chatbot                               # noqa: E402  (builds their RAG handles + chatbot graph)
import OptimalBankDepositFinderAgent as deposit_agent                              # noqa: E402

guard = chatbot.gRAils

# ---------------------------------------------------------------- MCP server
from mcp.server.fastmcp import FastMCP                                             # noqa: E402
from pydantic import Field                                                         # noqa: E402
from starlette.responses import JSONResponse                                       # noqa: E402

mcp = FastMCP("PFA teammate advisor", host=HOST, port=PORT, stateless_http=True, log_level="WARNING")


pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def run_in_context(ctx, run):
    """Runs in a worker thread, inside the MCP call's trace, so LangChain spans nest under it."""
    token = otel_context.attach(ctx)
    try:
        return run()
    finally:
        otel_context.detach(token)


def traced(name, question, run):
    """One Phoenix trace per MCP call; LangChain spans from the teammate's code nest under it.
    Each call has a time limit, so a stuck call can never hold n8n's agent."""
    with tracer.start_as_current_span(f"MCP · {name}") as span:
        span.set_attribute("openinference.span.kind", "CHAIN")
        span.set_attribute("input.value", question)
        ctx = otel_context.get_current()
        try:
            answer = pool.submit(run_in_context, ctx, run).result(timeout=TOOL_TIMEOUT)
        except concurrent.futures.TimeoutError:
            span.set_status(Status(StatusCode.ERROR, f"no answer within {TOOL_TIMEOUT:.0f} s"))
            return f"The teammate service did not answer within {TOOL_TIMEOUT:.0f} seconds. Answer without it."
        except Exception as exc:                                                    # the agent sees a clear message, not a crash
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            return f"The teammate service failed on this request ({type(exc).__name__}). Answer without it."
        span.set_attribute("output.value", answer)
        span.set_status(Status(StatusCode.OK))
        return answer


def guarded_rag(question, handle):
    clean, results = scan_prompt(guard.input_scanners, question)
    if not all(results.values()):
        blocked = ", ".join(k for k, ok in results.items() if not ok)
        return f"Blocked by the teammate's input guardrail ({blocked}). Ask a plain question about deposits or mutual funds."
    answer, _context = rag.QueryRag(clean, handle[0], handle[1])
    _out, out_results = scan_output(guard.output_scanners, clean, answer)
    if not all(out_results.values()):
        return "The teammate's output guardrail withheld this answer."
    return answer


@mcp.tool(name="Ask_Bank_Deposit_Schemes",
          description=("Answers factual questions about named Indian bank deposit schemes from the team's bank documents "
                       "(Axis, Bank of Baroda, Canara, HDFC, ICICI, IDFC FIRST, Kotak, PNB, SBI): features, rates, "
                       "premature-withdrawal penalties, RD rules, senior-citizen benefits, loans/overdraft against FDs."))
def ask_bank_deposit_schemes(question: str = Field(description="One plain-English question about a bank's deposit schemes")) -> str:
    return traced("Ask_Bank_Deposit_Schemes", question, lambda: guarded_rag(question, chatbot.ragHandleBankDeposits))


@mcp.tool(name="Ask_Mutual_Funds",
          description=("Answers factual questions about specific Indian mutual fund schemes from the team's fund summaries: "
                       "SBI Focused, Bank of India Flexi Cap, HDFC Flexi Cap, ICICI Prudential Large Cap, JM Flexi Cap, "
                       "Nippon India Large Cap, Nippon India Small Cap, Parag Parikh Flexi Cap, Quant Flexi Cap - category, "
                       "AMC, NAV, AUM, expense ratio, exit load, minimum investment. Information, not a recommendation."))
def ask_mutual_funds(question: str = Field(description="One plain-English question about a specific mutual fund")) -> str:
    return traced("Ask_Mutual_Funds", question, lambda: guarded_rag(question, chatbot.ragHandleMutualFund))


@mcp.tool(name="Financial_Information_Chat",
          description="The teammate's full guarded chatbot (LangGraph agent over both RAG stores) for a general deposits / mutual funds question.")
def financial_information_chat(question: str = Field(description="The user's question")) -> str:
    def run():
        out = chatbot.graph.invoke({"messages": [HumanMessage(content=question)]})
        return out["messages"][-1].content
    return traced("Financial_Information_Chat", question, run)


@mcp.tool(name="GetBestBankDepositSchemeSequence",
          description=("The teammate's LangGraph deposit agent (experimental): best FD/RD sequence from the present state "
                       "(lump sum, monthly saving) to a goal amount and date. Not wired into n8n: in the current teammate code "
                       "it fails on some inputs (see docs/TEAMMATE_INTEGRATION.md); the advisor uses the n8n deposit planner."))
def get_best_bank_deposit_scheme_sequence(request: str = Field(description="The user's initial state and goal state")) -> str:
    def run():
        out = deposit_agent.graph.invoke({"messages": [HumanMessage(content=request)]})
        return out["messages"][-1].content
    return traced("GetBestBankDepositSchemeSequence", request, run)


REST_TOOLS = {"Ask_Bank_Deposit_Schemes": ask_bank_deposit_schemes, "Ask_Mutual_Funds": ask_mutual_funds,
              "Financial_Information_Chat": financial_information_chat}


@mcp.custom_route("/ask/{tool}", methods=["POST"])
async def ask_rest(request):
    """The same tools as plain HTTP (bearer token required). n8n's agents call these: an HTTP tool connects only
    when it is used, so the advisor's chat keeps working even if this service is down."""
    import asyncio
    fn = REST_TOOLS.get(request.path_params["tool"])
    if not fn:
        return JSONResponse({"error": "unknown tool"}, status_code=404)
    try:
        body = await request.json()
    except Exception:
        body = {}
    question = str(body.get("question") or "").strip()[:2000]
    if not question:
        return JSONResponse({"error": "question is required"}, status_code=400)
    return JSONResponse({"answer": await asyncio.to_thread(fn, question)})


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    return JSONResponse({"status": "ok", "tools": 4, "deposit_chunks": rag.colDict["Deposit"].count(),
                         "mutual_fund_chunks": rag.colDict["MutualFund"].count(), "phoenix_project": PROJECT})


class BearerAuth:
    """Same bearer token as the n8n MCP servers; /health stays open for Docker's health check."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] != "/health" and TOKEN:
            auth = dict(scope["headers"]).get(b"authorization", b"").decode()
            if auth != f"Bearer {TOKEN}":
                await JSONResponse({"error": "missing or wrong bearer token"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


if __name__ == "__main__":
    import uvicorn
    print(f"Teammate MCP server on http://{HOST}:{PORT}/mcp, tracing to {PHOENIX} (project {PROJECT})", flush=True)
    uvicorn.run(BearerAuth(mcp.streamable_http_app()), host=HOST, port=PORT, log_level="warning")
