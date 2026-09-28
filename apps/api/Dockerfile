FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar pacotes reutilizáveis isolados
COPY packages/ /app/packages/
RUN pip install --no-cache-dir -e /app/packages/inference_gateway
RUN pip install --no-cache-dir -e /app/packages/rag_core

# Copiar e instalar a aplicação API
COPY apps/api/ /app/apps/api/
RUN pip install --no-cache-dir -e /app/apps/api/
RUN pip install --no-cache-dir uvicorn fastapi sse-starlette asyncpg redis structlog pydantic-settings sentence-transformers httpx

ENV PYTHONPATH="/app/packages/inference_gateway/src:/app/packages/rag_core/src:/app/apps/api/src"

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
