#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# JIBLI DZ — Mise à jour (git pull + rebuild + redémarrage)
# Usage : bash update.sh           → met à jour backend + frontend
#         bash update.sh --api     → backend seulement (plus rapide)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DEPLOY_DIR="/opt/jibli-dz"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "▶ JIBLI DZ — mise à jour"

# ── Backend ──────────────────────────────────────────────────────────────────
echo "→ Pull backend..."
cd "$DEPLOY_DIR/backend"
git pull origin develop

# ── Frontend ─────────────────────────────────────────────────────────────────
if [[ "${1:-}" != "--api" ]]; then
  echo "→ Pull frontend..."
  cd "$DEPLOY_DIR/frontend"
  git pull origin develop

  echo "→ Build frontend..."
  npm ci --prefer-offline
  npx vite build

  echo "→ Copie des fichiers statiques..."
  # On vide le dossier sans le supprimer : Caddy le monte en volume et resterait
  # accroché à l'ancien dossier supprimé (site en 404 jusqu'au redémarrage).
  mkdir -p "$SCRIPT_DIR/frontend"
  find "$SCRIPT_DIR/frontend" -mindepth 1 -delete
  cp -r "$DEPLOY_DIR/frontend/build/." "$SCRIPT_DIR/frontend/"
fi

# ── Rebuild + restart ─────────────────────────────────────────────────────────
echo "→ Rebuild et redémarrage des services..."
cd "$SCRIPT_DIR"
docker compose build api
docker compose up -d --remove-orphans

echo "✅ Mise à jour terminée !"
echo "   Logs : docker compose logs -f"
