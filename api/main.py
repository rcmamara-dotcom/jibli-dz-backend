import os
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from godata import init_db, database
from .routes import auth, trips, parcels, reviews
from .scheduler import start_scheduler, stop_scheduler

app = FastAPI(title="Jibli DZ API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(trips.router)
app.include_router(parcels.router)
app.include_router(reviews.router)


@app.middleware("http")
async def db_connection(request: Request, call_next):
    log.debug("→ %s %s", request.method, request.url.path)
    database.connect(reuse_if_open=True)
    try:
        response = await call_next(request)
        log.debug("← %s %s [%d]", request.method, request.url.path, response.status_code)
        return response
    except Exception as e:
        log.exception("Erreur non gérée: %s", e)
        raise
    finally:
        if not database.is_closed():
            database.close()


@app.on_event("startup")
def startup() -> None:
    log.debug("Démarrage — DB_HOST=%s DB_USER=%s DB_NAME=%s",
              os.environ.get("DB_HOST"), os.environ.get("DB_USER"), os.environ.get("DB_NAME"))
    init_db()
    log.debug("init_db() OK — tables créées")
    start_scheduler()


@app.on_event("shutdown")
def shutdown() -> None:
    stop_scheduler()


@app.get("/api/health")
def health() -> dict[str, str]:
    log.debug("GET /api/health")
    return {"status": "ok"}
