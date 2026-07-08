#!/usr/bin/env bash
# Usage: ./deploy.sh [--no-frontend]
# Lance depuis le dossier deploy/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$(dirname "$BACKEND_DIR")/jibli-dz"

echo "▶ JIBLI DZ — déploiement"

# ── 1. Build du frontend ──────────────────────────────────────────────────────
if [[ "${1:-}" != "--no-frontend" ]]; then
  if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "⚠ Dossier frontend introuvable : $FRONTEND_DIR"
    echo "  Clone le repo : git clone https://github.com/rcmamara-dotcom/jibli-dz $FRONTEND_DIR"
    exit 1
  fi

  echo "→ Build frontend..."
  cd "$FRONTEND_DIR"
  npm ci --prefer-offline
  npx vite build

  echo "→ Copie des fichiers statiques dans deploy/frontend/..."
  rm -rf "$SCRIPT_DIR/frontend"
  cp -r "$FRONTEND_DIR/build" "$SCRIPT_DIR/frontend"
fi

# ── 2. Vérification .env ──────────────────────────────────────────────────────
cd "$SCRIPT_DIR"
if [[ ! -f .env ]]; then
  echo "⚠ Fichier .env manquant — copie .env.example et remplis-le"
  cp .env.example .env
  echo "  Edite deploy/.env puis relance le script."
  exit 1
fi

# ── 3. Lancement ─────────────────────────────────────────────────────────────
echo "→ Démarrage des services Docker..."
docker compose pull caddy
docker compose build api
docker compose up -d --remove-orphans

echo "✅ Déployé ! Vérifie avec : docker compose logs -f"
