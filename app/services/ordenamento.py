"""Derivação do `ordenamento` dos alunos (§6.3) — nunca é ordenação manual.

`ordenamento` (menor = maior prioridade) é a fonte que fila/remanejo/motor consomem.
As duas fases ('7' e '9_10') nunca disputam o mesmo local → numeração independente
(1..k por fase). Espelha `reindexPorPrioridade` / `reindexarOrdenamento` do protótipo
(state.js:1147 / :1005).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno
from app.services.common import fase_do_aluno


def _por_fase(db: Session, ciclo_id: int) -> dict[str, list[Aluno]]:
    alunos = db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo_id)).all()
    grupos: dict[str, list[Aluno]] = {}
    for a in alunos:
        grupos.setdefault(fase_do_aluno(a.semestre).value, []).append(a)
    return grupos


def reindex_por_prioridade(db: Session, ciclo_id: int) -> None:
    """Deriva `ordenamento` 1..k por fase: prioritários primeiro, depois por matrícula.

    Chamar quando `prioridade` de algum aluno muda, ou ao incluir/remover aluno.
    """
    for grupo in _por_fase(db, ciclo_id).values():
        # prioridade desc (True antes de False), depois matrícula asc.
        grupo.sort(key=lambda a: (not a.prioridade, a.matricula))
        for i, aluno in enumerate(grupo, start=1):
            aluno.ordenamento = i


def reindexar_ordenamento(db: Session, ciclo_id: int) -> None:
    """Recomprime `ordenamento` para 1..k por fase, preservando a ordem relativa atual.

    Usado após remover um aluno (fecha o buraco: #3 vira #2) sem reordenar por prioridade.
    """
    for grupo in _por_fase(db, ciclo_id).values():
        grupo.sort(key=lambda a: a.ordenamento)
        for i, aluno in enumerate(grupo, start=1):
            aluno.ordenamento = i
