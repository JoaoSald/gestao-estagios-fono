"""Regras de Indisponibilidade de local — EXCLUSIVA da operação (nunca no bootstrap).

Modelada como PERÍODO (reverte sozinha ao fim). Cadastrar em andamento dispara remanejo
(só as sessões futuras daquele local no período voltam à fila).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflito
from app.models.enums import StatusCiclo
from app.models.local import IndisponibilidadeLocal
from app.schemas.local import IndisponibilidadeCreate
from app.services import common
from app.services.local import obter as obter_local


def listar(db: Session, local_id: int) -> list[IndisponibilidadeLocal]:
    obter_local(db, local_id)  # 404 se local não existe
    return list(db.scalars(
        select(IndisponibilidadeLocal)
        .where(IndisponibilidadeLocal.local_id == local_id)
        .order_by(IndisponibilidadeLocal.data_inicio)
    ).all())


def criar(db: Session, local_id: int, dados: IndisponibilidadeCreate) -> IndisponibilidadeLocal:
    local = obter_local(db, local_id)
    ciclo = common.exigir_ciclo_ativo(db)
    if ciclo.status != StatusCiclo.em_andamento:
        raise Conflito(
            "Indisponibilidade de local só na operação (ciclo em andamento), não no bootstrap."
        )
    ind = IndisponibilidadeLocal(
        local_id=local_id,
        motivo=dados.motivo,
        data_inicio=dados.data_inicio,
        data_fim=dados.data_fim,
    )
    db.add(ind)
    common.registrar_pendencia_infra(
        db, ciclo,
        f"Local {local.campo} indisponível ({dados.data_inicio}–{dados.data_fim}) — realocar.",
    )
    common.commit(db, "Não foi possível registrar a indisponibilidade.")
    db.refresh(ind)
    return ind


def remover(db: Session, indisponibilidade_id: int) -> None:
    ind = common.obter_ou_404(db, IndisponibilidadeLocal, indisponibilidade_id, "Indisponibilidade")
    ciclo = common.get_ciclo_ativo(db)
    db.delete(ind)
    if ciclo is not None:
        common.registrar_pendencia_infra(db, ciclo, "Indisponibilidade removida — realocar.")
    common.commit(db, "Não foi possível remover a indisponibilidade.")
