"""Regras de Áreas — catálogo permanente, com composta/sub-áreas (§3)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import Conflito, DomainError, NaoEncontrado
from app.models.catalogo import Area
from app.models.local import Local
from app.models.aluno import Matricula
from app.schemas.area import AreaCreate, AreaUpdate
from app.services import common


def listar(db: Session) -> list[Area]:
    return list(db.scalars(select(Area).order_by(Area.nome)).all())


def obter(db: Session, area_id: int) -> Area:
    return common.obter_ou_404(db, Area, area_id, "Área")


def _validar_nome_unico(db: Session, nome: str, ignora_id: int | None = None) -> None:
    q = select(Area).where(func.lower(Area.nome) == nome.lower())
    if ignora_id is not None:
        q = q.where(Area.id != ignora_id)
    if db.scalars(q).first() is not None:
        raise Conflito(f"Já existe uma área com o nome '{nome}'.")


def _resolver_mae(db: Session, area_mae_id: int | None) -> Area | None:
    if area_mae_id is None:
        return None
    mae = db.get(Area, area_mae_id)
    if mae is None:
        raise NaoEncontrado("Área-mãe não encontrada.")
    return mae


def criar(db: Session, dados: AreaCreate) -> Area:
    _validar_nome_unico(db, dados.nome)
    mae = _resolver_mae(db, dados.area_mae_id)

    composta = dados.composta
    pre_requisito = dados.pre_requisito
    fase = dados.fase
    cor = dados.cor

    if mae is not None:
        # Sub-área (leaf): não pode ser container e é sempre não pré-requisito;
        # herda fase/cor da mãe quando não informadas (espelha o protótipo).
        if composta:
            raise DomainError("Uma sub-área não pode ser composta.")
        pre_requisito = False
        fase = fase or mae.fase
        cor = cor or mae.cor

    if dados.pre_requisito and not mae:
        _garantir_unico_prerequisito(db)

    area = Area(
        nome=dados.nome,
        carga_exigida=dados.carga_exigida,
        fase=fase,
        cor=cor,
        pre_requisito=pre_requisito,
        composta=composta,
        area_mae_id=dados.area_mae_id,
    )
    db.add(area)
    common.commit(db, f"Não foi possível criar a área '{dados.nome}'.")
    db.refresh(area)
    return area


def _garantir_unico_prerequisito(db: Session, ignora_id: int | None = None) -> None:
    q = select(Area).where(Area.pre_requisito.is_(True))
    if ignora_id is not None:
        q = q.where(Area.id != ignora_id)
    existente = db.scalars(q).first()
    if existente is not None:
        raise Conflito(
            f"Já existe uma área pré-requisito ('{existente.nome}'). "
            "Só pode haver uma."
        )


def atualizar(db: Session, area_id: int, dados: AreaUpdate) -> Area:
    area = obter(db, area_id)
    campos = dados.model_dump(exclude_unset=True)

    if "nome" in campos:
        _validar_nome_unico(db, campos["nome"], ignora_id=area_id)
    if campos.get("area_mae_id") is not None:
        _resolver_mae(db, campos["area_mae_id"])
        if campos.get("composta", area.composta):
            raise DomainError("Uma sub-área não pode ser composta.")
    if campos.get("pre_requisito"):
        _garantir_unico_prerequisito(db, ignora_id=area_id)

    for campo, valor in campos.items():
        setattr(area, campo, valor)
    common.commit(db, "Não foi possível atualizar a área.")
    db.refresh(area)
    return area


def remover(db: Session, area_id: int) -> None:
    area = obter(db, area_id)
    # Áreas não têm soft-delete; recusa apagar se há vínculos (preserva histórico).
    if db.scalars(select(Local).where(Local.area_id == area_id)).first() is not None:
        raise Conflito("Área com locais cadastrados não pode ser removida.")
    if db.scalars(select(Matricula).where(Matricula.area_id == area_id)).first() is not None:
        raise Conflito("Área com matrículas não pode ser removida.")
    if db.scalars(select(Area).where(Area.area_mae_id == area_id)).first() is not None:
        raise Conflito("Área-mãe com sub-áreas não pode ser removida.")
    db.delete(area)
    common.commit(db)
