# jibli-dz-backend

REST API for **Jibli DZ** — FastAPI + Peewee + PostgreSQL.

## Structure

```
api/
├── main.py          # FastAPI app, CORS, startup
├── auth.py          # JWT helpers, password hashing, dependencies
├── schemas.py       # Pydantic request/response models
└── routes/
    ├── auth.py      # POST /api/auth/register  POST /api/auth/login
    ├── trips.py     # GET/POST/DELETE /api/trips
    └── parcels.py   # GET/POST/DELETE /api/parcels
```

## Quick start

```bash
cp .env.example .env   # fill in your values
uv sync
uv run fastapi dev api/main.py
```

## Environment variables

| Variable            | Default                    | Description                        |
|---------------------|----------------------------|------------------------------------|
| `JWT_SECRET`        | —                          | Secret key for JWT signing         |
| `JWT_ALGORITHM`     | `HS256`                    | JWT algorithm                      |
| `JWT_EXPIRE_MINUTES`| `10080` (7 days)           | Token lifetime in minutes          |
| `CORS_ORIGINS`      | `http://localhost:5173`    | Comma-separated allowed origins    |
| `DB_NAME`           | —                          | PostgreSQL database                |
| `DB_USER`           | —                          | PostgreSQL user                    |
| `DB_PASSWORD`       | —                          | PostgreSQL password                |
| `DB_HOST`           | `localhost`                | PostgreSQL host                    |
| `DB_PORT`           | `5432`                     | PostgreSQL port                    |
