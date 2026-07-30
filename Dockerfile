FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN groupadd --system irma && useradd --system --gid irma --create-home irma
COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
COPY migrations ./migrations
COPY deploy/api-entrypoint.sh /usr/local/bin/irma-api-entrypoint
RUN python -m pip install --upgrade pip \
    && python -m pip install . \
    && chmod +x /usr/local/bin/irma-api-entrypoint \
    && chown -R irma:irma /app
USER irma
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
ENTRYPOINT ["irma-api-entrypoint"]
