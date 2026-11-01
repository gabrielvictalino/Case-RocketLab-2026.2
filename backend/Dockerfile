# syntax=docker/dockerfile:1
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock .python-version README.md ./
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY ai-agent/pyproject.toml ./ai-agent/pyproject.toml
COPY importador/pyproject.toml ./importador/pyproject.toml
# Dependências externas ficam em camada reutilizável quando só o código muda.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --all-packages --no-dev --no-install-workspace
COPY backend ./backend
COPY ai-agent ./ai-agent
COPY importador ./importador
COPY contracts ./contracts
RUN chmod -R a+rX /app
# O segredo é opcional fora do ambiente gerenciado; nunca desabilita TLS.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --frozen --all-packages --no-dev
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
