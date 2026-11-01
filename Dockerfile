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

# L'API ne tourne pas en root dans le conteneur
RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000

# forwarded-allow-ips "*" : l'API n'est joignable que par Caddy (réseau Docker, pas de
# port publié). Sans ça tous les visiteurs partagent l'IP de Caddy et les limites
# de requêtes (login, inscription…) s'appliquent au site entier au lieu de chaque client.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
