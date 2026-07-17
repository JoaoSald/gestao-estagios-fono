"""Regras de Matrículas — oferta por fase, carry-forward, pré-requisito (aviso).

Pré-requisito Audiologia I é NÃO-bloqueante (regra revista §4 + protótipo): quando falta
o registro concluído, o service devolve um AVISO, mas nunca impede matrícula/alocação.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError, NaoEncontrado
from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area
from app.models.enums import FaseArea, StatusMatricula
from app.services.common import fase_do_aluno

AVISO_PRE_REQUISITO = "Sem registro de Audiologia I — conferir (não bloqueia)."


def areas_ofertadas(db: Session, fase: FaseArea) -> list[Area]:
    """Áreas que a fase enxerga: leaf/simples (não compostas) da fase.

    fase '7' (mini-ciclo) = só a área pré-requisito (Audiologia I).
    fase '9_10' = as demais áreas leaf.
    """
    return list(db.scalars(
        select(Area).where(Area.fase == fase, Area.composta.is_(False)).order_by(Area.nome)
    ).all())


def area_pre_requisito(db: Session) -> Area | None:
    return db.scalars(select(Area).where(Area.pre_requisito.is_(True))).first()


def pre_requisito_concluido(db: Session, aluno_id: int) -> bool:
    """True se o aluno tem matrícula concluída na área pré-requisito."""
    pr = area_pre_requisito(db)
    if pr is None:
        return False
    m = db.scalars(select(Matricula).where(
        Matricula.aluno_id == aluno_id,
        Matricula.area_id == pr.id,
        Matricula.status == StatusMatricula.concluida,
    )).first()
    return m is not None


def avisos_pre_requisito(db: Session, aluno: Aluno) -> list[str]:
    """Aviso não-bloqueante para aluno de 9/10 sem Audiologia I registrada (§4)."""
    if fase_do_aluno(aluno.semestre) == FaseArea._9_10 and not pre_requisito_concluido(db, aluno.id):
        return [AVISO_PRE_REQUISITO]
    return []


def sincronizar(db: Session, aluno: Aluno, itens: list) -> list[str]:
    """Aplica o conjunto desejado de matrículas do aluno (as 'marcadas' da fase).

    - Cria as novas; atualiza o status das existentes.
    - Remove as `em_andamento` desmarcadas; **preserva** concluídas/interrompidas/incompletas
      (carry-forward — histórico).
    - Só matricula áreas leaf; `em_andamento` só na fase do aluno; `concluida` (carry-forward)
      pode ser qualquer área leaf.
    Retorna a lista de avisos (ex.: pré-requisito).
    """
    fase = fase_do_aluno(aluno.semestre)
    desejadas: dict[int, StatusMatricula] = {}
    for item in itens:
        area = db.get(Area, item.area_id)
        if area is None:
            raise NaoEncontrado(f"Área {item.area_id} não encontrada.")
        if area.composta:
            raise DomainError(f"A área '{area.nome}' é composta e não é matriculável.")
        if item.status == StatusMatricula.em_andamento and area.fase != fase:
            raise DomainError(
                f"A área '{area.nome}' não pertence à fase do aluno ({fase.value})."
            )
        desejadas[item.area_id] = item.status

    existentes = {m.area_id: m for m in aluno.matriculas}

    # Upsert das desejadas.
    for area_id, status in desejadas.items():
        m = existentes.get(area_id)
        if m is None:
            db.add(Matricula(
                aluno_id=aluno.id, area_id=area_id, status=status,
                data_matricula=date.today(),
                data_conclusao=date.today() if status == StatusMatricula.concluida else None,
            ))
        else:
            m.status = status

    # Remoção: só `em_andamento` desmarcadas (concluídas etc. sobrevivem = carry-forward).
    for area_id, m in existentes.items():
        if area_id not in desejadas and m.status == StatusMatricula.em_andamento:
            db.delete(m)

    db.flush()
    return avisos_pre_requisito(db, aluno)
