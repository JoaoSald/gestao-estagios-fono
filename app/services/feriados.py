"""Importação automática de feriados (§11).

Usa a biblioteca `holidays` para carregar os feriados nacionais do Brasil + os
estaduais do Rio Grande do Sul (RS) do período do ciclo, inserindo-os como eventos
(tipo=feriado, origem=api_feriados, bloqueia_estagio=True). É chamada ao abrir o ciclo.
"""
from __future__ import annotations

from datetime import date

import holidays
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendario import Evento
from app.models.ciclo import Ciclo
from app.models.enums import OrigemEvento, TipoEvento


def feriados_do_periodo(inicio: date, fim: date) -> list[tuple[date, str]]:
    """(data, nome) de todos os feriados BR + RS entre `inicio` e `fim` (inclusive)."""
    anos = list(range(inicio.year, fim.year + 1))
    br_rs = holidays.country_holidays("BR", subdiv="RS", years=anos)
    return sorted((d, nome) for d, nome in br_rs.items() if inicio <= d <= fim)


def importar_feriados(db: Session, ciclo: Ciclo) -> int:
    """Insere os feriados do período do ciclo como eventos. Idempotente: pula os que já
    existem (mesmo nome + data). Devolve quantos foram criados. Não faz commit próprio
    (deixa para quem orquestra a transação — ex.: ciclo_service.abrir)."""
    existentes = {
        (e.nome, e.data_inicio)
        for e in db.scalars(select(Evento).where(Evento.ciclo_id == ciclo.id)).all()
    }
    criados = 0
    for dia, nome in feriados_do_periodo(ciclo.data_inicio, ciclo.data_fim):
        if (nome, dia) in existentes:
            continue
        db.add(Evento(
            ciclo_id=ciclo.id, nome=nome, tipo=TipoEvento.feriado,
            origem=OrigemEvento.api_feriados, data_inicio=dia, data_fim=dia,
            bloqueia_estagio=True,
        ))
        existentes.add((nome, dia))
        criados += 1
    db.flush()
    return criados
