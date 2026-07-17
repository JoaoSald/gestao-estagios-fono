"""Instância única de Jinja2Templates, compartilhada por main.py e pelos routers UI (FASE 5)."""
from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app.core.config import BASE_DIR

TEMPLATES_DIR = BASE_DIR / "app" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
