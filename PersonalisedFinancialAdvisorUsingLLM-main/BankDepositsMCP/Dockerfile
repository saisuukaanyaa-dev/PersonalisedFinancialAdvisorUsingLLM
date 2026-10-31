# Docker image for the Optimal Bank Deposit Finder MCP server.
#
# Build: docker build -t bank-deposit-mcp .
# Run:   docker run --rm -p 8090:8090 --env-file .env \
#            -v "$(pwd)/memory.db:/app/memory.db" bank-deposit-mcp
# Or simply: docker compose up --build

FROM python:3.13-slim

# Folder holding the .py files (override with --build-arg SOURCE_DIR=...)
ARG SOURCE_DIR=source

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8090 \
    SOURCE_DIR=${SOURCE_DIR}

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the locked dependencies first so this layer is cached across code
# changes. pyproject.toml pins torch to the CPU-only index, so
# sentence-transformers and llm-guard don't pull the multi-GB CUDA wheels.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY ${SOURCE_DIR}/ ./${SOURCE_DIR}/

EXPOSE 8090

CMD ["sh", "-c", "exec python ${SOURCE_DIR}/MCPServerForOptimalBankDepositFinderAgent.py"]
