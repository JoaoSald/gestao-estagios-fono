"""Montagem dos grupos (AR-8): molde vazio, banco de prioridade, pins e sua sobrevivência."""
from __future__ import annotations

from sqlalchemy import select

from app.models.enums import DiaSemana, Turno
from app.models.escala import Grupo, GrupoAluno, Alocacao
from app.services.motor import escala, montagem
import tests.factories as f


def _grupos_do_local(db, local_id):
    return db.scalars(select(Grupo).where(Grupo.local_id == local_id).order_by(Grupo.onda)).all()


def test_materializa_molde_vazio_e_banco(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    loc = f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c, prioridade=True)
    f.matricular(db, a1, ar)

    montagem.materializar(db, c)
    grupos = _grupos_do_local(db, loc.id)
    assert grupos and all(len(g.membros) == 0 for g in grupos)  # caixas vazias preservadas

    banco = montagem.banco_prioridade(db, c)
    item = next(x for x in banco if x["aluno_id"] == a1.id)
    assert ar.id in item["areas_pendentes"]
    assert item["ch_semanal"] == 0.0


def test_colocar_pin_e_area_nao_cursada(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    outra = f.area(db, carga=16)
    loc = f.local(db, c, ar, capacidade=4)
    loc_outra = f.local(db, c, outra, capacidade=4)
    a1 = f.aluno(db, c, prioridade=True)
    f.matricular(db, a1, ar)                      # cursa só `ar`
    montagem.materializar(db, c)

    g = _grupos_do_local(db, loc.id)[0]
    assert montagem.colocar(db, a1.id, g.id).ok
    ga = db.scalars(select(GrupoAluno).where(
        GrupoAluno.grupo_id == g.id, GrupoAluno.aluno_id == a1.id
    )).first()
    assert ga is not None and ga.fixado is True

    g_outra = _grupos_do_local(db, loc_outra.id)[0]
    r = montagem.colocar(db, a1.id, g_outra.id)
    assert not r.ok and any("não cursa" in m for m in r.motivos)


def test_colocar_bloqueia_por_teto_30h(db_session):
    db = db_session
    c = f.ciclo(db)
    ar_a = f.area(db, carga=16)
    ar_b = f.area(db, carga=28)
    loc_a = f.local(db, c, ar_a, dia=DiaSemana.terca, turno=Turno.manha, horas_sessao=4.0)
    loc_b = f.local(db, c, ar_b, dia=DiaSemana.quinta, turno=Turno.manha,
                    horas_sessao=28.0, numero_encontros=1)
    a1 = f.aluno(db, c, prioridade=True)
    f.matricular(db, a1, ar_a)
    f.matricular(db, a1, ar_b)
    montagem.materializar(db, c)

    ga = _grupos_do_local(db, loc_a.id)[0]
    gb = _grupos_do_local(db, loc_b.id)[0]
    assert montagem.colocar(db, a1.id, ga.id).ok           # 4h
    r = montagem.colocar(db, a1.id, gb.id)                 # +28h = 32h > 30
    assert not r.ok and any("30" in m for m in r.motivos)


def test_pin_sobrevive_geracao(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    loc = f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c, prioridade=True)
    f.matricular(db, a1, ar)
    montagem.materializar(db, c)

    grupos = _grupos_do_local(db, loc.id)
    alvo = grupos[1] if len(grupos) > 1 else grupos[0]     # pina numa onda específica
    onda_alvo = alvo.onda
    assert montagem.colocar(db, a1.id, alvo.id).ok

    escala.gerar_escala(db, c)

    # O pin sobreviveu: o aluno ficou na onda pinada, como membro fixado.
    ga = db.scalars(
        select(GrupoAluno).join(Grupo, GrupoAluno.grupo_id == Grupo.id)
        .where(Grupo.local_id == loc.id, GrupoAluno.aluno_id == a1.id, GrupoAluno.fixado.is_(True))
    ).first()
    assert ga is not None
    assert ga.grupo.onda == onda_alvo
    aloc = db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == a1.id, Alocacao.local_id == loc.id
    )).first()
    assert aloc is not None and aloc.travada is True
