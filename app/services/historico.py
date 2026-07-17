"""Snapshot denormalizado do ciclo no encerramento (§8 · FASE 8).

O passado não muda: ao encerrar, grava um retrato por aluno em `historico` (áreas, carga,
situação). Reusa a contagem de encontros do motor.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno
from app.models.catalogo import Area
from app.models.ciclo import Ciclo
from app.models.enums import SituacaoHistorico, StatusMatricula
from app.models.operacao import Historico
from app.services.motor import encontros


def snapshot_ciclo(db: Session, ciclo: Ciclo) -> int:
    """Grava um `Historico` por aluno do ciclo. Devolve quantos foram gravados."""
    ano = ciclo.data_inicio.year
    hoje = date.today()
    alunos = db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo.id).order_by(Aluno.nome)).all()
    n = 0
    for aluno in alunos:
        areas_json = []
        carga_total = 0
        n_areas = concluidas = 0
        for m in aluno.matriculas:
            area = db.get(Area, m.area_id)
            cont = encontros.contar_encontros(db, m)
            n_areas += 1
            if m.status == StatusMatricula.concluida:
                concluidas += 1
                carga_total += area.carga_exigida if area else 0
            areas_json.append({
                "nome": area.nome if area else "?",
                "carga_exigida": area.carga_exigida if area else 0,
                "feitos": cont["feitos"], "total": cont["total"],
                "status": m.status.value,
                "data_conclusao": m.data_conclusao.isoformat() if m.data_conclusao else None,
            })
        situacao = (SituacaoHistorico.ciclo_completo
                    if n_areas > 0 and concluidas == n_areas else SituacaoHistorico.pendente)
        db.add(Historico(
            ciclo_id=ciclo.id, ano=ano, aluno_nome=aluno.nome, matricula=aluno.matricula,
            areas=areas_json, carga_horaria_total=carga_total, situacao=situacao,
            encerramento=hoje, criado_em=datetime.now(),
        ))
        n += 1
    db.flush()
    return n
