#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# JIBLI DZ — Durcissement du VPS (Ubuntu). À lancer une fois : sudo bash harden-server.sh
#  - pare-feu : seuls SSH, HTTP et HTTPS sont ouverts
#  - fail2ban : bannit les IP qui ratent la connexion SSH en boucle
#  - mises à jour de sécurité automatiques
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

apt-get update -q
apt-get install -y -q ufw fail2ban unattended-upgrades

# SSH en premier pour ne pas se couper l'accès
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

systemctl enable --now fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "✅ Pare-feu :"; ufw status
echo "✅ fail2ban : $(systemctl is-active fail2ban)"
