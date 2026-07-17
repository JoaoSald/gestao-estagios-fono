"""Healthcheck — confirma que a API está no ar e que o banco responde."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(tags=["infra"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Ping simples: responde a aplicação e testa a conexão com o Postgres."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # pragma: no cover - só sinaliza indisponibilidade
        db_status = "erro"
    return {"status": "ok", "app_env": settings.APP_ENV, "db": db_status}
