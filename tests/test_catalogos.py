"""FASE 3 · Milestone A — Áreas, Docentes, Preceptores."""
from __future__ import annotations


def test_criar_area_e_nome_duplicado(client):
    r = client.post("/areas", json={"nome": "Área Teste ZZZ", "carga_exigida": 40, "fase": "9_10"})
    assert r.status_code == 201, r.text
    assert r.json()["nome"] == "Área Teste ZZZ"
    # nome duplicado → 409
    r2 = client.post("/areas", json={"nome": "Área Teste ZZZ", "carga_exigida": 40})
    assert r2.status_code == 409


def test_area_carga_deve_ser_positiva(client):
    r = client.post("/areas", json={"nome": "Área Carga 0", "carga_exigida": 0})
    assert r.status_code == 422  # pydantic gt=0


def test_pre_requisito_unico(client):
    # O seed já tem Audiologia I como pré-requisito → criar outra pré-requisito falha.
    r = client.post("/areas", json={
        "nome": "Outra PreReq", "carga_exigida": 30, "fase": "7", "pre_requisito": True,
    })
    assert r.status_code == 409


def test_sub_area_nao_pode_ser_composta(client):
    # área 7 (Audiologia II) é composta (container) no seed.
    r = client.post("/areas", json={
        "nome": "Sub Composta Inválida", "carga_exigida": 10,
        "area_mae_id": 7, "composta": True,
    })
    assert r.status_code == 400


def test_docente_crud_soft_delete(client):
    r = client.post("/docentes", json={"nome": "Prof. Teste Único", "email": "t@ufcspa.edu.br"})
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    # soft-delete → ativo=false, sem apagar
    r2 = client.delete(f"/docentes/{did}")
    assert r2.status_code == 200
    assert r2.json()["ativo"] is False
    assert client.get(f"/docentes/{did}").status_code == 200


def test_preceptor_email_obrigatorio(client):
    r = client.post("/preceptores", json={"nome": "Preceptor Sem Email"})
    assert r.status_code == 422  # email obrigatório (AR-1)
    r2 = client.post("/preceptores", json={"nome": "Preceptor OK", "email": "p@ex.com"})
    assert r2.status_code == 201, r2.text
