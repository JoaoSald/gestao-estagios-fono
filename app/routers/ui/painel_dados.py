"""Dados do Painel de Operação (tradução de painel.js) — só leitura."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno, Matricula
from app.models.calendario import Evento
from app.models.enums import StatusAlocacao, StatusMatricula
from app.models.escala import Alocacao
from app.models.local import Local
from app.models.operacao import Atividade
from app.services.common import get_ciclo_ativo


def _estado_matricula(db: Session, m: Matricula, fim_ciclo: date) -> str:
    if m.status == StatusMatricula.concluida:
        return "concluida"
    if m.status == StatusMatricula.interrompida:
        return "interrompida"
    if m.status == StatusMatricula.incompleta:
        return "incompleta"
    tem_aloc = db.scalars(select(Alocacao).where(
        Alocacao.matricula_id == m.id, Alocacao.status == StatusAlocacao.ativa
    )).first() is not None
    if not tem_aloc:
        return "aguardando"
    if m.data_conclusao_prevista and m.data_conclusao_prevista > fim_ciclo:
        return "em_risco"
    return "em_andamento"


def montar_painel(db: Session) -> dict:
    ciclo = get_ciclo_ativo(db)
    if ciclo is None:
        return {"sem_ciclo": True, "kpis": [], "eventos": [], "atividade": [], "progresso": {}}

    # "O tempo passando" (§7/§8.5): reflete conclusões e grupos em andamento por data.
    from app.services.motor import encontros
    encontros.sincronizar_tempo(db, ciclo)

    hoje = date.today()
    n_alunos = db.scalar(select(func.count()).select_from(Aluno).where(Aluno.ciclo_id == ciclo.id)) or 0
    n_locais = db.scalar(select(func.count()).select_from(Local).where(
        Local.ciclo_id == ciclo.id, Local.ativo.is_(True))) or 0
    n_alocs = db.scalar(select(func.count()).select_from(Alocacao)
        .join(Aluno, Alocacao.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id, Alocacao.status == StatusAlocacao.ativa)) or 0

    eventos = db.scalars(select(Evento).where(
        Evento.ciclo_id == ciclo.id, Evento.data_fim >= hoje
    ).order_by(Evento.data_inicio).limit(5)).all()

    atividade = db.scalars(select(Atividade).where(
        Atividade.ciclo_id == ciclo.id).order_by(Atividade.id.desc()).limit(8)).all()

    # Progresso da turma: distribuição dos estados das matrículas.
    matriculas = db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id)).all()
    progresso = {k: 0 for k in ("concluida", "em_andamento", "aguardando", "em_risco", "interrompida", "incompleta")}
    for m in matriculas:
        est = _estado_matricula(db, m, ciclo.data_fim)
        progresso[est] = progresso.get(est, 0) + 1
    progresso["total"] = sum(v for k, v in progresso.items() if k != "total") or 0

    kpis = [
        {"label": "Alunos", "valor": n_alunos, "ic": "users", "sub": "no ciclo", "warn": False},
        {"label": "Locais ativos", "valor": n_locais, "ic": "building", "sub": "cenários de prática", "warn": False},
        {"label": "Estágios gerados", "valor": n_alocs, "ic": "grid", "sub": "alocações ativas", "warn": False},
        {"label": "Eventos próximos", "valor": len(eventos), "ic": "calendar", "sub": "nos próximos dias", "warn": False},
        {"label": "Alunos em risco", "valor": progresso["em_risco"], "ic": "alert",
         "sub": "de não fechar no prazo", "warn": progresso["em_risco"] > 0},
    ]

    return {
        "sem_ciclo": False,
        "kpis": kpis,
        "eventos": eventos,
        "atividade": atividade,
        "progresso": progresso,
        "escala_desatualizada": ciclo.escala_desatualizada,
    }
