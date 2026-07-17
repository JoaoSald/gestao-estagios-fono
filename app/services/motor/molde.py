"""Fase 1 — Materialização do molde (§4).

Unidade atômica = (local, dia). No modelo SLOT (1 local = 1 campo+dia+turno), cada local
é UMA família de caixas. Fatia as datas viáveis em blocos consecutivos de N encontros;
cada bloco COMPLETO vira uma caixa. O bloco final incompleto é descartado (§4, passo 5; decisão §11.1) —
capacidade perdida no ciclo. As caixas saem encadeadas (a próxima começa onde a anterior
terminou), pois são fatias consecutivas da mesma fila de datas.

Construtor PURO: não toca o banco. A persistência do molde vive em `persistencia.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ciclo import Ciclo
from app.models.local import Local
from app.services.motor.calendario import ContextoCalendario, horas_sessao


@dataclass
class Caixa:
    """Vaga de onda: uma corrida completa de um grupo numa área (§2).

    N sessões consecutivas no dia fixo do slot. Terminar a caixa = concluir a área.
    `ocupantes` = aluno_ids; `fixos` = subset pinado (montagem/travada), imune à
    consolidação e ao auto-preenchimento.
    """
    local: Local
    area_id: int
    onda: int
    datas: list[date]
    data_inicio: date
    data_fim: date
    capacidade: int
    horas: float                              # horas/semana do slot (= horas_sessao × 1 dia)
    ocupantes: list[int] = field(default_factory=list)
    fixos: set[int] = field(default_factory=set)

    @property
    def vaga(self) -> int:
        return self.capacidade - len(self.ocupantes)

    def tem_vaga(self) -> bool:
        return len(self.ocupantes) < self.capacidade


def locais_ativos(db: Session, ciclo: Ciclo) -> list[Local]:
    return list(db.scalars(select(Local).where(
        Local.ciclo_id == ciclo.id, Local.ativo.is_(True)
    ).order_by(Local.id)).all())


def caixas_do_local(local: Local, ciclo: Ciclo, ctx: ContextoCalendario) -> list[Caixa]:
    """Fatia as datas viáveis do slot em blocos de N; blocos completos viram caixas."""
    n = local.numero_encontros
    if n <= 0:
        return []
    datas = ctx.datas_viaveis(local, ciclo)
    horas = horas_sessao(local)
    caixas: list[Caixa] = []
    onda = 0
    for i in range(0, len(datas), n):
        bloco = datas[i:i + n]
        if len(bloco) < n:
            break  # bloco final incompleto → não vira caixa (§4, passo 5)
        onda += 1
        caixas.append(Caixa(
            local=local, area_id=local.area_id, onda=onda,
            datas=bloco, data_inicio=bloco[0], data_fim=bloco[-1],
            capacidade=local.capacidade, horas=horas,
        ))
    return caixas


def materializar_molde(
    db: Session,
    ciclo: Ciclo,
    ctx: ContextoCalendario,
    locais: list[Local] | None = None,
    avisos: list[str] | None = None,
) -> list[Caixa]:
    """Molde do ciclo: todas as caixas de todos os slots ativos. Determinístico (§4).

    Local ativo sem docente é pulado ('todo local ativo precisa de docente' é
    validação, não constraint) — registra aviso quando `avisos` é fornecido.
    """
    if locais is None:
        locais = locais_ativos(db, ciclo)
    caixas: list[Caixa] = []
    for local in locais:
        if local.docente_id is None:
            if avisos is not None:
                avisos.append(f"Local '{local.campo}' ({local.dia_semana.value}) sem docente — pulado.")
            continue
        caixas.extend(caixas_do_local(local, ciclo, ctx))
    return caixas
