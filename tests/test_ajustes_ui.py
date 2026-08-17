"""Ajustes de UI/bugs (Ajustes no sistem.pdf) — comportamentos-chave."""
from __future__ import annotations

from datetime import time

from sqlalchemy import select

from app.models.catalogo import Area
from app.models.enums import DiaSemana
from app.services.motor import escala
import tests.factories as f


BOOT_UI = {"HX-Current-URL": "http://test/ui/bootstrap"}


def test_item1_salvar_area_com_subarea_vira_composta(client, db_session):
    """Item 1: sub_nome/sub_carga no Salvar principal cria a sub-área e a área vira composta
    (antes eram descartados; a flag composta não persistia)."""
    db = db_session
    ar = f.area(db, nome="Área Composta Teste", carga=60)
    r = client.put(f"/ui/areas/{ar.id}", data={
        "nome": "Área Composta Teste", "carga_exigida": 60, "fase": "9_10",
        "sub_nome": "Sub Alfa", "sub_carga": 30,
    })
    assert r.status_code == 200
    db.refresh(ar)
    assert ar.composta is True
    subs = db.scalars(select(Area).where(Area.area_mae_id == ar.id)).all()
    assert any(s.nome == "Sub Alfa" and s.carga_exigida == 30 for s in subs)


def test_item5_ch_do_encontro_somada(db_session):
    """Item 5: a coluna 'Em andamento' soma as HORAS POR ENCONTRO (não a carga total)."""
    db = db_session
    c = f.ciclo(db)
    ar1 = f.area(db, carga=120)                 # N grande → onda 1 em andamento hoje
    ar2 = f.area(db, carga=160)
    # encontro de 4,5h (8:00–12:30) + encontro de 4,0h (8:00–12:00) = 8,5h/semana
    f.local(db, c, ar1, dia=DiaSemana.terca, hora_inicio=time(8, 0), hora_fim=time(12, 30), horas_sessao=4.5)
    f.local(db, c, ar2, dia=DiaSemana.quinta, hora_inicio=time(8, 0), hora_fim=time(12, 0), horas_sessao=4.0)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar1)
    f.matricular(db, a1, ar2)
    escala.gerar_escala(db, c)

    from app.routers.ui.alunos_op import dados_matriculados
    row = next(r for r in dados_matriculados(db) if r["id"] == a1.id)
    assert row["em_and"] == 2
    assert row["ch_em_and"] == 8.5             # 4,5 + 4,0 (horas por encontro)


def test_item6_por_aluno_inclui_aguardando_com_motivo(db_session):
    """Item 6b: aluno matriculado sem vaga aparece na aba por-aluno com situação/motivo."""
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=40)                   # sem local → ninguém consegue vaga
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)

    from app.routers.ui.estagios_dados import dados_por_aluno
    dados = dados_por_aluno(db, c)
    row = next(r for r in dados["linhas"] if r["aluno_id"] == a1.id)
    assert dados["totais"]["todos"] == len(dados["linhas"])
    aguard = [x for x in row["areas"] if x["situacao"] == "aguardando"]
    assert aguard and aguard[0]["motivo"]
    assert row["aguardando"] >= 1


def test_item9_grupos_preseleciona_area(db_session):
    """Item 9: sem área informada, pré-seleciona a 1ª (não carrega todas); expõe sem_vaga."""
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    f.local(db, c, ar, dia=DiaSemana.terca)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)

    from app.routers.ui.estagios_dados import dados_grupos
    d = dados_grupos(db, c)                     # area_sel=None → pré-seleção
    assert d["area_sel"] != "todas"
    assert len(d["areas"]) == 1                 # só a área pré-selecionada
    assert "sem_vaga" in d["areas"][0]
    # "todas" continua mostrando todas (usado pela Revisão do bootstrap, item 4)
    assert len(dados_grupos(db, c, "todas")["areas"]) >= 1


# ----------------------- Resumo de slots por (área, campo) -----------------------
def test_resumo_de_slots_separa_campos_da_mesma_area(db_session):
    """O painel "Slots ofertados" tem UMA LINHA POR (ÁREA, CAMPO), não por área.

    Campos da mesma área podem ter nº de encontros e capacidade diferentes (Voz — Coral
    com 20 encontros vs. Voz — Amb. ORL com 16): agregando por área, a linha mostrava a
    capacidade somada de todos os campos com o nº de encontros de um deles só.
    """
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, nome="Voz Teste", carga=80)
    f.local(db, c, ar, campo="Coral", numero_encontros=20, capacidade=4)
    f.local(db, c, ar, campo="Amb. ORL", numero_encontros=16, capacidade=6,
            dia=DiaSemana.quinta)

    from app.routers.ui.bootstrap import ctx_locais
    linhas = {r["campo"]: r for r in ctx_locais(db)["locais_resumo"]
              if r["nome"] == "Voz Teste"}
    assert set(linhas) == {"Coral", "Amb. ORL"}
    assert linhas["Coral"]["enc"] == "20" and linhas["Coral"]["cap"] == 4
    assert linhas["Amb. ORL"]["enc"] == "16" and linhas["Amb. ORL"]["cap"] == 6
    assert not any(r["enc_varia"] for r in linhas.values())


def test_resumo_de_slots_soma_dias_do_mesmo_campo_e_avisa_divergencia(db_session):
    """Dias do MESMO campo continuam somados (slots em paralelo); nº de encontros
    divergente entre os dias vira faixa + aviso, em vez de escolher um em silêncio."""
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, nome="Área Dois Dias", carga=80)
    f.local(db, c, ar, campo="Mesmo Campo", dia=DiaSemana.terca,
            numero_encontros=16, capacidade=3)
    f.local(db, c, ar, campo="Mesmo Campo", dia=DiaSemana.quinta,
            numero_encontros=20, capacidade=2)

    from app.routers.ui.bootstrap import ctx_locais
    linha = next(r for r in ctx_locais(db)["locais_resumo"] if r["nome"] == "Área Dois Dias")
    assert linha["n"] == 2 and linha["cap"] == 5   # 2 slots em paralelo, 3+2 vagas/leva
    assert linha["enc"] == "16–20" and linha["enc_varia"]


# ----------------------- Totais por semestre em Estágios -----------------------
def test_estagios_por_aluno_traz_total_de_cada_aba(db_session):
    """As abas Todos / 7º / 9º-10º mostram o total de alunos — e o total NÃO muda
    quando o filtro está ativo (é sempre do ciclo inteiro)."""
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    f.local(db, c, ar, capacidade=4)
    for sem in (9, 10, 7):
        f.matricular(db, f.aluno(db, c, semestre=sem), ar)
    escala.gerar_escala(db, c)

    from app.routers.ui.estagios_dados import dados_por_aluno
    todos = dados_por_aluno(db, c)
    assert todos["totais"]["7"] >= 1 and todos["totais"]["9_10"] >= 2
    assert todos["totais"]["todos"] == todos["totais"]["7"] + todos["totais"]["9_10"]
    # filtrado: as linhas encolhem, os totais das abas não
    so7 = dados_por_aluno(db, c, "7")
    assert so7["totais"] == todos["totais"]
    assert len(so7["linhas"]) == todos["totais"]["7"]


# ----------------------- Acentuação (valores de enum na tela) -----------------------
def test_enum_nunca_chega_cru_na_tela(client, db_session):
    """Valores de enum são chaves de banco sem acento ('ferias', 'terca'): a tela mostra
    o rótulo pt-BR."""
    assert "Férias" in client.get("/ui/afastamentos/form", headers=BOOT_UI).text
    local_form = client.get("/ui/locais/form", headers=BOOT_UI).text
    assert "Terça" in local_form and "Sábado" in local_form and "Manhã" in local_form
    assert "Acadêmico" in client.get("/ui/eventos/form", headers=BOOT_UI).text
