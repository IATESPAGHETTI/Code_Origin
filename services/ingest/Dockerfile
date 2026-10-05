FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" PORT=8201 DATA_DIR=/data
# git is required to clone and read history; repository code is only read, never executed.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home app \
    && mkdir -p /data && chown app /data \
    && git config --system --add safe.directory '*'
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
USER app
VOLUME ["/data"]
EXPOSE 8201
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=10 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen('http://localhost:%s/health' % os.getenv('PORT','8201'))"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
