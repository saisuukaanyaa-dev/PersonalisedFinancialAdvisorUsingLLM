import csv
import os
import re
from pathlib import Path
from dotenv import load_dotenv
# Load .env first so the LANGSMITH_* variables are set before the graph and LangSmith client are created
load_dotenv()
import langsmith as ls
from langsmith import Client
from langchain_core.messages import (BaseMessage, SystemMessage, HumanMessage, ToolMessage,
                                     AIMessage, convert_to_messages)
from OptimalBankDepositFinderAgent import graph



PROMPT_DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "verification" / "promptDictionary.md"
RESULTS_CSV_PATH = Path(__file__).resolve().parent.parent / "verification" / "BankDepositEndToEndTestResults.csv"


def getTestPrompts(promptDictionaryPath = PROMPT_DICTIONARY_PATH):
    """Return the test prompts of Parts B (General Public), C (Senior Citizen) and
    D (Super Senior Citizen) of promptDictionary.md, in file order."""
    text = Path(promptDictionaryPath).read_text(encoding = "utf-8")
    testPromptParts = re.search(r"^## Part B\..*?(?=^## Part E\.)", text, flags = re.MULTILINE | re.DOTALL)
    if testPromptParts is None:
        raise ValueError("Parts B to D not found in " + str(promptDictionaryPath))
    return [prompt.strip() for prompt in re.findall(r"```text\r?\n(.*?)```", testPromptParts.group(0), flags = re.DOTALL)]


def writeResultsToCsv(rows, csvPath = RESULTS_CSV_PATH):
    """Write [testPrompt, finalResult] rows to a new CSV file with a header row."""
    csvPath = Path(csvPath)
    csvPath.parent.mkdir(parents = True, exist_ok = True)
    # utf-8-sig so Excel opens the file with the right encoding; newline="" is required by csv.writer
    with open(csvPath, "w", newline = "", encoding = "utf-8-sig") as csvFile:
        writer = csv.writer(csvFile)
        writer.writerow(["test_prompt", "final_result"])
        writer.writerows(rows)
    print("Results written to " + str(csvPath))


def getLangSmithSettings():
    """Read LANGSMITH_TRACING, LANGSMITH_ENDPOINT, LANGSMITH_API_KEY and LANGSMITH_PROJECT
    from the environment (.env). Return (tracingEnabled, client, projectName)."""
    tracingEnabled = os.getenv("LANGSMITH_TRACING", "false").strip().lower() == "true"
    apiKey = os.getenv("LANGSMITH_API_KEY")
    endpoint = os.getenv("LANGSMITH_ENDPOINT")
    projectName = os.getenv("LANGSMITH_PROJECT", "default")
    if tracingEnabled and not apiKey:
        print("LANGSMITH_TRACING is true but LANGSMITH_API_KEY is missing; tracing disabled.")
        return False, None, projectName
    if not tracingEnabled:
        return False, None, projectName
    client = Client(api_url = endpoint, api_key = apiKey)
    return True, client, projectName


def BankDepositTestEndToEndTestfunction():
    testPrompts = getTestPrompts()
    tracingEnabled, client, projectName = getLangSmithSettings()
    rows = []
    for testIndex, everyTestPrompt in enumerate(testPrompts[:9]):
        # Each test case becomes its own trace in the LangSmith project
        with ls.tracing_context(enabled = tracingEnabled, client = client, project_name = projectName):
            result = graph.invoke({"messages": [HumanMessage(content = everyTestPrompt)]},
                                  config = {"run_name": "BankDepositEndToEndTest-" + str(testIndex),
                                            "tags": ["BankDepositEndToEndTest"],
                                            "metadata": {"test_index": testIndex,
                                                         "test_prompt": everyTestPrompt}})
        finalResult = result["messages"][-1].content
        print(finalResult)
        rows.append([everyTestPrompt, finalResult])
    writeResultsToCsv(rows)
    if client is not None:
        client.flush()  # make sure all traces are uploaded before the process exits


if __name__ == "__main__":
    BankDepositTestEndToEndTestfunction()