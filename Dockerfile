FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# User owns /app up front, so the venv never needs a recursive chown.
RUN useradd --create-home --uid 10001 app && mkdir -p /app && chown app:app /app

WORKDIR /app
USER app

# Dependencies resolve first so a code change does not rebuild this layer.
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY --chown=app:app config.yml settings.py service.py main.py ./
COPY --chown=app:app llm_gateway/ ./llm_gateway/
COPY --chown=app:app model_routing/ ./model_routing/
COPY --chown=app:app Observability/ ./Observability/

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3)"

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8080"]
