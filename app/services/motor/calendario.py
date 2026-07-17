"""Helpers de calendário do motor — a DATA é função só da infraestrutura (§1).

Uma única fonte de datas viáveis: as ocorrências do dia-da-semana do slot dentro do
ciclo, removendo (a) eventos que bloqueiam estágio, (b) indisponibilidades do local e
(c) dias sem cobertura (docente E preceptor ambos afastados — §4/§8.3). Isso alimenta
a materialização do molde (`molde.py`). Datas já vêm como `datetime.date` do banco —
nada de `strptime` inline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendario import Afastamento, Evento
from app.models.ciclo import Ciclo
from app.models.local import IndisponibilidadeLocal, Local
from app.models.enums import DiaSemana

# DiaSemana → índice de date.weekday() (segunda=0 … domingo=6).
IDX_DIA: dict[DiaSemana, int] = {
    DiaSemana.segunda: 0,
    DiaSemana.terca: 1,
    DiaSemana.quarta: 2,
    DiaSemana.quinta: 3,
    DiaSemana.sexta: 4,
    DiaSemana.sabado: 5,
    DiaSemana.domingo: 6,
}


def ocorrencias_dia(dia: DiaSemana, inicio: date, fim: date) -> list[date]:
    """Todas as datas daquele dia-da-semana em [inicio, fim] (inclusive)."""
    alvo = IDX_DIA[dia]
    # Anda até a 1ª ocorrência do dia-da-semana alvo.
    delta = (alvo - inicio.weekday()) % 7
    cursor = inicio + timedelta(days=delta)
    datas: list[date] = []
    while cursor <= fim:
        datas.append(cursor)
        cursor += timedelta(days=7)
    return datas


def horas_sessao(local: Local) -> float:
    """Horas REAIS de cada encontro: `horas_sessao` quando cadastrado; senão (fim−início)."""
    if local.horas_sessao and local.horas_sessao > 0:
        return float(local.horas_sessao)
    ini, fim = local.hora_inicio, local.hora_fim
    return (fim.hour * 60 + fim.minute - ini.hour * 60 - ini.minute) / 60.0


def _dentro(d: date, ini: date, fim: date) -> bool:
    return ini <= d <= fim


@dataclass
class ContextoCalendario:
    """Índices carregados 1× por geração (evita N+1). Todos por ciclo."""
    eventos_bloqueantes: list[tuple[date, date]] = field(default_factory=list)
    afast_docente: dict[int, list[tuple[date, date]]] = field(default_factory=dict)
    afast_preceptor: dict[int, list[tuple[date, date]]] = field(default_factory=dict)
    indisp_local: dict[int, list[tuple[date, date]]] = field(default_factory=dict)
    # Desligamento permanente (`ativo=False`) — sem cobertura a partir de sempre (§7.1/§8.3).
    docentes_inativos: set[int] = field(default_factory=set)
    preceptores_inativos: set[int] = field(default_factory=set)

    # --- Cobertura (§4/§8.3) ---
    def _pessoa_afastada(self, index: dict[int, list[tuple[date, date]]], pid: int | None, d: date) -> bool:
        if pid is None:
            return False
        return any(_dentro(d, ini, fim) for ini, fim in index.get(pid, ()))

    def docente_afastado_em(self, docente_id: int | None, d: date) -> bool:
        """Sem cobertura do docente em `d`: desligado (permanente) OU afastado no período."""
        if docente_id is None:
            return False
        if docente_id in self.docentes_inativos:
            return True
        return self._pessoa_afastada(self.afast_docente, docente_id, d)

    def preceptor_afastado_em(self, local: Local, d: date) -> bool:
        """Preceptor polimórfico: 'docente' consulta docentes; 'externo', preceptores.
        Considera desligamento permanente (`ativo=False`) e afastamento no período."""
        if local.preceptor_id is None:
            return False
        if local.preceptor_tipo == "docente":
            if local.preceptor_id in self.docentes_inativos:
                return True
            return self._pessoa_afastada(self.afast_docente, local.preceptor_id, d)
        if local.preceptor_id in self.preceptores_inativos:
            return True
        return self._pessoa_afastada(self.afast_preceptor, local.preceptor_id, d)

    def local_sem_cobertura_em(self, local: Local, d: date) -> bool:
        """Cai só quando TODOS os responsáveis faltam: docente E preceptor (se houver)."""
        docente_fora = local.docente_id is None or self.docente_afastado_em(local.docente_id, d)
        if local.preceptor_id is None:
            return docente_fora
        return docente_fora and self.preceptor_afastado_em(local, d)

    def evento_bloqueia_em(self, d: date) -> bool:
        return any(_dentro(d, ini, fim) for ini, fim in self.eventos_bloqueantes)

    def local_indisponivel_em(self, local_id: int, d: date) -> bool:
        return any(_dentro(d, ini, fim) for ini, fim in self.indisp_local.get(local_id, ()))

    def data_bloqueada(self, d: date, local: Local) -> bool:
        return (
            not local.ativo                       # local desativado/inválido (§8.3)
            or self.evento_bloqueia_em(d)
            or self.local_indisponivel_em(local.id, d)
            or self.local_sem_cobertura_em(local, d)
        )

    def datas_viaveis(self, local: Local, ciclo: Ciclo) -> list[date]:
        """Fonte ÚNICA de datas: ocorrências do dia do slot, sem as bloqueadas (§4)."""
        return [
            d for d in ocorrencias_dia(local.dia_semana, ciclo.data_inicio, ciclo.data_fim)
            if not self.data_bloqueada(d, local)
        ]


def carregar_contexto(db: Session, ciclo: Ciclo) -> ContextoCalendario:
    """Monta os índices do ciclo (eventos bloqueantes, afastamentos, indisponibilidades)."""
    ctx = ContextoCalendario()

    for ev in db.scalars(select(Evento).where(
        Evento.ciclo_id == ciclo.id, Evento.bloqueia_estagio.is_(True)
    )).all():
        ctx.eventos_bloqueantes.append((ev.data_inicio, ev.data_fim))

    # Afastamentos: XOR docente/preceptor. Considera os do ciclo e os globais (ciclo_id nulo).
    for af in db.scalars(select(Afastamento).where(
        (Afastamento.ciclo_id == ciclo.id) | (Afastamento.ciclo_id.is_(None))
    )).all():
        intervalo = (af.data_inicio, af.data_retorno)
        if af.docente_id is not None:
            ctx.afast_docente.setdefault(af.docente_id, []).append(intervalo)
        elif af.preceptor_id is not None:
            ctx.afast_preceptor.setdefault(af.preceptor_id, []).append(intervalo)

    for indi in db.scalars(select(IndisponibilidadeLocal).join(Local).where(
        Local.ciclo_id == ciclo.id
    )).all():
        ctx.indisp_local.setdefault(indi.local_id, []).append((indi.data_inicio, indi.data_fim))

    # Desligamento permanente (§7.1/§8.3): docente/preceptor com `ativo=False`.
    from app.models.catalogo import Docente, Preceptor
    ctx.docentes_inativos = set(db.scalars(select(Docente.id).where(Docente.ativo.is_(False))).all())
    ctx.preceptores_inativos = set(db.scalars(select(Preceptor.id).where(Preceptor.ativo.is_(False))).all())

    return ctx
