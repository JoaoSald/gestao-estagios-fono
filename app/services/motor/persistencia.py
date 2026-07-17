"""Persistência do molde preenchido (grade-primeiro).

Grava o resultado do motor nas tabelas de saída:
- `grupos`  = TODAS as caixas do molde (inclusive vazias), com o período da onda;
- `grupo_alunos` = ocupantes (com `fixado` para os pins);
- `alocacoes` + `sessoes` = a escala concreta de cada ocupante (exatamente N sessões, as
  datas reais da caixa; ocupantes de uma caixa compartilham as mesmas datas — fonte única).

Os PINS (§5 — rascunho manual) são capturados como tuplas (aluno, local, onda) ANTES de qualquer
wipe (ver `capturar_pins`), re-aplicados pelo orquestrador e re-persistidos como `fixado`
— assim o ajuste manual e a montagem sobrevivem à regeração.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno, Matricula
from app.models.ciclo import Ciclo
from app.models.enums import StatusAlocacao, StatusGrupo, StatusSessao
from app.models.escala import Alocacao, Grupo, GrupoAluno, Sessao
from app.services.motor.molde import Caixa


def _onda_do_aluno_no_local(db: Session, ciclo_id: int, aluno_id: int, local_id: int) -> int:
    row = db.execute(
        select(Grupo.onda)
        .join(GrupoAluno, GrupoAluno.grupo_id == Grupo.id)
        .where(
            Grupo.ciclo_id == ciclo_id, Grupo.local_id == local_id,
            GrupoAluno.aluno_id == aluno_id,
        )
    ).first()
    return row[0] if row else 1


def capturar_pins(db: Session, ciclo: Ciclo) -> list[tuple[int, int, int]]:
    """Coleta os assentos manuais a preservar: (aluno_id, local_id, onda). Dedup por (aluno, local).

    Fontes: `grupo_alunos.fixado` (montagem e ajuste manual) e `alocacoes.travada`
    (alocação manual). Chamar ANTES de apagar grupos/alocações.
    """
    pins: list[tuple[int, int, int]] = []
    visto: set[tuple[int, int]] = set()

    fixados = db.execute(
        select(GrupoAluno.aluno_id, Grupo.local_id, Grupo.onda)
        .join(Grupo, GrupoAluno.grupo_id == Grupo.id)
        .where(Grupo.ciclo_id == ciclo.id, GrupoAluno.fixado.is_(True))
    ).all()
    for aluno_id, local_id, onda in fixados:
        chave = (aluno_id, local_id)
        if chave in visto:
            continue
        visto.add(chave)
        pins.append((aluno_id, local_id, onda))

    travadas = db.execute(
        select(Alocacao.aluno_id, Alocacao.local_id)
        .join(Aluno, Alocacao.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id, Alocacao.travada.is_(True),
               Alocacao.status == StatusAlocacao.ativa)
    ).all()
    for aluno_id, local_id in travadas:
        chave = (aluno_id, local_id)
        if chave in visto:
            continue
        visto.add(chave)
        pins.append((aluno_id, local_id, _onda_do_aluno_no_local(db, ciclo.id, aluno_id, local_id)))

    return pins


def _apagar_grupos(db: Session, ciclo: Ciclo) -> None:
    for g in db.scalars(select(Grupo).where(Grupo.ciclo_id == ciclo.id)).all():
        db.delete(g)  # cascade grupo_alunos
    db.flush()


def _apagar_alocacoes(db: Session, ciclo: Ciclo) -> None:
    alocs = db.scalars(
        select(Alocacao).join(Aluno, Alocacao.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id)
    ).all()
    for a in alocs:
        db.delete(a)  # cascade sessoes
    db.flush()


def _gravar_grupos(db: Session, ciclo: Ciclo, caixas: list[Caixa], hoje: date) -> list[Grupo]:
    grupos: list[Grupo] = []
    for caixa in caixas:
        status = (
            StatusGrupo.em_andamento if caixa.data_inicio <= hoje else StatusGrupo.previsto
        )
        g = Grupo(
            ciclo_id=ciclo.id, local_id=caixa.local.id, area_id=caixa.area_id,
            onda=caixa.onda, status=status,
            data_inicio=caixa.data_inicio, data_fim=caixa.data_fim,
        )
        db.add(g)
        db.flush()
        for aluno_id in caixa.ocupantes:
            db.add(GrupoAluno(grupo_id=g.id, aluno_id=aluno_id, fixado=aluno_id in caixa.fixos))
        grupos.append(g)
    db.flush()
    return grupos


def materializar_molde_vazio(db: Session, ciclo: Ciclo, ctx) -> list[Grupo]:
    """Persiste TODAS as caixas do molde SEM ocupar (§5 — tela de Montagem).

    Preserva os pins existentes (`fixado`) e NÃO descarta caixas vazias. Não toca
    `alocacoes`/`sessoes`.
    """
    from app.services.motor.molde import materializar_molde
    from app.services.motor.preenchimento import aplicar_pins

    caixas = materializar_molde(db, ciclo, ctx)
    pins = capturar_pins(db, ciclo)
    aplicar_pins(caixas, pins, {}, {})
    _apagar_grupos(db, ciclo)
    grupos = _gravar_grupos(db, ciclo, caixas, date.today())
    db.flush()
    return grupos


def persistir(
    db: Session,
    ciclo: Ciclo,
    caixas: list[Caixa],
    matricula_id_por: Callable[[int, int], int | None],
    hoje: date | None = None,
) -> None:
    """Grava grupos + grupo_alunos + alocações + sessões do molde preenchido."""
    hoje = hoje or date.today()
    _apagar_alocacoes(db, ciclo)
    _apagar_grupos(db, ciclo)
    _gravar_grupos(db, ciclo, caixas, hoje)

    for caixa in caixas:
        for aluno_id in caixa.ocupantes:
            mid = matricula_id_por(aluno_id, caixa.area_id)
            if mid is None:
                continue
            aloc = Alocacao(
                aluno_id=aluno_id, local_id=caixa.local.id, matricula_id=mid,
                data_inicio=caixa.data_inicio, data_fim_prevista=caixa.data_fim,
                travada=aluno_id in caixa.fixos, ajuste_encontros=0,
                status=StatusAlocacao.ativa,
            )
            db.add(aloc)
            db.flush()
            horas = Decimal(str(round(caixa.horas, 2)))
            for d in caixa.datas:
                db.add(Sessao(
                    alocacao_id=aloc.id, data=d,
                    hora_inicio=caixa.local.hora_inicio, hora_fim=caixa.local.hora_fim,
                    horas=horas,
                    status=StatusSessao.cumprida if d < hoje else StatusSessao.prevista,
                ))
            m = db.get(Matricula, mid)
            if m is not None:
                m.data_conclusao_prevista = caixa.data_fim
    db.flush()
