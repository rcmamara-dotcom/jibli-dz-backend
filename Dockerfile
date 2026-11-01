FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml .
# godata suit une branche git : sans ceci, Docker réutilise le cache et garde
# l'ancienne version tant que pyproject.toml ne change pas.
ADD https://api.github.com/repos/rcmamara-dotcom/jibli-dz-godata/git/refs/heads/develop /tmp/godata-ref.json
RUN uv pip install --system --no-cache .

COPY api/ ./api/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
