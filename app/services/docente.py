"""Regras de Docentes — catálogo permanente, soft-delete via `ativo`."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflito
from app.models.catalogo import Docente
from app.schemas.docente import DocenteCreate, DocenteUpdate
from app.services import common


def listar(db: Session, incluir_inativos: bool = True) -> list[Docente]:
    q = select(Docente).order_by(Docente.nome)
    if not incluir_inativos:
        q = q.where(Docente.ativo.is_(True))
    return list(db.scalars(q).all())


def obter(db: Session, docente_id: int) -> Docente:
    return common.obter_ou_404(db, Docente, docente_id, "Docente")


def _validar_nome_unico(db: Session, nome: str, ignora_id: int | None = None) -> None:
    q = select(Docente).where(func.lower(Docente.nome) == nome.lower())
    if ignora_id is not None:
        q = q.where(Docente.id != ignora_id)
    if db.scalars(q).first() is not None:
        raise Conflito(f"Já existe um docente com o nome '{nome}'.")


def _gatilho_desligamento(db: Session, docente: Docente) -> None:
    """Desligar docente em operação → realocar sessões futuras (§12)."""
    ciclo = common.get_ciclo_ativo(db)
    if ciclo is not None:
        common.registrar_pendencia_infra(
            db, ciclo, f"Docente {docente.nome} desligado — realocar sessões futuras."
        )


def criar(db: Session, dados: DocenteCreate) -> Docente:
    _validar_nome_unico(db, dados.nome)
    docente = Docente(nome=dados.nome, email=dados.email, ativo=dados.ativo)
    db.add(docente)
    common.commit(db, f"Não foi possível criar o docente '{dados.nome}'.")
    db.refresh(docente)
    return docente


def atualizar(db: Session, docente_id: int, dados: DocenteUpdate) -> Docente:
    docente = obter(db, docente_id)
    campos = dados.model_dump(exclude_unset=True)
    if "nome" in campos:
        _validar_nome_unico(db, campos["nome"], ignora_id=docente_id)

    desligou = campos.get("ativo") is False and docente.ativo
    for campo, valor in campos.items():
        setattr(docente, campo, valor)
    if desligou:
        _gatilho_desligamento(db, docente)
    common.commit(db, "Não foi possível atualizar o docente.")
    db.refresh(docente)
    return docente


def desativar(db: Session, docente_id: int) -> Docente:
    """Soft-delete: nunca apaga (preserva histórico); dispara remanejo em operação."""
    docente = obter(db, docente_id)
    if docente.ativo:
        docente.ativo = False
        _gatilho_desligamento(db, docente)
    common.commit(db, "Não foi possível desativar o docente.")
    db.refresh(docente)
    return docente
