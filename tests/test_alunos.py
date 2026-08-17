"""FASE 3 · Milestones C+D — Alunos, Matrículas, Restrições, Desmatrícula."""
from __future__ import annotations

from datetime import date

from app.models.enums import StatusAlocacao, StatusMatricula, StatusSessao
from app.models.escala import Alocacao, Sessao

AREA_MOTRICIDADE = 2   # leaf, fase 9_10 (seed)
AREA_AUDIOLOGIA_I = 1  # pré-requisito, fase 7 (seed)


def _novo_aluno(client, matricula="20269999", semestre=9, prioridade=False, matriculas=None):
    return client.post("/alunos", json={
        "nome": "Aluno Teste", "matricula": matricula, "semestre": semestre,
        "prioridade": prioridade, "matriculas": matriculas or [],
        "locais_bloqueados": [],
    })


def test_criar_aluno_email_default_e_matricula_unica(client):
    r = _novo_aluno(client, matricula="20269001")
    assert r.status_code == 201, r.text
    assert r.json()["aluno"]["email"] == "20269001@aluno.ufcspa.edu.br"
    # matrícula duplicada no ciclo → 409
    r2 = _novo_aluno(client, matricula="20269001")
    assert r2.status_code == 409


def test_matricula_fora_da_fase_bloqueia(client):
    a = _novo_aluno(client, matricula="20269002", semestre=9).json()["aluno"]["id"]
    # tentar matricular em_andamento na Audiologia I (fase 7) → 400
    r = client.put(f"/alunos/{a}/matriculas", json={
        "itens": [{"area_id": AREA_AUDIOLOGIA_I, "status": "em_andamento"}]
    })
    assert r.status_code == 400


def test_pre_requisito_aviso_nao_bloqueia(client):
    a = _novo_aluno(client, matricula="20269003", semestre=9).json()["aluno"]["id"]
    r = client.put(f"/alunos/{a}/matriculas", json={
        "itens": [{"area_id": AREA_MOTRICIDADE, "status": "em_andamento"}]
    })
    assert r.status_code == 200, r.text  # NÃO bloqueia
    body = r.json()
    assert any("Audiologia I" in a for a in body["avisos"])  # só avisa
    assert body["pre_requisito_ok"] is False


def test_carry_forward_preserva_concluida(client):
    a = _novo_aluno(client, matricula="20269004", semestre=9).json()["aluno"]["id"]
    # carry-forward: Audiologia I concluída (fase 7) + Motricidade em andamento
    client.put(f"/alunos/{a}/matriculas", json={"itens": [
        {"area_id": AREA_AUDIOLOGIA_I, "status": "concluida"},
        {"area_id": AREA_MOTRICIDADE, "status": "em_andamento"},
    ]})
    # re-sincroniza só com Motricidade → a concluída sobrevive (não é desmarcável)
    r = client.put(f"/alunos/{a}/matriculas", json={
        "itens": [{"area_id": AREA_MOTRICIDADE, "status": "em_andamento"}]
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pre_requisito_ok"] is True
    areas = {m["area_id"]: m["status"] for m in body["matriculas"]}
    assert areas.get(AREA_AUDIOLOGIA_I) == "concluida"


def test_restricao_sem_local_liberado_bloqueia(client):
    a = _novo_aluno(client, matricula="20269005", semestre=9, matriculas=[
        {"area_id": AREA_MOTRICIDADE, "status": "em_andamento"},
    ]).json()["aluno"]["id"]
    locais_moto = [l["id"] for l in client.get("/locais").json()
                   if l["area_id"] == AREA_MOTRICIDADE and l["ativo"]]
    assert locais_moto, "seed deve ter local de Motricidade"
    # bloquear TODOS os locais da área matriculada → 400
    r = client.put(f"/alunos/{a}/restricoes", json={"locais_bloqueados": locais_moto})
    assert r.status_code == 400


def test_estado_aguardando_sem_alocacao(client):
    a = _novo_aluno(client, matricula="20269006", semestre=9, matriculas=[
        {"area_id": AREA_MOTRICIDADE, "status": "em_andamento"},
    ]).json()["aluno"]["id"]
    detalhe = client.get(f"/alunos/{a}").json()
    moto = next(m for m in detalhe["matriculas"] if m["area_id"] == AREA_MOTRICIDADE)
    assert moto["estado"] == "aguardando"  # em_andamento sem alocação ativa
    assert detalhe["resumo"]["aguardando"] >= 1


def test_interromper_area_cancela_futuro_preserva_passado(client, db_session):
    a = _novo_aluno(client, matricula="20269007", semestre=9, matriculas=[
        {"area_id": AREA_MOTRICIDADE, "status": "em_andamento"},
    ]).json()["aluno"]["id"]
    # pega a matrícula e um local da área; insere alocação + sessões (passada e futura)
    detalhe = client.get(f"/alunos/{a}").json()
    local_id = next(l["id"] for l in client.get("/locais").json()
                    if l["area_id"] == AREA_MOTRICIDADE and l["ativo"])
    from app.models.aluno import Matricula
    mat = db_session.query(Matricula).filter_by(aluno_id=a, area_id=AREA_MOTRICIDADE).one()
    aloc = Alocacao(aluno_id=a, local_id=local_id, matricula_id=mat.id,
                    data_inicio=date(2026, 6, 1), data_fim_prevista=date(2026, 12, 1),
                    status=StatusAlocacao.ativa)
    db_session.add(aloc)
    db_session.flush()
    s_pass = Sessao(alocacao_id=aloc.id, data=date(2026, 7, 1), status=StatusSessao.prevista)
    s_fut = Sessao(alocacao_id=aloc.id, data=date(2026, 12, 1), status=StatusSessao.prevista)
    db_session.add_all([s_pass, s_fut])
    db_session.commit()

    r = client.post(f"/alunos/{a}/interromper/{AREA_MOTRICIDADE}", json={"motivo": "afastamento médico"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "interrompida"
    assert r.json()["motivo_interrupcao"] == "afastamento médico"

    db_session.refresh(aloc)
    db_session.refresh(s_pass)
    db_session.refresh(s_fut)
    assert aloc.status == StatusAlocacao.cancelada       # vaga liberada
    assert s_fut.status == StatusSessao.cancelada        # futura cancelada
    assert s_pass.status == StatusSessao.prevista        # passada preservada


def test_interromper_sem_matricula_em_andamento_404(client):
    a = _novo_aluno(client, matricula="20269008", semestre=9).json()["aluno"]["id"]
    r = client.post(f"/alunos/{a}/interromper/{AREA_MOTRICIDADE}", json={})
    assert r.status_code == 404


def test_edicao_em_operacao_enfileira_remanejo(client, db_session):
    """afterSave: cadastrar em ciclo em_andamento marca escala desatualizada + enfileira."""
    from app.models.ciclo import Ciclo
    from app.models.operacao import FilaRemanejo
    ciclo = db_session.query(Ciclo).filter_by(status="em_andamento").one()
    antes = db_session.query(FilaRemanejo).filter_by(ciclo_id=ciclo.id).count()
    _novo_aluno(client, matricula="20269009", semestre=9)
    db_session.refresh(ciclo)
    depois = db_session.query(FilaRemanejo).filter_by(ciclo_id=ciclo.id).count()
    assert ciclo.escala_desatualizada is True
    assert depois == antes + 1
