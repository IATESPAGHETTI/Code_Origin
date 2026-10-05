FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/opt/venv/bin:$PATH" PORT=8205 DATA_DIR=/data
RUN useradd --system --uid 10001 --create-home app && mkdir -p /data && chown app /data
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY datasets ./datasets
USER app
VOLUME ["/data"]
EXPOSE 8205
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=10 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen('http://localhost:%s/health' % os.getenv('PORT','8205'))"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
