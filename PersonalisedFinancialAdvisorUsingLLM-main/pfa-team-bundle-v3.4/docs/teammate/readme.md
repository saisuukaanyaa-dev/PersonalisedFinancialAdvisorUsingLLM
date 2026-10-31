# Financial Agent & MCP Server Development Guide

Quick reference and execution guide for local development, database creation, LangGraph Studio, and Model Context Protocol (MCP) server inspection for the Bank Deposit Financial Agent.

---

## 📋 Overview of Development Workflow

This setup provides commands to test prompt execution, launch the LangGraph Studio interface, and run or inspect the Model Context Protocol (MCP) server for bank deposit analysis.

---

## 🛠️ Step-by-Step Execution Guide

### 1. Ingest & Prepare Database
Run the complete application against a test prompt to initialize database records and verify tool integration.

```bash
python DatabaseCreator.py
```
* **Purpose:** Executes the main data pipeline script for single-prompt end-to-end testing and database initialization.

---

### 2. Optimal Fixed deposit finder
Run the Optimal Fixed deposit finder application against a test prompt.

```bash
python OptimalBankDepositFinderAgent.py
```
* **Purpose:** Executes the main data pipeline script for single-prompt end-to-end testing and database initialization.

---

### 3. Financial General Information Chatbot
Run the chatbot that answers general questions about bank deposits and mutual funds.

```bash
python FinancialGeneralInformationChatBot.py
```
* **Purpose:** Builds the guarded chatbot graph, which answers bank deposit and mutual fund questions from the RAG databases (loading them on first run).

---

### 4. Launch LangGraph Studio (Dev Mode)
Activate the local LangGraph visual development environment and studio interface.

```bash
python -m langgraph_cli dev
```
* **Purpose:** Starts the interactive LangGraph Studio server to inspect agent state graphs, step-by-step execution chains, and memory states.

---

### 5. Run the MCP Server
Start the Model Context Protocol (MCP) server handling Bank Deposit query capabilities.

```bash
mcp run .\MCPServerForBestbankDeposit.py
```
* **Purpose:** Launches the production/runtime instance of the Bank Deposit MCP server for client connections.

---

### 6. Inspect & Debug the MCP Server
Run the MCP server in development mode alongside the MCP Inspector UI.

```bash
mcp dev .\MCPServerForBestbankDeposit.py
```
* **Purpose:** Opens the interactive MCP Inspector UI in your web browser to debug available tools, resources, and prompt templates in real time.

---

## ⚡ Quick Reference Table

| Task | Command | Description |
| :--- | :--- | :--- |
| **Test Application Pipeline** | `python DatabaseCreator.py` | Single-prompt test execution & database initialization |
| **Optimal Fixed Deposit Finder** | `python OptimalBankDepositFinderAgent.py` | Single-prompt test execution & database initialization |
| **Financial Information Chatbot** | `python FinancialGeneralInformationChatBot.py` | Bank deposit & mutual fund Q&A chatbot using the RAG databases |
| **Activate LangGraph Studio** | `python -m langgraph_cli dev` | Interactive graph visualization & agent state debugging |
| **Start MCP Server** | `mcp run .\MCPServerForBestbankDeposit.py` | Runs the Bank Deposit MCP service |
| **Inspect MCP Server** | `mcp dev .\MCPServerForBestbankDeposit.py` | Launches MCP Inspector UI for real-time tool testing |
