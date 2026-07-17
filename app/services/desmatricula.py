"""Desmatrícula / interrupção de estágio (§8.2) — espelha `desmatricular` (state.js:728).

Interromper ≠ excluir aluno: preserva o histórico (a matrícula vira `interrompida`, não é
apagada). Modelo grade-primeiro (§8.2): a vaga liberada **não gera gatilho de remanejo** e
NÃO promove ninguém automaticamente — o grupo segue desfalcado. Aqui só marcamos a
interrupção e registramos no log (sem pendência de remanejo).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NaoEncontrado
from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area
from app.models.enums import StatusAlocacao, StatusMatricula, StatusSessao
from app.models.escala import Alocacao, Sessao
from app.services import common


def desmatricular_area(
    db: Session, aluno_id: int, area_id: int, motivo: str | None = None
) -> Matricula:
    aluno = common.obter_ou_404(db, Aluno, aluno_id, "Aluno")
    matricula = db.scalars(select(Matricula).where(
        Matricula.aluno_id == aluno_id,
        Matricula.area_id == area_id,
        Matricula.status == StatusMatricula.em_andamento,
    )).first()
    if matricula is None:
        raise NaoEncontrado("Matrícula em andamento não encontrada para esta área.")

    hoje = date.today()
    # 1. Marca interrompida (não apaga) — guarda motivo/data, zera previsão.
    matricula.status = StatusMatricula.interrompida
    matricula.motivo_interrupcao = motivo
    matricula.data_interrupcao = hoje
    matricula.data_conclusao_prevista = None

    # 2. Cancela alocações ativas e sessões FUTURAS (cumpridas ficam como registro).
    alocacoes = db.scalars(select(Alocacao).where(
        Alocacao.matricula_id == matricula.id,
        Alocacao.status == StatusAlocacao.ativa,
    )).all()
    for aloc in alocacoes:
        aloc.status = StatusAlocacao.cancelada  # 3. libera a vaga
        sessoes = db.scalars(select(Sessao).where(
            Sessao.alocacao_id == aloc.id,
            Sessao.status == StatusSessao.prevista,
            Sessao.data >= hoje,
        )).all()
        for s in sessoes:
            s.status = StatusSessao.cancelada

    # 4. Só registra no log — vaga aberta não é gatilho (§8.2), sem promoção automática.
    area = db.get(Area, area_id)
    common.registrar_atividade(
        db, aluno.ciclo,
        f"Vaga liberada em {area.nome if area else area_id} — {aluno.nome} interrompeu.",
    )
    common.commit(db, "Não foi possível interromper o estágio.")
    db.refresh(matricula)
    return matricula
