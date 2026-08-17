"""Ajuste manual da escala (§9) — bloqueio com sugestão e volta à fila."""
from __future__ import annotations

from sqlalchemy import select

from app.models.enums import DiaSemana, StatusAlocacao
from app.models.escala import Alocacao, Grupo, GrupoAluno
from app.services.motor import ajuste, escala
import tests.factories as f


def _alocs(db, aluno_id):
    return db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == aluno_id, Alocacao.status == StatusAlocacao.ativa
    )).all()


def _grupo_do_aluno(db, aluno_id):
    return db.scalars(
        select(Grupo).join(GrupoAluno, GrupoAluno.grupo_id == Grupo.id)
        .where(GrupoAluno.aluno_id == aluno_id)
    ).first()


def test_remover_volta_para_fila_e_readicionar(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)

    g = _grupo_do_aluno(db, a1.id)
    assert ajuste.remover(db, a1.id, g.id).ok
    assert _alocs(db, a1.id) == []

    r = ajuste.adicionar_da_fila(db, a1.id, g.id)
    assert r.ok
    alocs = _alocs(db, a1.id)
    assert len(alocs) == 1 and alocs[0].travada is True  # colocação manual nasce fixa


def test_mover_bloqueado_por_blocklist_sugere(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    loc1 = f.local(db, c, ar, dia=DiaSemana.terca, capacidade=4)
    loc2 = f.local(db, c, ar, dia=DiaSemana.quinta, capacidade=4)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    f.bloquear_local(db, a1, loc2)
    escala.gerar_escala(db, c)

    g_orig = _grupo_do_aluno(db, a1.id)                       # em loc1 (loc2 bloqueado)
    g_dest = db.scalars(select(Grupo).where(Grupo.local_id == loc2.id).order_by(Grupo.onda)).first()
    r = ajuste.mover(db, a1.id, g_orig.id, g_dest.id)
    assert not r.ok
    assert any("bloqueado" in m for m in r.motivos)


def test_mover_ok_entre_caixas_da_mesma_area(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    loc1 = f.local(db, c, ar, dia=DiaSemana.terca, capacidade=4)
    loc2 = f.local(db, c, ar, dia=DiaSemana.quinta, capacidade=4)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)

    g_orig = _grupo_do_aluno(db, a1.id)
    outro_local = loc2.id if g_orig.local_id == loc1.id else loc1.id
    g_dest = db.scalars(select(Grupo).where(Grupo.local_id == outro_local).order_by(Grupo.onda)).first()
    r = ajuste.mover(db, a1.id, g_orig.id, g_dest.id)
    assert r.ok
    assert _grupo_do_aluno(db, a1.id).local_id == outro_local
