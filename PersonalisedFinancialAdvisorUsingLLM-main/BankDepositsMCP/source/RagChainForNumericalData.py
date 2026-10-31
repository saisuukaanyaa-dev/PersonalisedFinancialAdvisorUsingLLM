import chromadb
from langchain_text_splitters import (MarkdownHeaderTextSplitter,
                                      RecursiveCharacterTextSplitter)
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pathlib import Path
import os
from dotenv import load_dotenv
from chromadb.api.models.Collection import Collection
import numpy as np
from sentence_transformers import CrossEncoder
import spacy
from rank_bm25 import BM25Okapi
import re

colDict = {"Deposit": None, "MutualFund": None}


def _GetChunksFromHeirarchicalHeaders(md_text, sourceID, co):
    # MarkdownHeaderTextSplitter expects (markdown_marker, metadata_key)
    # tuples, not the nested title/children tree from
    # _get_hierarchical_headers.
    headers_to_split_on = [
        ("#", "Header_1"),
        ("##", "Header_2"),
        ("###", "Header_3"),
        ("####", "Header_4"),
        ("#####", "Header_5"),
        ("######", "Header_6")
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=True
    )

    header_splits = markdown_splitter.split_text(md_text)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )
    final_chunks = text_splitter.split_documents(header_splits)
    if not final_chunks:
        return

    documents = [doc.page_content for doc in final_chunks]
    metadatas = [doc.metadata for doc in final_chunks]
    metadatasCopy = metadatas.copy()

    for i, eachDoc in enumerate(documents):
        for eachWord in re.findall(r'\- \*\*([^*]+)\*\*:', eachDoc):
            metadatas[i]["keyword"] = eachWord

    metadatas1 = []
    for metadata in metadatas:
        metadata["source"] = sourceID
        metadatas1.append(metadata)

    ids = [f"{sourceID}_chunk_{i}" for i in range(len(final_chunks))]

    docs = []
    for i, eachDoc in enumerate(documents):
        doc = ""
        for key in metadatasCopy[i]:
            doc = doc + key + ": " + metadatasCopy[i][key] + "\n"
        doc = doc + "chunk:\n"
        eachDoc = doc + eachDoc
        docs.append(eachDoc)

    co.upsert(
        documents=docs,
        metadatas=metadatas1,
        ids=ids
    )


def QueryRagInit(financialInstrument):
    load_dotenv()
    if financialInstrument == "Deposit":
        folder_path = Path(
            './IndianBankDeposits/'
            'DetailedDescriptionsOfAllDepositeSchemesOfBanksOfIndia')
        client = chromadb.PersistentClient(path="./chroma_dbBankDeposit")
        collection = client.get_or_create_collection(
            name="hierarchical_docsBankDeposits")
        colDict[financialInstrument] = collection
    else:
        folder_path = Path('./IndianMutualFunds/Summaries')
        client = chromadb.PersistentClient(path="./chroma_dbMutualFund")
        collection = client.get_or_create_collection(
            name="hierarchical_docsMutualFunds")
        colDict[financialInstrument] = collection

    if collection.count() == 0:
        for file_path in folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in {
                    ".md", ".markdown", ".txt"}:
                with open(file_path, 'r', encoding='utf-8') as file:
                    md_data = file.read()
                    _GetChunksFromHeirarchicalHeaders(
                        md_data, sourceID=file_path.stem, co=collection)

    llm = ChatOpenAI(model="gpt-4.1", temperature=0,
                     api_key=os.environ["OPENAI_API_KEY"])
    return financialInstrument, llm


def _SemanticSimilaritySearch(query: str, co: Collection, count: int):
    results = co.query(
        query_texts=[query],
        n_results=count
    )
    return results["documents"][0]


def _Bm25Search(queryWordList: list[str], co: Collection, count: int):
    all_data = co.get(include=["metadatas"])
    heading_texts = [m.values() for m in all_data["metadatas"]]
    tokenized = []
    for H in heading_texts:
        tokens = []
        for h in H:
            tokens.extend(h.lower().split())
        tokenized.append(tokens)
    bm25 = BM25Okapi(tokenized, k1=1.5, b=0.75)
    scores = bm25.get_scores(queryWordList)
    top_idx = np.argsort(scores)[::-1][:count]
    all_data1 = co.get(include=["documents"])
    candidates = [all_data1["documents"][i] for i in top_idx]
    return candidates


def QueryRag(query: str, co: str, llm: ChatOpenAI) -> tuple[str, str]:
    """Retrieve context for the query, ask the LLM, and return the result.

    Returns a tuple of (answer, context).
    """
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(query)

    keywords = []
    for ent in doc.ents:
        keywords.append(ent.text)
    splitKeywords = []
    for keyword in keywords:
        splitKeywords.append(keyword.lower().split(" "))
    apppendedSplitKeywords = []
    for splitKeyword in splitKeywords:
        apppendedSplitKeywords = apppendedSplitKeywords + splitKeyword

    reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    # 8:2 hybrid search
    if [] != apppendedSplitKeywords:
        candidates = _Bm25Search(apppendedSplitKeywords, colDict[co], 15)
        argsort_descending = range(len(candidates))
    else:
        candidates = _SemanticSimilaritySearch(query, colDict[co], 10)
        # rerank using a slow precise reranker.
        pairs = [[query, doc] for doc in candidates]
        scores = reranker.predict(pairs)
        argsort_descending = sorted(
            range(len(candidates)), key=lambda i: scores[i], reverse=True)

    # Make the context.
    context = "\n\n".join(candidates[i] for i in argsort_descending)
    # append to the query and invole llm.
    messages = [
        SystemMessage(
            content=("You are a helpful assistant. Answer the question "
                     "using only the provided context. If the context is "
                     "not sufficient, say you do not know.")
        ),
        HumanMessage(
            content=(f"-------Context:\n{context}\n\n"
                     f"Question: {query}--------")),
    ]
    # pretPrint(messages)
    response = llm.invoke(messages)
    return response.content, context


def pretPrint(messages):
    for msg in messages:
        msg.pretty_print()


__all__ = ["QueryRagInit", "QueryRag"]
