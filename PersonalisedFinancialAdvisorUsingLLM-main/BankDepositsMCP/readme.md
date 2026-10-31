# Financial Agent & MCP Server Development Guide

Quick reference and execution guide for local development, database creation, LangGraph Studio, and Model Context Protocol (MCP) server inspection for the Bank Deposit Financial Agent.

---

## 📋 Overview of Development Workflow

This setup provides commands to test prompt execution, launch the LangGraph Studio interface, and run or inspect the Model Context Protocol (MCP) server for bank deposit analysis.

---

## 📦 Environment Setup (uv)

The project uses [uv](https://docs.astral.sh/uv/) to manage Python and its dependencies.
Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`; the Python
version is pinned in `.python-version`.

```bash
# Install uv (once): https://docs.astral.sh/uv/getting-started/installation/
uv sync                 # create .venv and install the locked dependencies
uv add <package>        # add a dependency (updates pyproject.toml and uv.lock)
uv lock --upgrade       # upgrade the locked versions
```

Prefix commands with `uv run` (as below) to run them inside the project environment
without activating `.venv`.

---

## 🛠️ Step-by-Step Execution Guide

### 1. Ingest & Prepare Database
Run the complete application against a test prompt to initialize database records and verify tool integration.

```bash
uv run python source/DatabaseCreator.py
```
* **Purpose:** Executes the main data pipeline script for single-prompt end-to-end testing and database initialization.

---

### 2. Optimal Fixed deposit finder
Run the Optimal Fixed deposit finder application against a test prompt.

```bash
uv run python source/OptimalBankDepositFinderAgent.py
```
* **Purpose:** Executes the main data pipeline script for single-prompt end-to-end testing and database initialization.

---

### 3. Financial General Information Chatbot
Run the chatbot that answers general questions about bank deposits and mutual funds.

```bash
uv run python source/FinancialGeneralInformationChatBot.py
```
* **Purpose:** Builds the guarded chatbot graph, which answers bank deposit and mutual fund questions from the RAG databases (loading them on first run).

---

### 4. Launch LangGraph Studio (Dev Mode)
Activate the local LangGraph visual development environment and studio interface.

```bash
uv run python -m langgraph_cli dev
```
* **Purpose:** Starts the interactive LangGraph Studio server to inspect agent state graphs, step-by-step execution chains, and memory states.

---

### 5. Run the MCP Server
Start the Model Context Protocol (MCP) server handling Bank Deposit query capabilities.

```bash
uv run mcp run source/MCPServerForOptimalBankDepositFinderAgent.py
```
* **Purpose:** Launches the production/runtime instance of the Bank Deposit MCP server for client connections.

---

### 6. Inspect & Debug the MCP Server
Run the MCP server in development mode alongside the MCP Inspector UI.

```bash
uv run mcp dev source/MCPServerForOptimalBankDepositFinderAgent.py
```
* **Purpose:** Opens the interactive MCP Inspector UI in your web browser to debug available tools, resources, and prompt templates in real time.

---

## ⚡ Quick Reference Table

| Task | Command | Description |
| :--- | :--- | :--- |
| **Test Application Pipeline** | `uv run python source/DatabaseCreator.py` | Single-prompt test execution & database initialization |
| **Optimal Fixed Deposit Finder** | `uv run python source/OptimalBankDepositFinderAgent.py` | Single-prompt test execution & database initialization |
| **Financial Information Chatbot** | `uv run python source/FinancialGeneralInformationChatBot.py` | Bank deposit & mutual fund Q&A chatbot using the RAG databases |
| **Activate LangGraph Studio** | `uv run python -m langgraph_cli dev` | Interactive graph visualization & agent state debugging |
| **Start MCP Server** | `uv run mcp run source/MCPServerForOptimalBankDepositFinderAgent.py` | Runs the Bank Deposit MCP service |
| **Inspect MCP Server** | `uv run mcp dev source/MCPServerForOptimalBankDepositFinderAgent.py` | Launches MCP Inspector UI for real-time tool testing |
