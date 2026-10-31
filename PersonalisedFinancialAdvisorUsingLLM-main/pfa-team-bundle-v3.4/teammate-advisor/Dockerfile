# The teammate's project (PersonalisedFinancialAdvisorUsingLLM) as a service in the PFA stack.
# Their code in teammate/ runs unchanged; pfa_mcp_server.py publishes it as an MCP server for n8n.
# Models (embeddings, cross-encoder reranker, spaCy, tiktoken) and the two Chroma RAG stores are
# built into the image, so the container starts quickly and works without downloading anything.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/cache/hf \
    TIKTOKEN_CACHE_DIR=/app/cache/tiktoken \
    ANONYMIZED_TELEMETRY=False \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_DOWNLOAD_TIMEOUT=120 \
    HF_HUB_ETAG_TIMEOUT=60

WORKDIR /app

RUN pip install --upgrade pip \
    && pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements-service.txt .
RUN pip install -r requirements-service.txt \
    && pip install --no-deps llm-guard==0.0.2

# Models first, in their own cached layer: resumable downloads with retries, so a slow connection
# doesn't fail the build, and code changes below never download them again.
COPY prefetch_models.py ./
RUN python prefetch_models.py

COPY teammate/ ./teammate/
COPY warmup.py ./
RUN python warmup.py
COPY pfa_mcp_server.py ./

EXPOSE 8090
HEALTHCHECK --interval=15s --timeout=5s --retries=20 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health')"
CMD ["python", "pfa_mcp_server.py"]
