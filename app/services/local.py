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


def sugerir_numero_encontros(carga_horaria: int, horas_sessao: float) -> int:
    """Sugestão de N = ceil(carga_da_área / horas_por_sessão), mínimo 1 (MOTOR §4).

    É só o VALOR PADRÃO quando a comissão não informa o nº de encontros. O número real
    manda-o o espelho: se `numero_encontros` vier no formulário, ele é usado como está
    (o ceil pode arredondar pra cima e discordar do espelho — ex.: ORL-TAN 10h/3h = 3,33
    → ceil 4, mas o espelho usa 3).
    """
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


def _validar_preceptor(db: Session, tipo: str | None, preceptor_id: int | None) -> None:
    """Preceptor polimórfico: `tipo` diz em qual catálogo `preceptor_id` aponta."""
    if (tipo is None) != (preceptor_id is None):
        raise DomainError("Informe o preceptor e o seu tipo, ou deixe ambos em branco.")
    if tipo is None:
        return
    if tipo == "externo":
        if db.get(Preceptor, preceptor_id) is None:
            raise NaoEncontrado("Preceptor (externo) não encontrado.")
    elif tipo == "docente":
        if db.get(Docente, preceptor_id) is None:
            raise NaoEncontrado("Docente (como preceptor) não encontrado.")
    else:
        raise DomainError("Tipo de preceptor inválido.")


def criar(db: Session, dados: LocalCreate) -> Local:
    ciclo = common.exigir_ciclo_ativo(db)
    _validar_area_leaf(db, dados.area_id)
    _validar_docente(db, dados.docente_id)
    _validar_preceptor(db, dados.preceptor_tipo, dados.preceptor_id)
    local = Local(
        ciclo_id=ciclo.id,
        area_id=dados.area_id,
        docente_id=dados.docente_id,
        preceptor_tipo=dados.preceptor_tipo,
        preceptor_id=dados.preceptor_id,
        unidade=dados.unidade,
        campo=dados.campo,
        dia_semana=dados.dia_semana,
        turno=dados.turno,
        hora_inicio=dados.hora_inicio,
        hora_fim=dados.hora_fim,
        capacidade=dados.capacidade,
        carga_horaria=dados.carga_horaria,
        horas_sessao=dados.horas_sessao,
        numero_encontros=(
            dados.numero_encontros
            if dados.numero_encontros is not None
            else sugerir_numero_encontros(dados.carga_horaria, dados.horas_sessao)
        ),
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

    # Valida horário. Re-deriva numero_encontros SÓ quando carga/horas mudam E a comissão
    # não informou o nº de encontros explicitamente (o espelho manda; ceil é só sugestão).
    if local.hora_fim <= local.hora_inicio:
        raise DomainError("hora_fim deve ser maior que hora_inicio.")
    if {"preceptor_tipo", "preceptor_id"} & campos.keys():
        _validar_preceptor(db, local.preceptor_tipo, local.preceptor_id)
    if ("numero_encontros" not in campos
            and {"carga_horaria", "horas_sessao"} & campos.keys() and local.horas_sessao):
        local.numero_encontros = sugerir_numero_encontros(local.carga_horaria, local.horas_sessao)

    # Docente/preceptor mexem na COBERTURA do slot (§7.1) — mesmo gatilho de infra que
    # 'Config. de campo' dispara, já que agora dão para ser editados por aqui também.
    # Qualquer outra edição de cadastro é só log (no-op fora de `em_andamento`).
    if {"docente_id", "preceptor_tipo", "preceptor_id"} & campos.keys():
        common.registrar_pendencia_infra(
            db, local.ciclo, f"Cobertura do local {local.campo} alterada.")
    else:
        common.registrar_atividade(db, local.ciclo, f"Local {local.campo} alterado.")
    common.commit(db, "Não foi possível atualizar o local.")
    db.refresh(local)
    return local


def configurar_campo(db: Session, local_id: int, dados: LocalConfigCampo) -> Local:
    """Atribui docente (obrigatório antes de gerar a escala, não no banco) e preceptor
    (polimórfico) ao slot. Valida a existência das pessoas referenciadas."""
    local = obter(db, local_id)
    _validar_docente(db, dados.docente_id)
    _validar_preceptor(db, dados.preceptor_tipo, dados.preceptor_id)
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
