# syntax=docker/dockerfile:1.7
# Build arg EMBEDDING_BACKEND=sentence (default, real embeddings, CPU torch) or
# hash (tiny image, deterministic embeddings; used by CI smoke tests).
FROM python:3.11-slim AS builder
ARG EMBEDDING_BACKEND=sentence
ENV PIP_NO_CACHE_DIR=1 HF_HOME=/opt/hf
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt
# CPU-only torch first, otherwise pip resolves the multi-GB CUDA wheel set.
RUN if [ "$EMBEDDING_BACKEND" = "sentence" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu && \
      pip install sentence-transformers==3.0.1 && \
      python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"; \
    else mkdir -p /opt/hf; fi

FROM python:3.11-slim
ARG EMBEDDING_BACKEND=sentence
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" HF_HOME=/opt/hf HF_HUB_OFFLINE=1 \
    EMBEDDING_BACKEND=${EMBEDDING_BACKEND} PORT=8202
RUN useradd --system --uid 10001 --create-home app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf /opt/hf
COPY app ./app
USER app
EXPOSE 8202
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=10 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen('http://localhost:%s/health' % os.getenv('PORT','8202'))"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
