#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# JIBLI DZ — Sauvegarde de la base PostgreSQL (dump compressé, 14 jours gardés)
# Manuel : sudo bash backup.sh
# Chaque nuit à 3 h : sudo crontab -e  →  0 3 * * * /opt/jibli-dz/backend/deploy/backup.sh
# Restauration : gunzip -c FICHIER.sql.gz | sudo docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/opt/jibli-dz/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
file="$BACKUP_DIR/jibli-$(date +%F-%H%M).sql.gz"
trap 'rm -f "$file"' ERR   # pas de sauvegarde à moitié écrite

cd "$SCRIPT_DIR"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$file"
chmod 600 "$file"
find "$BACKUP_DIR" -name 'jibli-*.sql.gz' -mtime +"$KEEP_DAYS" -delete

echo "✅ Sauvegarde : $file ($(du -h "$file" | cut -f1))"
