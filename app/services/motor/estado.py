"""Ponte entre a escala PERSISTIDA (grupos/alocações) e as `Caixa` em memória.

O ajuste manual (§5), a montagem (§5) e os eventos de meio de ciclo (§7/§8) operam sobre
o que já está no banco. Este módulo reconstrói as `Caixa` a partir dos `grupos` (datas
re-derivadas do molde — grade-primeiro) para reaproveitar as 4 restrições duras, e provê
o "sentar"/"levantar" um aluno numa caixa (alocação + sessões + membro do grupo).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.aluno import Matricula
from app.models.ciclo import Ciclo
from app.models.enums import StatusAlocacao, StatusMatricula, StatusSessao
from app.models.escala import Alocacao, Grupo, GrupoAluno, Sessao
from app.models.local import Local
from app.services.motor import molde
from app.services.motor.calendario import ContextoCalendario, horas_sessao, ocorrencias_dia
from app.services.motor.molde import Caixa


@dataclass
class MoldeVivo:
    """Caixas persistidas indexadas por grupo_id, + os próprios Grupo (para escrever)."""
    caixas: dict[int, Caixa]         # grupo_id -> Caixa
    grupos: dict[int, Grupo]         # grupo_id -> Grupo

    def por_area(self, area_id: int) -> list[tuple[int, Caixa]]:
        return [(gid, cx) for gid, cx in self.caixas.items() if cx.area_id == area_id]

    def compromissos(self, aluno_id: int, excluir_grupo: int | None = None) -> list[Caixa]:
        return [
            cx for gid, cx in self.caixas.items()
            if aluno_id in cx.ocupantes and gid != excluir_grupo
        ]

    def grupo_do_aluno_no_local(self, aluno_id: int, local_id: int) -> int | None:
        for gid, cx in self.caixas.items():
            if cx.local.id == local_id and aluno_id in cx.ocupantes:
                return gid
        return None


def carregar_molde_vivo(db: Session, ciclo: Ciclo, ctx: ContextoCalendario) -> MoldeVivo:
    grupos = db.scalars(select(Grupo).where(Grupo.ciclo_id == ciclo.id)).all()
    locais = {l.id: l for l in molde.locais_ativos(db, ciclo)}

    # Datas reais re-derivadas do molde (grade-primeiro), indexadas por (local, onda).
    datas_por: dict[tuple[int, int], Caixa] = {}
    for lid, local in locais.items():
        for cx in molde.caixas_do_local(local, ciclo, ctx):
            datas_por[(lid, cx.onda)] = cx

    caixas: dict[int, Caixa] = {}
    mapa_grupos: dict[int, Grupo] = {}
    for g in grupos:
        local = locais.get(g.local_id) or db.get(Local, g.local_id)
        base = datas_por.get((g.local_id, g.onda))
        if base is not None:
            datas, horas = base.datas, base.horas
        else:
            datas = [d for d in ocorrencias_dia(local.dia_semana, g.data_inicio, g.data_fim)
                     if not ctx.data_bloqueada(d, local)]
            horas = horas_sessao(local)
        cx = Caixa(
            local=local, area_id=g.area_id, onda=g.onda, datas=datas,
            data_inicio=g.data_inicio, data_fim=g.data_fim,
            capacidade=local.capacidade, horas=horas,
        )
        for m in g.membros:
            cx.ocupantes.append(m.aluno_id)
            if m.fixado:
                cx.fixos.add(m.aluno_id)
        caixas[g.id] = cx
        mapa_grupos[g.id] = g
    return MoldeVivo(caixas=caixas, grupos=mapa_grupos)


def matricula_de(db: Session, aluno_id: int, area_id: int) -> Matricula | None:
    return db.scalars(select(Matricula).where(
        Matricula.aluno_id == aluno_id, Matricula.area_id == area_id
    )).first()


def sentar(
    db: Session, aluno_id: int, caixa: Caixa, grupo_id: int,
    matricula_id: int, *, fixado: bool, hoje: date | None = None,
) -> None:
    """Cria alocação + sessões (datas reais da caixa) + membro do grupo."""
    hoje = hoje or date.today()
    aloc = Alocacao(
        aluno_id=aluno_id, local_id=caixa.local.id, matricula_id=matricula_id,
        data_inicio=caixa.data_inicio, data_fim_prevista=caixa.data_fim,
        travada=fixado, ajuste_encontros=0, status=StatusAlocacao.ativa,
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
    db.add(GrupoAluno(grupo_id=grupo_id, aluno_id=aluno_id, fixado=fixado))
    m = db.get(Matricula, matricula_id)
    if m is not None:
        m.data_conclusao_prevista = caixa.data_fim
        if m.status == StatusMatricula.incompleta:
            m.status = StatusMatricula.em_andamento
    db.flush()


def levantar(db: Session, aluno_id: int, local_id: int, grupo_id: int) -> None:
    """Remove a alocação (cascade sessões) e o membro do grupo — libera o assento."""
    alocs = db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == aluno_id, Alocacao.local_id == local_id
    )).all()
    for a in alocs:
        db.delete(a)  # cascade sessoes
    ga = db.scalars(select(GrupoAluno).where(
        GrupoAluno.grupo_id == grupo_id, GrupoAluno.aluno_id == aluno_id
    )).first()
    if ga is not None:
        db.delete(ga)
    db.flush()
