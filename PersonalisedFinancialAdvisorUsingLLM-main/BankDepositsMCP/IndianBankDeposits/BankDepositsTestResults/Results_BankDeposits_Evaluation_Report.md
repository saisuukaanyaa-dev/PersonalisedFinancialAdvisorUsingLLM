**Bank Deposit RAG System Benchmark Evaluation Report**

*Comprehensive 5-Metric Evaluation Across 49 Test Scenarios (Results_BankDeposits.csv)*

# 1. Executive Evaluation Summary

This report evaluates the RAG (Retrieval-Augmented Generation) system performance across **49 test queries** covering retail bank deposit schemes across 9 major Indian banks (Axis, BoB, Canara, HDFC, ICICI, IDFC FIRST, Kotak Mahindra, PNB, and SBI). The benchmark assesses five core RAG metrics: Faithfulness, Context Relevance, Answer Relevance, Context Recall, and Answer Correctness.

## Overall Metric Averages

| **Metric Name** | **Average Score** | **System Performance Status** |
|----|----|----|
| Faithfulness | 91.49% | 91.5% — High Groundedness; minimal hallucination |
| Context Relevance | 94.98% | 95.0% — Excellent retrieval chunk alignment |
| Answer Relevance | 99.76% | 99.8% — Near-perfect question coverage |
| Context Recall | 92.24% | 92.2% — Strong ground-truth context capture |
| Answer Correctness | 85.69% | 85.7% — High factual & numerical accuracy |

# 2. Detailed Row-by-Row Metric Benchmark (49 Test Cases)

| **Row** | **Question** | **Faithfulness** | **Ctx Rel** | **Ans Rel** | **Ctx Rec** | **Correctness** |
|----|----|----|----|----|----|----|
| 0 | Please give the Executive summary of Axis Bank deposit schemes | 0.84 | 1.00 | 1.00 | 1.00 | 0.84 |
| 1 | What are the key deposit metrics and rates of Axis Bank Fixed Deposits? | 0.87 | 1.00 | 1.00 | 0.98 | 0.96 |
| 2 | How does the Axis Bank Auto Fixed Deposit (Sweep-In) work? | 0.76 | 1.00 | 1.00 | 0.98 | 0.90 |
| 3 | What is Axis Bank Fixed Deposit Plus? | 0.84 | 1.00 | 1.00 | 0.94 | 0.93 |
| 4 | What are the Recurring Deposit (RD) rules and penalties for Axis Bank? | 0.95 | 1.00 | 1.00 | 1.00 | 0.89 |
| 5 | What overdraft and credit card facilities are offered against Axis Bank FDs? | 0.94 | 0.80 | 1.00 | 0.96 | 0.96 |
| 6 | Please give the Executive summary of Bank of Baroda deposit schemes | 0.85 | 1.00 | 1.00 | 0.97 | 0.96 |
| 7 | What are the key deposit rates of Bank of Baroda Fixed Deposits? | 0.93 | 1.00 | 1.00 | 0.97 | 0.93 |
| 8 | What is Baroda Advantage Fixed Deposit in Bank of Baroda? | 0.91 | 1.00 | 1.00 | 0.96 | 0.95 |
| 9 | What are the features of bob SDP (Systematic Deposit Plan)? | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| 10 | What are the interest rates for Baroda Tax Savings Fixed Deposit? | 1.00 | 1.00 | 1.00 | 0.98 | 0.67 |
| 11 | Please give the Executive summary of Canara Bank deposit schemes | 0.88 | 1.00 | 1.00 | 0.98 | 0.91 |
| 12 | What are the key deposit rates for Canara Bank Fixed Deposits? | 0.99 | 1.00 | 1.00 | 0.97 | 0.95 |
| 13 | How does the Nitya Nidhi Deposit (NND) Pigmy scheme work at Canara Bank? | 0.92 | 1.00 | 1.00 | 0.93 | 0.91 |
| 14 | What is Canara Dhanvarsha Flexible Recurring Deposit? | 0.96 | 1.00 | 1.00 | 0.93 | 0.96 |
| 15 | What is Kamadhenu Deposit at Canara Bank? | 0.92 | 1.00 | 1.00 | 0.95 | 0.95 |
| 16 | What is the premature withdrawal penalty on Canara Bank Recurring Deposits? | 0.97 | 1.00 | 1.00 | 0.97 | 0.93 |
| 17 | Please give the Executive summary of HDFC Bank deposit schemes | 0.85 | 1.00 | 1.00 | 0.95 | 0.91 |
| 18 | What are the key interest rates for HDFC Bank Fixed Deposits? | 0.99 | 1.00 | 1.00 | 0.98 | 0.96 |
| 19 | What is HDFC Bank HealthCover Fixed Deposit? | 0.90 | 1.00 | 1.00 | 0.96 | 0.92 |
| 20 | What is the Super Saver Facility (Overdraft against FD) at HDFC Bank? | 0.88 | 1.00 | 1.00 | 0.89 | 0.78 |
| 21 | What is HDFC Bank My Passion Fund? | 1.00 | 0.80 | 1.00 | 0.98 | 0.94 |
| 22 | What are the standard Recurring Deposit (RD) rules at HDFC Bank? | 0.97 | 1.00 | 1.00 | 1.00 | 0.95 |
| 23 | Please give the Executive summary of ICICI Bank deposit schemes | 0.77 | 1.00 | 1.00 | 0.92 | 0.89 |
| 24 | What are the key deposit rates of ICICI Bank Fixed Deposits? | 0.94 | 1.00 | 1.00 | 0.97 | 0.95 |
| 25 | What is ICICI Bank Golden Years Fixed Deposit? | 0.88 | 1.00 | 1.00 | 0.95 | 0.94 |
| 26 | How does ICICI Bank iWish Flexible RD work? | 0.81 | 0.80 | 1.00 | 0.98 | 0.90 |
| 27 | What are ICICI Bank Delightful Deposits? | 0.93 | 1.00 | 1.00 | 0.93 | 0.89 |
| 28 | What are the premature withdrawal penalties for ICICI Bank RDs? | 1.00 | 1.00 | 1.00 | 1.00 | 0.71 |
| 29 | Please give the Executive summary of IDFC FIRST Bank deposit schemes | 0.81 | 1.00 | 1.00 | 1.00 | 0.94 |
| 30 | What are the key interest rates for IDFC FIRST Bank Fixed Deposits? | 0.98 | 1.00 | 1.00 | 0.97 | 0.95 |
| 31 | What is special about IDFC FIRST Bank Recurring Deposits? | 0.94 | 1.00 | 1.00 | 0.89 | 0.32 |
| 32 | What premature withdrawal benefits do senior citizens get at IDFC FIRST Bank? | 1.00 | 0.67 | 0.88 | 0.98 | 0.53 |
| 33 | Please give the Executive summary of Kotak Mahindra Bank deposit schemes | 0.84 | 1.00 | 1.00 | 1.00 | 0.90 |
| 34 | What are the key interest rates for Kotak Mahindra Bank Term Deposits? | 1.00 | 0.80 | 1.00 | 0.97 | 0.96 |
| 35 | How does Kotak ActiveMoney (Dynamic Sweep-In) work? | 0.94 | 0.47 | 1.00 | 0.89 | 0.85 |
| 36 | What are the Recurring Deposit (RD) rules and caps at Kotak Mahindra Bank? | 0.91 | 1.00 | 1.00 | 1.00 | 0.97 |
| 37 | Please give the Executive summary of Punjab National Bank deposit schemes | 0.87 | 1.00 | 1.00 | 0.96 | 0.91 |
| 38 | What are the key interest rates across age tiers for PNB Fixed Deposits? | 0.95 | 1.00 | 1.00 | 0.98 | 0.91 |
| 39 | How does PNB Sugam Term Deposit differ from standard FDs? | 0.72 | 1.00 | 1.00 | 0.97 | 0.93 |
| 40 | What is PNB Sugam Plus (444 Days Scheme)? | 0.94 | 0.53 | 1.00 | 0.97 | 0.93 |
| 41 | What are the Recurring Deposit rules and late fee policies at PNB? | 0.97 | 1.00 | 1.00 | 0.97 | 0.95 |
| 42 | Please give the Executive summary of State Bank of India deposit schemes | 0.88 | 1.00 | 1.00 | 0.91 | 0.92 |
| 43 | What are the core interest rates for SBI Retail Domestic Term Deposits? | 0.99 | 1.00 | 1.00 | 0.96 | 0.90 |
| 44 | What is SBI Amrit Vrishti 444 Days Special Scheme? | 0.95 | 0.87 | 1.00 | 0.97 | 0.97 |
| 45 | What benefits do SBI WeCare and SBI Patrons schemes provide? | 0.94 | 0.80 | 1.00 | 0.97 | 0.93 |
| 46 | What is SBI Sarvottam Non-Callable Term Deposit? | 0.88 | 1.00 | 1.00 | 0.94 | 0.93 |
| 47 | How does SBI Multi Option Deposit Scheme (MODS) work? | 0.87 | 1.00 | 1.00 | 0.92 | 0.95 |
| 48 | What are the rules and late fees for SBI Recurring Deposits? | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
