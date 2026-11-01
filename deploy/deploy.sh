#!/usr/bin/env bash
# Usage: ./deploy.sh [--no-frontend]
# Lance depuis le dossier deploy/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Sur le VPS : /opt/jibli-dz/backend → /opt/jibli-dz/frontend
# En local (dev) : ../jibli-dz-backend/../jibli-dz
if [[ -d "$(dirname "$BACKEND_DIR")/frontend" ]]; then
  FRONTEND_DIR="$(dirname "$BACKEND_DIR")/frontend"
else
  FRONTEND_DIR="$(dirname "$BACKEND_DIR")/jibli-dz"
fi

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
  # On vide le dossier sans le supprimer : Caddy le monte en volume et resterait
  # accroché à l'ancien dossier supprimé (site en 404 jusqu'au redémarrage).
  # Vérifier le build AVANT de vider le dossier servi : sinon le site tombe en 404
  if [[ ! -f "$FRONTEND_DIR/build/index.html" ]]; then
    echo "❌ Build introuvable dans $FRONTEND_DIR/build — site en ligne laissé tel quel"
    exit 1
  fi
  mkdir -p "$SCRIPT_DIR/frontend"
  find "$SCRIPT_DIR/frontend" -mindepth 1 -delete
  cp -r "$FRONTEND_DIR/build/." "$SCRIPT_DIR/frontend/"
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
