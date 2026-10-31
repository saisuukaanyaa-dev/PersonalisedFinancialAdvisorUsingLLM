import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def extract_numerical_facts(text: str) -> set:
    """Extracts exact numerical expressions.

    Covers percentages, currency figures and tenure months/years.
    """
    if not isinstance(text, str):
        return set()
    # Match numbers, percentages, currency, and ranges (e.g., 7.10%, ₹5,000,
    # 444 days, 12-120 months)
    pattern = (r'(\b\d+(?:\.\d+)?%?'
               r'|\b₹\s*\d+(?:,\d+)*(?:\.\d+)?'
               r'|\b\d+\s*(?:days|months|years|bps|Cr|Crore|Lakhs)\b)')
    return set(re.findall(pattern, text, flags=re.IGNORECASE))


def tokenize_clean(text: str) -> list[str]:
    """Tokenizes text into lowercase alphanumeric words."""
    if not isinstance(text, str):
        return []
    return re.findall(r'\b\w+\b', text.lower())


def sentence_split(text: str) -> list[str]:
    """Splits text into discrete sentences/claims."""
    if not isinstance(text, str):
        return []
    sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]


# --- 1. CONTEXT RECALL ---
def calculate_context_recall(expected: str, context: str) -> float:
    """Measures what proportion of Expected Answer statements are in Context.
    """
    exp_claims = sentence_split(expected)
    if not exp_claims:
        return 1.0

    ctx_tokens = set(tokenize_clean(context))
    if not ctx_tokens:
        return 0.0

    recalled_count = 0
    for claim in exp_claims:
        claim_tokens = set(tokenize_clean(claim))
        if not claim_tokens:
            continue
        overlap = len(claim_tokens.intersection(
            ctx_tokens)) / len(claim_tokens)
        if overlap >= 0.50:  # Claim captured if 50%+ key tokens match
            recalled_count += 1

    return round(recalled_count / len(exp_claims), 4)


# --- 2. CONTEXT RELEVANCE ---
def calculate_context_relevance(
        question: str, context: str, beta: float = 1.0) -> float:
    """Calculates F_beta score of context sentences relevant to Question."""
    q_tokens = set(tokenize_clean(question))
    ctx_sentences = sentence_split(context)
    if not ctx_sentences or not q_tokens:
        return 0.0

    relevant_sentences = 0
    for sent in ctx_sentences:
        sent_tokens = set(tokenize_clean(sent))
        overlap = len(q_tokens.intersection(sent_tokens))
        if overlap >= 1:  # Sentence addresses query terms
            relevant_sentences += 1

    precision = relevant_sentences / len(ctx_sentences)
    recall = min(1.0, relevant_sentences / max(1, len(q_tokens)))

    if precision + recall == 0:
        return 0.0

    # F_beta weighting
    f_beta = (1 + beta**2) * (precision * recall) / \
        ((beta**2 * precision) + recall)
    return round(f_beta, 4)


# --- 3. ANSWER RELEVANCE ---
def calculate_answer_relevance(question: str, actual: str) -> float:
    """Measures how directly the Actual Answer addresses the Question."""
    if "not contain" in actual.lower() or "do not know" in actual.lower():
        return 0.50  # Faithful refusal penalty

    q_tokens = set(tokenize_clean(question))
    ans_tokens = set(tokenize_clean(actual))
    if not q_tokens or not ans_tokens:
        return 0.0

    overlap = len(q_tokens.intersection(ans_tokens)) / len(q_tokens)
    # Scale overlap to a normalized relevance score [0.0, 1.0]
    return round(min(1.0, 0.5 + 0.5 * (overlap / max(1, len(q_tokens)))), 4)


# --- 4. FAITHFULNESS ---
def calculate_faithfulness(actual: str, context: str) -> float:
    """Measures if Actual Answer statements are strictly supported by Context.
    """
    # Faithful refusal check
    if "not contain" in actual.lower() or "do not know" in actual.lower():
        return 1.0  # Refusing ungrounded answers is 100% faithful

    ans_claims = sentence_split(actual)
    if not ans_claims:
        return 1.0

    ctx_tokens = set(tokenize_clean(context))
    supported_claims = 0

    for claim in ans_claims:
        claim_tokens = set(tokenize_clean(claim))
        if not claim_tokens:
            continue
        overlap = len(claim_tokens.intersection(
            ctx_tokens)) / len(claim_tokens)
        if overlap >= 0.40:
            supported_claims += 1

    return round(supported_claims / len(ans_claims), 4)


# --- 5. ANSWER CORRECTNESS ---
def calculate_answer_correctness(expected: str, actual: str) -> float:
    """Measures semantic and exact numerical agreement.

    Compares the Expected and Actual answers.
    """
    # Refusal handling
    if "not contain" in actual.lower() or "do not know" in actual.lower():
        return 0.0 if len(expected) > 20 else 1.0

    # Semantic similarity using TF-IDF Cosine Distance
    vectorizer = TfidfVectorizer().fit([expected, actual])
    tfidf = vectorizer.transform([expected, actual])
    sem_sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]

    # Numerical & Factual Exact Match
    exp_nums = extract_numerical_facts(expected)
    act_nums = extract_numerical_facts(actual)

    num_match = 1.0
    if exp_nums:
        num_match = len(exp_nums.intersection(act_nums)) / len(exp_nums)

    # Combined Correctness Score
    # (60% Numerical/Factual Match + 40% Semantic Similarity)
    correctness = (0.60 * num_match) + (0.40 * sem_sim)
    return round(float(correctness), 4)


def evaluate_dataset(file_path: str, output_path: str):
    """Loads CSV dataset, runs evaluation pipeline, saves evaluated dataset."""
    df = pd.read_csv(file_path)

    faithfulness_list = []
    ctx_rel_list = []
    ans_rel_list = []
    ctx_rec_list = []
    correctness_list = []

    for _, row in df.iterrows():
        q = str(row['Question'])
        exp = str(row['Expected answer'])
        ctx = str(row['Context'])
        act = str(row['Actual answer'])

        faith = calculate_faithfulness(act, ctx)
        c_rel = calculate_context_relevance(q, ctx, beta=1.0)
        a_rel = calculate_answer_relevance(q, act)
        c_rec = calculate_context_recall(exp, ctx)
        corr = calculate_answer_correctness(exp, act)

        faithfulness_list.append(faith)
        ctx_rel_list.append(c_rel)
        ans_rel_list.append(a_rel)
        ctx_rec_list.append(c_rec)
        correctness_list.append(corr)

    df['Faithfulness'] = faithfulness_list
    df['Context Relevance'] = ctx_rel_list
    df['Answer Relevance'] = ans_rel_list
    df['Context Recall'] = ctx_rec_list
    df['Correctness'] = correctness_list

    df.to_csv(output_path, index=False)
    print(f"Evaluated dataset saved to {output_path}")
    print("\n--- Summary Averages ---")
    print(df[['Faithfulness', 'Context Relevance', 'Answer Relevance',
          'Context Recall', 'Correctness']].mean())


if __name__ == "__main__":
    # Example usage for Bank Deposits or Mutual Funds results
    evaluate_dataset("Results_BankDeposits.csv",
                     "Results_BankDeposits_Evaluated.csv")
