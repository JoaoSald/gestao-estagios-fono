"""Smoke dos endpoints do motor (TestClient + savepoint)."""
from __future__ import annotations

from sqlalchemy import select

from app.models.enums import StatusAlocacao
from app.models.escala import Alocacao, Grupo, GrupoAluno
import tests.factories as f


def test_gerar_e_ler_grupos_e_escala(client, db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    loc = f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)

    r = client.post(f"/ciclos/{c.id}/escala/gerar")
    assert r.status_code == 200, r.text
    rel = r.json()
    assert rel["alocados"] == 1 and rel["total_alunos"] >= 1

    g = client.get(f"/ciclos/{c.id}/grupos")
    assert g.status_code == 200
    assert any(x["local_id"] == loc.id for x in g.json())

    e = client.get(f"/alunos/{a1.id}/escala")
    assert e.status_code == 200
    body = e.json()
    assert len(body["alocacoes"]) == 1
    assert body["alocacoes"][0]["total"] == loc.numero_encontros


def test_mover_bloqueio_via_api(client, db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    loc1 = f.local(db, c, ar, capacidade=4)
    loc2 = f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    f.bloquear_local(db, a1, loc2)
    client.post(f"/ciclos/{c.id}/escala/gerar")

    g_orig = db.scalars(
        select(Grupo).join(GrupoAluno, GrupoAluno.grupo_id == Grupo.id)
        .where(GrupoAluno.aluno_id == a1.id)
    ).first()
    g_dest = db.scalars(select(Grupo).where(Grupo.local_id == loc2.id).order_by(Grupo.onda)).first()
    r = client.post("/escala/mover", json={
        "aluno_id": a1.id, "grupo_origem": g_orig.id, "grupo_destino": g_dest.id,
    })
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_encontros_via_api(client, db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    client.post(f"/ciclos/{c.id}/escala/gerar")

    aloc = db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == a1.id, Alocacao.status == StatusAlocacao.ativa
    )).first()
    r = client.post(f"/alocacoes/{aloc.id}/encontros", json={"delta": -1})
    assert r.status_code == 200
    assert set(r.json()) == {"total", "feitos"}
