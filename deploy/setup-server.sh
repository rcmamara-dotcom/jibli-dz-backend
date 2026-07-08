#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# JIBLI DZ — Installation initiale du serveur (Ubuntu 22.04 / Debian 12)
# Usage : bash setup-server.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DEPLOY_DIR="/opt/jibli-dz"

echo "▶ Installation de Docker..."
apt-get update -qq
apt-get install -y --no-install-recommends ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
echo "✅ Docker installé : $(docker --version)"

echo "▶ Clonage des dépôts..."
mkdir -p "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

if [[ ! -d backend ]]; then
  git clone https://github.com/rcmamara-dotcom/jibli-dz-backend backend
fi
if [[ ! -d frontend ]]; then
  git clone https://github.com/rcmamara-dotcom/jibli-dz frontend
fi

echo "▶ Installation de Node.js (pour le build frontend)..."
if ! command -v node &>/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
echo "✅ Node $(node -v)"

echo "▶ Configuration du .env..."
cd "$DEPLOY_DIR/backend/deploy"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo ""
  echo "┌─────────────────────────────────────────────────────┐"
  echo "│  IMPORTANT : édite /opt/jibli-dz/backend/deploy/.env│"
  echo "│  avec tes vraies valeurs avant de continuer.        │"
  echo "│                                                      │"
  echo "│  nano /opt/jibli-dz/backend/deploy/.env             │"
  echo "│                                                      │"
  echo "│  Puis relance : bash /opt/jibli-dz/backend/deploy/deploy.sh │"
  echo "└─────────────────────────────────────────────────────┘"
  echo ""
  echo "Variables minimales à remplir :"
  echo "  DOMAIN=jiblidz.com"
  echo "  DB_PASSWORD=..."
  echo "  JWT_SECRET=$(openssl rand -hex 32)"
  echo "  SMTP_HOST=smtp.gmail.com"
  echo "  SMTP_USER=..."
  echo "  SMTP_PASS=..."
  echo "  PUBLIC_URL=https://jiblidz.com"
else
  echo "✅ .env existe déjà"
fi

echo ""
echo "✅ Serveur configuré. Prochaine étape :"
echo "   1. Édite le .env : nano /opt/jibli-dz/backend/deploy/.env"
echo "   2. Lance le déploiement : bash /opt/jibli-dz/backend/deploy/deploy.sh"
