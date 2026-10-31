from typing import List, Dict, Sequence
import math
import csv
from pathlib import Path
from RagChainForNumericalData import QueryRagInit, QueryRag

_ROOT = Path(__file__).resolve().parent
_BANK_DEPOSIT_TEST_CASES_PATH = _ROOT / \
    "IndianBankDeposits" / "TestCases_BankDeposits.csv"
_MUTUAL_FUND_TEST_CASES_PATH = _ROOT / \
    "IndianMutualFunds" / "TestCases_MutualFunds.csv"
_BANK_DEPOSIT_RESULTS_PATH = _ROOT / \
    "IndianBankDeposits" / "Results_BankDeposits.csv"
_MUTUAL_FUND_RESULTS_PATH = _ROOT / \
    "IndianMutualFunds" / "Results_MutualFunds.csv"
_RESULTS_FIELDNAMES = ["Question",
                       "Expected answer", "Context", "Actual answer"]


def load_test_cases(csv_path: Path) -> List[Dict[str, str]]:
    """Read Question / Expected answer CSV into row dicts."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            {
                "question": (row.get("Question") or "").strip(),
                "expected_answer": (row.get("Expected answer") or "").strip(),
            }
            for row in reader
            if (row.get("Question") or "").strip()
        ]


def save_results(csv_path: Path, test_cases: List[Dict[str, str]]) -> None:
    """Write evaluation results CSV with Context and Actual answer columns."""
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=_RESULTS_FIELDNAMES, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for test_case in test_cases:
            writer.writerow(
                {
                    "Question": test_case.get("question", ""),
                    "Expected answer": test_case.get("expected_answer", ""),
                    "Context": test_case.get("context", ""),
                    "Actual answer": test_case.get("actual_answer", ""),
                }
            )


def _evaluate_test_cases(
    test_cases: List[Dict[str, str]],
    results_path: Path,
    financial_instrument: str,
) -> List[Dict[str, str]]:
    """Run RAG for each question and write the results CSV.

    Each result row holds the context and the actual answer.
    """
    instrument, llm = QueryRagInit(financial_instrument)
    results: List[Dict[str, str]] = []
    for test_case in test_cases:
        question = test_case["question"]
        actual_answer, context = QueryRag(question, instrument, llm)
        results.append(
            {
                "question": question,
                "expected_answer": test_case["expected_answer"],
                "context": context,
                "actual_answer": actual_answer,
            }
        )
    save_results(results_path, results)
    return results


def evaluate_bank_deposit_test_cases() -> List[Dict[str, str]]:
    return _evaluate_test_cases(
        bank_deposit_test_cases,
        _BANK_DEPOSIT_RESULTS_PATH,
        "Deposit",
    )


def evaluate_mutual_fund_test_cases() -> List[Dict[str, str]]:
    return _evaluate_test_cases(
        mutual_fund_test_cases,
        _MUTUAL_FUND_RESULTS_PATH,
        "MutualFund",
    )


# Program variables holding source test cases (question / expected)
bank_deposit_test_cases = load_test_cases(_BANK_DEPOSIT_TEST_CASES_PATH)
mutual_fund_test_cases = load_test_cases(_MUTUAL_FUND_TEST_CASES_PATH)
evaluate_bank_deposit_test_cases()
evaluate_mutual_fund_test_cases()


# Retrival metrics
def hit_at_k(retrieved_ids: Sequence[str],
             gold_ids: Sequence[str], k: int) -> float:
    # Consider only the top-k retrieved document IDs
    top_k = retrieved_ids[:k]
    # If ANY of the correct (gold) document IDs appear in the top-k → return
    # 1.0, else 0.0
    return 1.0 if any(g in top_k for g in gold_ids) else 0.0


def mrr_at_k(retrieved_ids: Sequence[str],
             gold_ids: Sequence[str], k: int) -> float:
    # Look only at the top-k retrieved document IDs
    top_k = retrieved_ids[:k]

    # Find the first correct document and return its reciprocal rank
    for rank, doc_id in enumerate(top_k, start=1):
        if doc_id in gold_ids:
            return 1.0 / rank   # Higher rank → higher score

    # If no correct document appears in top-k, score is 0
    return 0.0


def ndcg_at_k(retrieved_ids: Sequence[str],
              gold_ids: Sequence[str], k: int) -> float:
    # Assign gain = 1 for relevant docs, 0 for non-relevant docs
    gains = [1.0 if doc_id in gold_ids else 0.0
             for doc_id in retrieved_ids[:k]]

    # Compute DCG (Discounted Cumulative Gain)
    dcg = 0.0
    for i, g in enumerate(gains, start=1):
        if g > 0:
            dcg += g / math.log2(i + 1)  # Relevance discounted by log(rank)

    # Compute ideal DCG (best possible ranking)
    ideal_gains = sorted(gains, reverse=True)
    idcg = 0.0

    for i, g in enumerate(ideal_gains, start=1):
        if g > 0:
            idcg += g / math.log2(i + 1)

    # NDCG = DCG normalized by the best possible DCG
    return dcg / idcg if idcg > 0 else 0.0
