# RAG backend: Django + DRF + LlamaIndex + Milvus Lite(embedded)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# mysqlclient needs a C compiler + MySQL client headers.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Milvus Lite keeps its data here (volume-mounted below).
RUN mkdir -p /app/data/milvus

EXPOSE 8000

# sync + threads workers stream SSE natively (no ASGI needed);
# --timeout 300 keeps long LLM streams from being cut off.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--threads", "4", \
     "--timeout", "300", "--graceful-timeout", "60"]
