"""Ponto de entrada da API (FastAPI).

FASE 2 — esqueleto: app, CORS, estáticos, Jinja2, healthcheck e a home.
Rodar em dev:  uvicorn app.main:app --reload
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import BASE_DIR, settings
from app.core.errors import DomainError
from app.routers import (
    afastamentos, alunos, areas, ciclos, docentes, escala, eventos,
    health, locais, preceptores,
)
from app.routers.ui import bootstrap as ui_bootstrap
from app.routers.ui import cadastros as ui_cadastros
from app.routers.ui import escala as ui_escala
from app.routers.ui import exportacao as ui_exportacao
from app.routers.ui import paginas as ui_paginas
from app.routers.ui.deps import Redirecionar, RedirecionarLogin

app = FastAPI(
    title="Gestão de Estágios — Fonoaudiologia UFCSPA",
    version="0.2.0",
    description="API do planejador de escala de estágios (server-rendered, Jinja2 + HTMX).",
)

# CORS: liberado em dev. Em produção, restringir aos domínios da faculdade.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "dev" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estáticos (CSS/JS/img reaproveitados do protótipo).
STATIC_DIR = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.exception_handler(DomainError)
def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Regra de negócio violada → JSON pt-BR com o status certo (400/404/409)."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.mensagem})


@app.exception_handler(RedirecionarLogin)
def _redirecionar_login(request: Request, exc: RedirecionarLogin) -> RedirectResponse:
    """Página UI sem sessão (stub de login) → redireciona para /login."""
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(Redirecionar)
def _redirecionar(request: Request, exc: Redirecionar) -> RedirectResponse:
    """Gate por estado do ciclo → welcome/bootstrap/painel."""
    return RedirectResponse(exc.destino, status_code=303)


# Routers
app.include_router(health.router)
app.include_router(areas.router)
app.include_router(docentes.router)
app.include_router(preceptores.router)
app.include_router(ciclos.router)
app.include_router(locais.router)
app.include_router(alunos.router)
app.include_router(afastamentos.router)
app.include_router(eventos.router)
app.include_router(escala.router)

# FASE 5 — camada de apresentação (páginas + parciais HTMX).
app.include_router(ui_paginas.auth_router)
app.include_router(ui_bootstrap.router)
app.include_router(ui_paginas.router)
app.include_router(ui_cadastros.router)
app.include_router(ui_escala.router)
app.include_router(ui_exportacao.router)
