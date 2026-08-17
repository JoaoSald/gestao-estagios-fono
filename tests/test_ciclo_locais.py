"""FASE 3 · Milestone B — Ciclos (máquina de estados) e Locais/slot."""
from __future__ import annotations

import math


def test_estado_e_ciclo_ativo(client):
    r = client.get("/ciclos/estado")
    assert r.status_code == 200
    assert r.json()["estado"] == "em_andamento"  # seed
    assert client.get("/ciclos/ativo").status_code == 200


def test_abrir_ciclo_com_ativo_falha(client):
    r = client.post("/ciclos", json={"data_inicio": "2027-03-01", "data_fim": "2027-12-01"})
    assert r.status_code == 409  # já há ciclo ativo


def test_ciclo_datas_invalidas(client):
    r = client.post("/ciclos", json={"data_inicio": "2027-12-01", "data_fim": "2027-03-01"})
    assert r.status_code == 422  # data_fim <= data_inicio


def test_local_em_area_composta_falha(client):
    # área 7 (Audiologia II) é composta → não pode ter local.
    r = client.post("/locais", json={
        "area_id": 7, "campo": "Campo X", "dia_semana": "segunda", "turno": "manha",
        "hora_inicio": "08:00", "hora_fim": "12:00", "capacidade": 4,
        "carga_horaria": 40, "horas_sessao": 4,
    })
    assert r.status_code == 400


def test_local_numero_encontros_derivado(client):
    # área 2 (Motricidade) é leaf 9_10. carga 120 / 4h = 30 encontros.
    r = client.post("/locais", json={
        "area_id": 2, "campo": "Campo Teste NE", "dia_semana": "quarta", "turno": "tarde",
        "hora_inicio": "13:00", "hora_fim": "17:00", "capacidade": 3,
        "carga_horaria": 120, "horas_sessao": 4,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["numero_encontros"] == math.ceil(120 / 4) == 30
    assert body["docente_id"] is None  # slot nasce sem docente (AR-7)


def test_config_campo_preceptor_polimorfico(client):
    r = client.post("/locais", json={
        "area_id": 2, "campo": "Campo Config", "dia_semana": "sexta", "turno": "manha",
        "hora_inicio": "08:00", "hora_fim": "11:00", "capacidade": 2,
        "carga_horaria": 30, "horas_sessao": 3,
    })
    lid = r.json()["id"]
    # docente do catálogo (1) + preceptor externo (1)
    r2 = client.patch(f"/locais/{lid}/campo", json={
        "docente_id": 1, "preceptor_tipo": "externo", "preceptor_id": 1,
    })
    assert r2.status_code == 200, r2.text
    assert r2.json()["docente_id"] == 1
    assert r2.json()["preceptor_tipo"] == "externo"


def test_config_campo_preceptor_incoerente(client):
    r = client.post("/locais", json={
        "area_id": 2, "campo": "Campo Incoerente", "dia_semana": "terca", "turno": "tarde",
        "hora_inicio": "14:00", "hora_fim": "17:00", "capacidade": 2,
        "carga_horaria": 30, "horas_sessao": 3,
    })
    lid = r.json()["id"]
    # só preceptor_id sem tipo → 422
    r2 = client.patch(f"/locais/{lid}/campo", json={"preceptor_id": 1})
    assert r2.status_code == 422
