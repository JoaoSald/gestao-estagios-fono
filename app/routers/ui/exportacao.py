"""Rotas de download: planilha (.xlsx) dos grupos e calendário (.ics) do aluno.

Mesmo gate das demais páginas de operação (sessão + ciclo em_andamento). Sem
distinção de perfil ainda (FASE 6): qualquer sessão baixa qualquer arquivo.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.ui.deps import exigir_operacao, exigir_sessao
from app.services import common, exportacao

router = APIRouter(prefix="/ui", tags=["ui-exportacao"],
                   dependencies=[Depends(exigir_sessao), Depends(exigir_operacao)])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _anexo(nome: str) -> str:
    """Content-Disposition com fallback ASCII + filename* (RFC 5987) p/ acentos."""
    return f"attachment; filename={exportacao.slug(nome)}; filename*=UTF-8''{quote(nome)}"


@router.get("/estagios/grupos.xlsx")
def exportar_grupos(db: Session = Depends(get_db)) -> Response:
    ciclo = common.exigir_ciclo_ativo(db)
    conteudo = exportacao.grupos_xlsx(db, ciclo)
    nome = f"grupos_{ciclo.data_inicio.year}.xlsx"
    return Response(content=conteudo, media_type=XLSX_MIME,
                    headers={"Content-Disposition": _anexo(nome)})


@router.get("/estagios/grupos.pdf")
def exportar_grupos_pdf(db: Session = Depends(get_db)) -> Response:
    ciclo = common.exigir_ciclo_ativo(db)
    conteudo = exportacao.grupos_pdf(db, ciclo)
    nome = f"grupos_{ciclo.data_inicio.year}.pdf"
    return Response(content=conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": _anexo(nome)})


@router.get("/alunos/{aluno_id:int}/calendario.ics")
def exportar_calendario_aluno(aluno_id: int, db: Session = Depends(get_db)) -> Response:
    nome, conteudo = exportacao.calendario_aluno_ics(db, aluno_id)
    return Response(content=conteudo, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": _anexo(nome)})


@router.get("/alunos/{aluno_id:int}/calendario.pdf")
def exportar_calendario_aluno_pdf(aluno_id: int, db: Session = Depends(get_db)) -> Response:
    nome, conteudo = exportacao.calendario_aluno_pdf(db, aluno_id)
    return Response(content=conteudo, media_type="application/pdf",
                    headers={"Content-Disposition": _anexo(nome)})
