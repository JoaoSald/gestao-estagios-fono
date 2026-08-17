"""Eventos de meio de ciclo (§10) e encontros (§10.5)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.enums import StatusAlocacao
from app.models.escala import Alocacao
from app.services.motor import encontros, escala, eventos_ciclo
import tests.factories as f

HOJE = date.today()


def _alocs(db, aluno_id):
    return db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == aluno_id, Alocacao.status == StatusAlocacao.ativa
    )).all()


def test_nova_matricula_pega_caixa_futura(db_session):
    db = db_session
    c = f.ciclo(db)
    ar_a = f.area(db, carga=16)
    ar_b = f.area(db, carga=16)
    f.local(db, c, ar_a, capacidade=4)
    loc_b = f.local(db, c, ar_b, capacidade=4)     # caixas materializadas no gerar (vazias)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar_a)                     # só A antes de gerar
    escala.gerar_escala(db, c)

    f.matricular(db, a1, ar_b)                     # matrícula nova no meio do ciclo
    r = eventos_ciclo.nova_matricula(db, a1.id, ar_b.id)
    assert r.ok
    aloc_b = db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == a1.id, Alocacao.local_id == loc_b.id
    )).first()
    assert aloc_b is not None
    assert aloc_b.data_inicio > HOJE               # caixa FUTURA (§10.1)


def test_novo_local_oferece_a_fila(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)                     # sem local p/ a área → a1 aguardando
    assert _alocs(db, a1.id) == []

    loc = f.local(db, c, ar, capacidade=4)
    res = eventos_ciclo.novo_local(db, loc.id)
    assert res["caixas_criadas"] >= 1 and res["alocados"] >= 1
    assert _alocs(db, a1.id)                        # agora alocado


def test_encontros_ajuste_reforco_e_falta(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    m = f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)

    aloc = _alocs(db, a1.id)[0]
    antes = encontros.contar_encontros(db, m)
    depois = encontros.ajustar_encontros(db, aloc.id, -1)
    assert depois["feitos"] == max(0, antes["feitos"] - 1)
    voltou = encontros.ajustar_encontros(db, aloc.id, +1)
    assert voltou["feitos"] == antes["feitos"]
