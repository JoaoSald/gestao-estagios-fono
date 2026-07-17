"""Regras de Preceptores — catálogo permanente externo, e-mail obrigatório (AR-1)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflito
from app.models.catalogo import Preceptor
from app.schemas.preceptor import PreceptorCreate, PreceptorUpdate
from app.services import common


def listar(db: Session, incluir_inativos: bool = True) -> list[Preceptor]:
    q = select(Preceptor).order_by(Preceptor.nome)
    if not incluir_inativos:
        q = q.where(Preceptor.ativo.is_(True))
    return list(db.scalars(q).all())


def obter(db: Session, preceptor_id: int) -> Preceptor:
    return common.obter_ou_404(db, Preceptor, preceptor_id, "Preceptor")


def _validar_email_unico(db: Session, email: str, ignora_id: int | None = None) -> None:
    q = select(Preceptor).where(func.lower(Preceptor.email) == email.lower())
    if ignora_id is not None:
        q = q.where(Preceptor.id != ignora_id)
    if db.scalars(q).first() is not None:
        raise Conflito(f"Já existe um preceptor com o e-mail '{email}'.")


def _gatilho_desligamento(db: Session, preceptor: Preceptor) -> None:
    ciclo = common.get_ciclo_ativo(db)
    if ciclo is not None:
        common.registrar_pendencia_infra(
            db, ciclo, f"Preceptor {preceptor.nome} desligado — realocar sessões futuras."
        )


def criar(db: Session, dados: PreceptorCreate) -> Preceptor:
    _validar_email_unico(db, dados.email)
    preceptor = Preceptor(nome=dados.nome, email=dados.email, ativo=dados.ativo)
    db.add(preceptor)
    common.commit(db, f"Não foi possível criar o preceptor '{dados.nome}'.")
    db.refresh(preceptor)
    return preceptor


def atualizar(db: Session, preceptor_id: int, dados: PreceptorUpdate) -> Preceptor:
    preceptor = obter(db, preceptor_id)
    campos = dados.model_dump(exclude_unset=True)
    if "email" in campos and campos["email"] is not None:
        _validar_email_unico(db, campos["email"], ignora_id=preceptor_id)

    desligou = campos.get("ativo") is False and preceptor.ativo
    for campo, valor in campos.items():
        setattr(preceptor, campo, valor)
    if desligou:
        _gatilho_desligamento(db, preceptor)
    common.commit(db, "Não foi possível atualizar o preceptor.")
    db.refresh(preceptor)
    return preceptor


def desativar(db: Session, preceptor_id: int) -> Preceptor:
    preceptor = obter(db, preceptor_id)
    if preceptor.ativo:
        preceptor.ativo = False
        _gatilho_desligamento(db, preceptor)
    common.commit(db, "Não foi possível desativar o preceptor.")
    db.refresh(preceptor)
    return preceptor
