"""Regras de Eventos (§11). Só eventos `bloqueia_estagio=true` empurram sessões (motor)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflito
from app.models.calendario import Evento
from app.schemas.evento import EventoCreate, EventoUpdate
from app.services import common


def listar(db: Session) -> list[Evento]:
    ciclo = common.exigir_ciclo_ativo(db)
    return list(db.scalars(
        select(Evento).where(Evento.ciclo_id == ciclo.id).order_by(Evento.data_inicio)
    ).all())


def obter(db: Session, evento_id: int) -> Evento:
    return common.obter_ou_404(db, Evento, evento_id, "Evento")


def _validar_unico(db: Session, ciclo_id: int, nome: str, data_inicio, ignora_id: int | None = None) -> None:
    q = select(Evento).where(
        Evento.ciclo_id == ciclo_id, Evento.nome == nome, Evento.data_inicio == data_inicio
    )
    if ignora_id is not None:
        q = q.where(Evento.id != ignora_id)
    if db.scalars(q).first() is not None:
        raise Conflito(f"Já existe o evento '{nome}' em {data_inicio}.")


def criar(db: Session, dados: EventoCreate) -> Evento:
    ciclo = common.exigir_ciclo_ativo(db)
    _validar_unico(db, ciclo.id, dados.nome, dados.data_inicio)
    ev = Evento(
        ciclo_id=ciclo.id,
        nome=dados.nome,
        tipo=dados.tipo,
        origem=dados.origem,
        data_inicio=dados.data_inicio,
        data_fim=dados.data_fim,
        bloqueia_estagio=dados.bloqueia_estagio,
    )
    db.add(ev)
    if dados.bloqueia_estagio:
        common.registrar_pendencia_infra(db, ciclo, f"Evento '{dados.nome}' — realocar sessões no período.")
    common.commit(db, "Não foi possível criar o evento.")
    db.refresh(ev)
    return ev


def atualizar(db: Session, evento_id: int, dados: EventoUpdate) -> Evento:
    ev = obter(db, evento_id)
    campos = dados.model_dump(exclude_unset=True)
    nome = campos.get("nome", ev.nome)
    data_inicio = campos.get("data_inicio", ev.data_inicio)
    if "nome" in campos or "data_inicio" in campos:
        _validar_unico(db, ev.ciclo_id, nome, data_inicio, ignora_id=evento_id)
    for campo, valor in campos.items():
        setattr(ev, campo, valor)
    if ev.data_fim < ev.data_inicio:
        raise Conflito("data_fim deve ser >= data_inicio.")
    common.registrar_pendencia_infra(db, ev.ciclo, f"Evento '{ev.nome}' alterado — realocar.")
    common.commit(db, "Não foi possível atualizar o evento.")
    db.refresh(ev)
    return ev


def remover(db: Session, evento_id: int) -> None:
    ev = obter(db, evento_id)
    ciclo = ev.ciclo
    db.delete(ev)
    common.registrar_pendencia_infra(db, ciclo, "Evento removido — realocar.")
    common.commit(db, "Não foi possível remover o evento.")
