# Déploiement JIBLI DZ

## Prérequis

- Un VPS sous Ubuntu 22.04 ou Debian 12 (1 vCPU, 1 GB RAM minimum)
- Un nom de domaine pointant vers l'IP du VPS (DNS A record)
- Accès root ou sudo

## 1. Installation initiale (une seule fois)

```bash
# Se connecter au VPS
ssh root@<IP_DU_VPS>

# Télécharger et lancer le script d'installation
curl -fsSL https://raw.githubusercontent.com/rcmamara-dotcom/jibli-dz-backend/develop/deploy/setup-server.sh | bash
```

Ce script installe Docker, clone les deux repos dans `/opt/jibli-dz/` et crée le fichier `.env`.

## 2. Configurer le .env

```bash
nano /opt/jibli-dz/backend/deploy/.env
```

Variables obligatoires :

```env
DOMAIN=jiblidz.com
PUBLIC_URL=https://jiblidz.com

DB_NAME=postgres
DB_USER=postgres.VOTRE_REF
DB_PASSWORD=VOTRE_MOT_DE_PASSE
DB_HOST=aws-1-eu-central-1.pooler.supabase.com
DB_PORT=5432
DB_SSL=true

JWT_SECRET=<généré par openssl rand -hex 32>

SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=votre@gmail.com
SMTP_PASS=xxxx_xxxx_xxxx_xxxx
SMTP_FROM=JIBLI DZ <noreply@jiblidz.com>
```

## 3. Premier déploiement

```bash
cd /opt/jibli-dz/backend/deploy
bash deploy.sh
```

Caddy obtient le certificat HTTPS automatiquement. Vérifie avec :

```bash
docker compose logs -f
```

## 4. Mises à jour

Pour mettre à jour backend + frontend :
```bash
cd /opt/jibli-dz/backend/deploy
bash update.sh
```

Pour mettre à jour uniquement le backend (plus rapide) :
```bash
bash update.sh --api
```

## Commandes utiles

```bash
# Voir les logs en temps réel
docker compose logs -f

# Redémarrer un service
docker compose restart api

# Voir l'état des services
docker compose ps

# Accéder au shell de l'API
docker compose exec api bash
```

## Structure sur le VPS

```
/opt/jibli-dz/
├── backend/          ← repo jibli-dz-backend
│   └── deploy/
│       ├── .env      ← variables de production (ne pas committer)
│       ├── docker-compose.yml
│       ├── Caddyfile
│       ├── frontend/ ← build Vite copié ici par deploy.sh
│       ├── deploy.sh
│       └── update.sh
└── frontend/         ← repo jibli-dz (source)
```
