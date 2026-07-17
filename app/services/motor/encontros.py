"""Contagem de encontros e status de conclusão (§8.5).

Filosofia (§8): responsabilidade compartilhada. O motor assume presença nos encontros
passados; o docente ajusta com ±1 (reforço/falta). A conclusão é DERIVADA:
`feitos ≥ N` → concluída (mesmo antecipada, sem disparar evento); caixa fechada com
`feitos < N` → incompleta (carry-forward, refaz no próximo ciclo).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno, Matricula
from app.models.ciclo import Ciclo
from app.models.enums import StatusAlocacao, StatusMatricula, StatusSessao
from app.models.escala import Alocacao, Sessao
from app.services import common


def _cumpridas(db: Session, alocacao_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Sessao).where(
        Sessao.alocacao_id == alocacao_id, Sessao.status == StatusSessao.cumprida
    )) or 0


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def contar_encontros(db: Session, matricula: Matricula) -> dict[str, int]:
    """{total, feitos} da ÁREA — com CARRY-FORWARD (§8.3).

    `total` = alvo da área (numero_encontros da caixa; uma caixa cobre a área inteira).
    `feitos` = soma das sessões cumpridas de TODAS as alocações da matrícula —
    **inclusive as canceladas por descarte** — mais o ajuste, limitado a [0, total].
    Assim, quando um local morre e o aluno é recolocado, ele **retoma em
    feitos/total** (o grupo novo começa 0/total para alunos frescos).
    """
    alocs = db.scalars(select(Alocacao).where(
        Alocacao.matricula_id == matricula.id,
    )).all()
    if not alocs:
        return {"total": 0, "feitos": 0}
    total = max((a.local.numero_encontros or 0) for a in alocs)
    cumpridas = sum(_cumpridas(db, a.id) for a in alocs)
    ajuste = sum((a.ajuste_encontros or 0) for a in alocs)
    feitos = _clamp(cumpridas + ajuste, 0, total)
    return {"total": total, "feitos": feitos}


def _fim_previsto(db: Session, matricula: Matricula) -> date | None:
    return db.scalar(select(func.max(Alocacao.data_fim_prevista)).where(
        Alocacao.matricula_id == matricula.id,
        Alocacao.status == StatusAlocacao.ativa,
    ))


def _tem_alocacao_ativa(db: Session, matricula_id: int) -> bool:
    return db.scalars(select(Alocacao).where(
        Alocacao.matricula_id == matricula_id, Alocacao.status == StatusAlocacao.ativa
    )).first() is not None


def atualizar_conclusao_matricula(db: Session, matricula: Matricula, hoje: date) -> None:
    """Recalcula o status de UMA matrícula a partir dos encontros (§8.5).

    Só mexe em matrículas com alocação ativa; carry-forward (concluídas/interrompidas sem
    alocação) fica intocado.
    """
    if not _tem_alocacao_ativa(db, matricula.id):
        return
    cont = contar_encontros(db, matricula)
    total, feitos = cont["total"], cont["feitos"]
    fim = _fim_previsto(db, matricula)

    if total > 0 and feitos >= total:
        if matricula.status != StatusMatricula.concluida:
            matricula.status = StatusMatricula.concluida
            matricula.data_conclusao = matricula.data_conclusao_prevista or hoje
    elif fim is not None and fim < hoje and feitos < total:
        # A caixa fechou sem atingir N → incompleta (refaz no próximo ciclo).
        matricula.status = StatusMatricula.incompleta
        matricula.data_conclusao = None
    else:
        # Ainda em curso: se estava concluída por engano, volta.
        if matricula.status == StatusMatricula.concluida:
            matricula.status = StatusMatricula.em_andamento
            matricula.data_conclusao = None


def atualizar_conclusoes(db: Session, ciclo: Ciclo, hoje: date | None = None) -> None:
    """Marca sessões passadas como cumpridas e recalcula a conclusão de cada matrícula."""
    hoje = hoje or date.today()
    # Sessões previstas já decorridas → cumpridas (presença assumida).
    sessoes = db.scalars(
        select(Sessao)
        .join(Alocacao, Sessao.alocacao_id == Alocacao.id)
        .join(Aluno, Alocacao.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id,
               Sessao.status == StatusSessao.prevista, Sessao.data < hoje)
    ).all()
    for s in sessoes:
        s.status = StatusSessao.cumprida
    db.flush()

    matriculas = db.scalars(
        select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id)
    ).all()
    for m in matriculas:
        atualizar_conclusao_matricula(db, m, hoje)
    db.flush()


def sincronizar_tempo(db: Session, ciclo: Ciclo, hoje: date | None = None) -> None:
    """Reflete "o tempo passando" (§7/§8.5) — automático, por data, SEM banner.

    Chamada ao carregar as telas de operação: (1) marca sessões decorridas como
    cumpridas e recalcula conclusões (`atualizar_conclusoes`); (2) atualiza o
    `status` dos grupos pela data — o próximo grupo entra em andamento no dia do
    seu 1º encontro sozinho. Idempotente; persiste (commit) o estado derivado.
    Só roda em ciclo `em_andamento`.
    """
    from app.models.enums import StatusCiclo, StatusGrupo
    from app.models.escala import Grupo
    if ciclo.status != StatusCiclo.em_andamento:
        return
    hoje = hoje or date.today()
    atualizar_conclusoes(db, ciclo, hoje)
    grupos = db.scalars(select(Grupo).where(Grupo.ciclo_id == ciclo.id)).all()
    for g in grupos:
        novo = StatusGrupo.em_andamento if g.data_inicio <= hoje else StatusGrupo.previsto
        if g.status != novo:
            g.status = novo
    common.commit(db, "Não foi possível sincronizar o tempo.")


def ajustar_encontros(db: Session, alocacao_id: int, delta: int) -> dict[str, int]:
    """Ajuste manual do docente: +1 reforço / −1 falta. Recalcula conclusão. Devolve {total, feitos}."""
    aloc = common.obter_ou_404(db, Alocacao, alocacao_id, "Alocação")
    total = aloc.local.numero_encontros or 0
    cumpridas = _cumpridas(db, aloc.id)
    feitos = _clamp(cumpridas + (aloc.ajuste_encontros or 0) + delta, 0, total)
    aloc.ajuste_encontros = feitos - cumpridas
    db.flush()
    atualizar_conclusao_matricula(db, aloc.matricula, date.today())
    common.registrar_atividade(
        db, aloc.aluno.ciclo,
        "Reforço: +1 encontro concedido" if delta > 0 else "Falta: −1 encontro registrado",
    )
    common.commit(db, "Não foi possível ajustar os encontros.")
    return contar_encontros(db, aloc.matricula)
