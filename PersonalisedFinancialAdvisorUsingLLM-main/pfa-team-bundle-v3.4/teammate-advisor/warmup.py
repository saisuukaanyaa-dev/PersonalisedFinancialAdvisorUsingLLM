"""Runs once while the Docker image is built (no OpenAI key needed, nothing is sent to OpenAI).
Downloads the models the teammate's code loads on first use and builds their two Chroma RAG stores,
so the running container never has to fetch anything."""
import os
import sys

os.environ.setdefault("OPENAI_API_KEY", "build-time-placeholder")   # ChatOpenAI() needs a value; no call is made
os.chdir("/app/teammate")
sys.path.insert(0, "/app/teammate")

import spacy                                                          # noqa: E402
import tiktoken                                                       # noqa: E402
from sentence_transformers import CrossEncoder                        # noqa: E402
from RagChainForNumericalData import QueryRagInit, colDict            # noqa: E402

for instrument in ("Deposit", "MutualFund"):
    QueryRagInit(instrument)                                          # embeds the documents into ./chroma_db* (local ONNX model)
    print(f"{instrument}: {colDict[instrument].count()} chunks")
CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")                  # reranker used by QueryRag
spacy.load("en_core_web_sm")
tiktoken.get_encoding("cl100k_base")                                  # llm_guard TokenLimit scanner
from GaurdRails import _banned_substrings                             # noqa: E402  (loads llm_guard and its stop-word list)
print("banned phrases:", len(_banned_substrings()))
print("warm-up done")
