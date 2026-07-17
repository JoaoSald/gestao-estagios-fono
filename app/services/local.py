"""Regras de Locais/slot (§7 SLOT-DIA, §12, MOTOR §4)."""
from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NaoEncontrado
from app.models.catalogo import Area, Docente, Preceptor
from app.models.local import Local
from app.schemas.local import LocalConfigCampo, LocalCreate, LocalUpdate
from app.services import common


def _numero_encontros(carga_horaria: int, horas_sessao: float) -> int:
    """N = ceil(carga_da_área / horas_por_sessão), mínimo 1 (MOTOR §4)."""
    return max(1, math.ceil(carga_horaria / horas_sessao))


def _validar_area_leaf(db: Session, area_id: int) -> Area:
    area = db.get(Area, area_id)
    if area is None:
        raise NaoEncontrado("Área não encontrada.")
    if area.composta:
        raise DomainError(
            f"A área '{area.nome}' é composta (container) e não pode ter locais. "
            "Use uma sub-área."
        )
    return area


def listar(db: Session, incluir_inativos: bool = True) -> list[Local]:
    ciclo = common.exigir_ciclo_ativo(db)
    q = select(Local).where(Local.ciclo_id == ciclo.id).order_by(Local.campo)
    if not incluir_inativos:
        q = q.where(Local.ativo.is_(True))
    return list(db.scalars(q).all())


def obter(db: Session, local_id: int) -> Local:
    return common.obter_ou_404(db, Local, local_id, "Local")


def _validar_docente(db: Session, docente_id: int | None) -> None:
    if docente_id is not None and db.get(Docente, docente_id) is None:
        raise NaoEncontrado("Docente não encontrado.")


def criar(db: Session, dados: LocalCreate) -> Local:
    ciclo = common.exigir_ciclo_ativo(db)
    _validar_area_leaf(db, dados.area_id)
    _validar_docente(db, dados.docente_id)
    local = Local(
        ciclo_id=ciclo.id,
        area_id=dados.area_id,
        docente_id=dados.docente_id,
        unidade=dados.unidade,
        campo=dados.campo,
        dia_semana=dados.dia_semana,
        turno=dados.turno,
        hora_inicio=dados.hora_inicio,
        hora_fim=dados.hora_fim,
        capacidade=dados.capacidade,
        carga_horaria=dados.carga_horaria,
        horas_sessao=dados.horas_sessao,
        numero_encontros=_numero_encontros(dados.carga_horaria, dados.horas_sessao),
        passagem_grupo=dados.passagem_grupo,
        ativo=True,
    )
    db.add(local)
    common.commit(db, "Não foi possível criar o local.")
    db.refresh(local)
    return local


def atualizar(db: Session, local_id: int, dados: LocalUpdate) -> Local:
    local = obter(db, local_id)
    campos = dados.model_dump(exclude_unset=True)
    if "area_id" in campos:
        _validar_area_leaf(db, campos["area_id"])
    if "docente_id" in campos:
        _validar_docente(db, campos["docente_id"])

    for campo, valor in campos.items():
        setattr(local, campo, valor)

    # Valida horário e re-deriva numero_encontros quando carga/horas mudam.
    if local.hora_fim <= local.hora_inicio:
        raise DomainError("hora_fim deve ser maior que hora_inicio.")
    if {"carga_horaria", "horas_sessao"} & campos.keys() and local.horas_sessao:
        local.numero_encontros = _numero_encontros(local.carga_horaria, local.horas_sessao)

    # Edição comum de cadastro → só registra no log (não é gatilho de infra).
    common.registrar_atividade(db, local.ciclo, f"Local {local.campo} alterado.")
    common.commit(db, "Não foi possível atualizar o local.")
    db.refresh(local)
    return local


def configurar_campo(db: Session, local_id: int, dados: LocalConfigCampo) -> Local:
    """Atribui docente (obrigatório antes de gerar a escala, não no banco) e preceptor
    (polimórfico) ao slot. Valida a existência das pessoas referenciadas."""
    local = obter(db, local_id)

    if dados.docente_id is not None and db.get(Docente, dados.docente_id) is None:
        raise NaoEncontrado("Docente não encontrado.")

    if dados.preceptor_tipo == "externo":
        if db.get(Preceptor, dados.preceptor_id) is None:
            raise NaoEncontrado("Preceptor (externo) não encontrado.")
    elif dados.preceptor_tipo == "docente":
        if db.get(Docente, dados.preceptor_id) is None:
            raise NaoEncontrado("Docente (como preceptor) não encontrado.")

    local.docente_id = dados.docente_id
    local.preceptor_tipo = dados.preceptor_tipo
    local.preceptor_id = dados.preceptor_id
    # Muda docente/preceptor → afeta cobertura → pendência de infra (§7.1).
    common.registrar_pendencia_infra(db, local.ciclo, f"Config. de campo do local {local.campo} alterada.")
    common.commit(db, "Não foi possível configurar o campo do local.")
    db.refresh(local)
    return local


def desativar(db: Session, local_id: int) -> Local:
    """Soft-delete: desativar em operação dispara remanejo (sessões futuras à fila)."""
    local = obter(db, local_id)
    if local.ativo:
        local.ativo = False
        common.registrar_pendencia_infra(
            db, local.ciclo, f"Local {local.campo} desativado — realocar estágios."
        )
    common.commit(db, "Não foi possível desativar o local.")
    db.refresh(local)
    return local
