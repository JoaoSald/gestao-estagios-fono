"""Dependências e helpers das rotas UI: gate de ESTADO DO CICLO + shell das páginas.

O gate de acesso (quem é / pode escrever) mora em `app/routers/acesso.py`, porque a API
JSON usa o mesmo. Aqui fica a terceira pergunta, que só existe na tela:

  3. o ciclo permite? → `exigir_operacao` (sem ciclo em andamento → tela certa do estado)

Regra que vale para toda a superfície de leitura: **aluno e docente só existem quando o
ciclo está `em_andamento`** — ciclo em `rascunho` é escala em edição e não pode aparecer
fora da comissão; e leitor nunca é mandado para o wizard, que é tela de operação.
"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.seguranca import Sessao
from app.core.templates import templates
from app.models.ciclo import Ciclo
from app.models.enums import StatusCiclo
from app.models.operacao import FilaRemanejo
from app.routers.acesso import (  # noqa: F401 — reexport: as rotas UI importam tudo daqui
    RedirecionarLogin, SemPermissao, exigir_coordenacao, exigir_leitura_ampla,
    exigir_sessao, gravar_sessao, limpar_sessao, sessao_opcional,
)
from app.services.common import get_ciclo_ativo


class Redirecionar(Exception):
    """Redireciona para a tela certa do estado do ciclo (welcome/bootstrap/painel/aguarde)."""

    def __init__(self, destino: str) -> None:
        self.destino = destino


# ============================ Gate por estado do ciclo ============================
def destino_por_estado(db: Session, sessao: Sessao | None = None) -> str:
    """Tela inicial de quem entrou, conforme perfil + estado do ciclo.

    Leitura (aluno/docente) nunca é mandada para o bootstrap: o wizard é da comissão, e
    ciclo fora de `em_andamento` significa "escala ainda não publicada" (→ /ui/aguarde).
    """
    ciclo = get_ciclo_ativo(db)
    if sessao is not None and not sessao.pode_editar:
        em_operacao = ciclo is not None and ciclo.status == StatusCiclo.em_andamento
        return "/ui/estagios" if em_operacao else "/ui/aguarde"
    if ciclo is None:
        return "/ui/bem-vindo"
    if ciclo.status == StatusCiclo.rascunho:
        return "/ui/bootstrap"
    return "/ui/painel"


def exigir_operacao(request: Request, db: Session = Depends(get_db)) -> None:
    """Páginas de operação exigem ciclo `em_andamento`; senão manda para a tela do estado
    (coordenação → welcome/bootstrap; leitura → aguarde)."""
    sessao = exigir_sessao(request)
    ciclo = get_ciclo_ativo(db)
    if ciclo is None or ciclo.status != StatusCiclo.em_andamento:
        raise Redirecionar(destino_por_estado(db, sessao))


# ============================ Shell ============================
def contexto_shell(db: Session, ativo: str) -> dict:
    """Contexto comum do shell (sidebar/topbar): ciclo ativo, ano e tamanho da fila.

    `usuario`/`pode_editar` NÃO vêm daqui: entram em todo render pelo processador de
    contexto do Jinja (`core/templates.py`), para valerem também nas parciais HTMX.
    """
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
