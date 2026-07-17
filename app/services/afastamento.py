"""Regras de Afastamentos (§12.3). Cobertura (§12.2) é aplicada pelo motor (FASE 4)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NaoEncontrado
from app.models.calendario import Afastamento
from app.models.catalogo import Docente, Preceptor
from app.schemas.afastamento import AfastamentoCreate
from app.services import common


def listar(db: Session) -> list[Afastamento]:
    ciclo = common.exigir_ciclo_ativo(db)
    return list(db.scalars(
        select(Afastamento).where(Afastamento.ciclo_id == ciclo.id)
        .order_by(Afastamento.data_inicio)
    ).all())


def obter(db: Session, afastamento_id: int) -> Afastamento:
    return common.obter_ou_404(db, Afastamento, afastamento_id, "Afastamento")


def _pessoa(db: Session, dados: AfastamentoCreate) -> str:
    if dados.docente_id is not None:
        d = db.get(Docente, dados.docente_id)
        if d is None:
            raise NaoEncontrado("Docente não encontrado.")
        return d.nome
    p = db.get(Preceptor, dados.preceptor_id)
    if p is None:
        raise NaoEncontrado("Preceptor não encontrado.")
    return p.nome


def criar(db: Session, dados: AfastamentoCreate) -> Afastamento:
    ciclo = common.exigir_ciclo_ativo(db)
    nome = _pessoa(db, dados)
    af = Afastamento(
        ciclo_id=ciclo.id,
        docente_id=dados.docente_id,
        preceptor_id=dados.preceptor_id,
        tipo=dados.tipo,
        motivo=dados.motivo,
        data_inicio=dados.data_inicio,
        data_retorno=dados.data_retorno,
        criado_em=datetime.now(),
    )
    db.add(af)
    common.registrar_pendencia_infra(
        db, ciclo,
        f"Afastamento de {nome} ({dados.data_inicio}–{dados.data_retorno}) — verificar cobertura.",
    )
    common.commit(db, "Não foi possível registrar o afastamento.")
    db.refresh(af)
    return af


def remover(db: Session, afastamento_id: int) -> None:
    af = obter(db, afastamento_id)
    ciclo = common.get_ciclo_ativo(db)
    db.delete(af)
    if ciclo is not None:
        common.registrar_pendencia_infra(db, ciclo, "Afastamento removido — realocar.")
    common.commit(db, "Não foi possível remover o afastamento.")
