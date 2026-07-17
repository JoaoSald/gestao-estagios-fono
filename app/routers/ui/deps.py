"""Dependências e helpers compartilhados das rotas UI (FASE 5)."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import Depends

from app.core.database import get_db
from app.core.templates import templates
from app.models.ciclo import Ciclo
from app.models.enums import StatusCiclo
from app.models.operacao import FilaRemanejo
from app.services.common import get_ciclo_ativo

COOKIE_SESSAO = "sessao"


class RedirecionarLogin(Exception):
    """Sem sessão (stub de login) → o handler em main.py redireciona para /login."""


class Redirecionar(Exception):
    """Redireciona para a tela certa do estado do ciclo (welcome/bootstrap/painel)."""

    def __init__(self, destino: str) -> None:
        self.destino = destino


def exigir_sessao(request: Request) -> None:
    """Gate de acesso das PÁGINAS UI (não afeta a API JSON). Stub — trocado na FASE 6."""
    if request.cookies.get(COOKIE_SESSAO) != "ok":
        raise RedirecionarLogin()


def destino_por_estado(db: Session) -> str:
    """Tela inicial conforme o estado do ciclo (espelha o gate do protótipo)."""
    ciclo = get_ciclo_ativo(db)
    if ciclo is None:
        return "/ui/bem-vindo"
    if ciclo.status == StatusCiclo.rascunho:
        return "/ui/bootstrap"
    return "/ui/painel"


def exigir_operacao(request: Request, db: Session = Depends(get_db)) -> None:
    """Páginas de operação exigem ciclo `em_andamento`; senão manda p/ welcome/bootstrap."""
    ciclo = get_ciclo_ativo(db)
    if ciclo is None or ciclo.status != StatusCiclo.em_andamento:
        raise Redirecionar(destino_por_estado(db))


def contexto_shell(db: Session, ativo: str) -> dict:
    """Contexto comum do shell (sidebar/topbar): ciclo ativo, ano e tamanho da fila."""
    ciclo: Ciclo | None = get_ciclo_ativo(db)
    fila_count = 0
    if ciclo is not None:
        fila_count = db.scalar(
            select(func.count()).select_from(FilaRemanejo).where(FilaRemanejo.ciclo_id == ciclo.id)
        ) or 0
    return {
        "ativo": ativo,
        "ciclo": ciclo,
        "ciclo_ano": ciclo.data_inicio.year if ciclo else "",
        "fila_count": fila_count,
    }


def render(request: Request, db: Session, nome: str, ativo: str, **extra):
    """Atalho: renderiza uma página com o contexto do shell + extras."""
    ctx = contexto_shell(db, ativo)
    ctx.update(extra)
    return templates.TemplateResponse(request, nome, ctx)
