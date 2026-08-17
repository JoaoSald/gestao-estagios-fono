"""Validação dos ajustes de bootstrap/ciclo-ativo (itens 1–19).

Cada teste valida o "critério de aceite" do item correspondente. Roda no fixture
transacional (rollback) — não persiste no banco real.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models.catalogo import Area, Docente
from app.models.local import Local

BOOT = {"HX-Current-URL": "http://test/ui/bootstrap"}


def _login(client):
    client.post("/login")


# ------------------------- Áreas (1ª seção do passo "Áreas e Locais") -------------------------
def test_item3_editar_area_persiste_e_reflete(client, db_session):
    """Item 3: editar área no bootstrap persiste e re-renderiza a etapa 3a."""
    _login(client)
    a = db_session.scalars(select(Area).where(Area.composta.is_(False), Area.area_mae_id.is_(None))).first()
    novo = a.nome + " XPTO"
    r = client.put(f"/ui/areas/{a.id}", data={"nome": novo, "carga_exigida": "77", "fase": a.fase.value}, headers=BOOT)
    assert r.status_code == 200
    assert "fechar-modal" in r.headers.get("HX-Trigger", "")
    # corpo = seção 3a re-renderizada, já com o novo nome
    assert novo in r.text and "<h3>Áreas</h3>" in r.text
    db_session.expire_all()
    assert db_session.get(Area, a.id).carga_exigida == 77


def test_item3_form_area_no_bootstrap_aponta_para_bs_areas(client, db_session):
    """Item 3 (raiz): no bootstrap o modal tem alvo existente (#bs-areas), senão o htmx nem envia."""
    _login(client)
    a = db_session.scalars(select(Area)).first()
    r = client.get(f"/ui/areas/{a.id}/form", headers=BOOT)
    assert 'hx-target="#bs-areas"' in r.text


def test_item1_2_subarea_botao_salvar_e_reflete(client, db_session):
    """Itens 1 e 2: botão 'Salvar sub-área' ao lado dos campos + dispara recarregar-areas."""
    _login(client)
    mae = db_session.scalars(select(Area).where(Area.composta.is_(True))).first()
    r_form = client.get(f"/ui/areas/{mae.id}/form", headers=BOOT)
    assert "Salvar sub-área" in r_form.text and 'id="btn-add-sub"' in r_form.text
    r = client.post(f"/ui/areas/{mae.id}/subareas",
                    data={"sub_nome": "SubTeste ZZ", "sub_carga": "15"}, headers=BOOT)
    assert "recarregar-areas" in r.headers.get("HX-Trigger", "")
    assert "SubTeste ZZ" in r.text  # aparece na lista do modal imediatamente
    db_session.expire_all()
    subs = db_session.scalars(select(Area).where(Area.area_mae_id == mae.id, Area.nome == "SubTeste ZZ")).all()
    assert len(subs) == 1


def test_item2_endpoint_passo3a_lista_areas(client):
    _login(client)
    r = client.get("/ui/bootstrap/passo3a")
    assert r.status_code == 200 and "<h3>Áreas</h3>" in r.text


# ----------------------------- Etapa 3b — Locais -----------------------------
def test_item4_form_local_sem_campo_horas(client, db_session):
    """Item 4: form de local não tem mais o campo horas/encontro (horas_sessao)."""
    _login(client)
    r = client.get("/ui/locais/form", headers=BOOT)
    assert 'name="horas_sessao"' not in r.text
    assert 'name="hora_inicio"' in r.text and 'name="hora_fim"' in r.text


def test_item4_7_criar_local_deriva_horas_e_grava_docente(client, db_session):
    """Item 4: horas_sessao = fim − início. Item 7: docente responsável gravado."""
    _login(client)
    area = db_session.scalars(select(Area).where(Area.composta.is_(False))).first()
    doc = db_session.scalars(select(Docente).where(Docente.ativo.is_(True))).first()
    r = client.post("/ui/locais", headers=BOOT, data={
        "area_id": str(area.id), "docente_id": str(doc.id), "campo": "CAMPO TESTE ZZ",
        "dia_semana": "segunda", "turno": "manha", "hora_inicio": "08:00", "hora_fim": "11:30",
        "capacidade": "3", "numero_encontros": "10",
    })
    assert r.status_code == 200, r.text
    assert "Locais (slots)" in r.text  # devolveu a seção de locais (tabela + slots)
    db_session.expire_all()
    l = db_session.scalars(select(Local).where(Local.campo == "CAMPO TESTE ZZ")).first()
    assert l is not None
    assert l.horas_sessao == 3.5  # 11:30 − 08:00
    assert l.docente_id == doc.id


def test_item5_criar_local_atualiza_slots(client, db_session):
    """Item 5: após criar local, o painel de slots reflete (resumo re-renderizado)."""
    _login(client)
    area = db_session.scalars(select(Area).where(Area.composta.is_(False))).first()
    r = client.post("/ui/locais", headers=BOOT, data={
        "area_id": str(area.id), "campo": "SLOT REFRESH ZZ", "dia_semana": "quarta",
        "turno": "tarde", "hora_inicio": "13:30", "hora_fim": "17:30",
        "capacidade": "2", "numero_encontros": "16",
    })
    assert "Slots ofertados no ciclo" in r.text


def test_item6_ordem_tabela_antes_slots(client):
    """Item 6: na seção de locais a tabela vem antes do painel de slots."""
    _login(client)
    r = client.get("/ui/bootstrap/passo3b")
    assert r.text.index("tbody-locais") < r.text.index("Slots ofertados no ciclo")


def test_item7_form_local_tem_select_docente(client):
    _login(client)
    r = client.get("/ui/locais/form", headers=BOOT)
    assert 'name="docente_id"' in r.text and "Docente responsável" in r.text


# ----------------------------- Renderização direta de partials -----------------------------
def _render(nome: str, ctx: dict) -> str:
    from app.core.templates import templates
    return templates.env.get_template(nome).render(**ctx)


# ----------------------------- Etapa 5 / 7 -----------------------------
def test_item8_sem_botao_novo_preceptor():
    """Item 8: a etapa 5 (bootstrap.html) não tem mais 'Novo preceptor'."""
    from app.core.templates import TEMPLATES_DIR
    src = (TEMPLATES_DIR / "bootstrap.html").read_text(encoding="utf-8")
    assert "Novo preceptor" not in src


def test_item9_mini_ciclo_so_audiologia_i(client, db_session):
    """Item 9: form do 7º semestre só mostra locais da área pré-requisito."""
    _login(client)
    r7 = client.get("/ui/alunos/form?semestre=7", headers=BOOT)
    r9 = client.get("/ui/alunos/form?semestre=9", headers=BOOT)
    n7 = r7.text.count('name="disp"')
    n9 = r9.text.count('name="disp"')
    assert 0 < n7 < n9  # mini-ciclo vê só um subconjunto (Audiologia I)
    # todas as pills de área da seção de disponibilidade do 7º são da área pré-requisito
    from app.models.catalogo import Area
    prereq = db_session.scalars(select(Area).where(Area.pre_requisito.is_(True))).first()
    assert prereq.nome in r7.text


def test_item12_9_10_disp_toda_marcada(client):
    """Item 12: aluno novo do 9º/10º inicia com todos os checkboxes de disponibilidade marcados."""
    _login(client)
    r = client.get("/ui/alunos/form?semestre=9", headers=BOOT)
    import re
    checks = re.findall(r'name="disp"[^>]*>', r.text)
    assert len(checks) > 0 and all("checked" in c for c in checks)


def test_item11_todo_modal_de_cadastro_e_estatico(client):
    """Item 11: nenhum formulário fecha ao clicar fora — só no X, no Cancelar ou salvando.

    Era só o de aluno. O mesmo bug seguia em docente, preceptor, evento, afastamento, área e
    local: um clique de raspão no backdrop apagava o que a pessoa tinha digitado. Como o
    padrão do macro virou estático, este teste cobre TODOS os recursos — o próximo form
    nasce protegido, e se alguém reintroduzir o `estatico=false` o teste cai.
    """
    from app.routers.ui.cadastros import VALIDOS
    _login(client)
    for recurso in sorted(VALIDOS):
        r = client.get(f"/ui/{recurso}/form", headers=BOOT)
        assert r.status_code == 200, recurso
        assert "modal-backdrop" in r.text, recurso
        assert "data-static" in r.text, f"{recurso}: fecha ao clicar fora"
        # e continua havendo as duas saídas explícitas
        assert r.text.count("data-close") >= 2, recurso


def test_modal_de_abrir_ciclo_tambem_e_estatico(client, db_session):
    """Mesmo motivo: é formulário (datas do ciclo), e não usa o macro."""
    from app.models.ciclo import Ciclo
    from app.models.enums import StatusCiclo
    _login(client)
    for c in db_session.scalars(select(Ciclo)).all():
        c.status = StatusCiclo.encerrado       # sem ciclo ativo → a tela oferece abrir
    db_session.flush()
    r = client.get("/ui/ciclos/abrir-modal")
    assert r.status_code == 200
    assert "modal-backdrop" in r.text and "data-static" in r.text


def test_item10_13_14_lista_alunos():
    """Itens 10 (contador), 13 (busca) e 14 (scroll) na lista de alunos do bootstrap."""
    rows7 = [{"id": 1, "nome": "Ana Souza", "matricula": "1", "email": None,
              "semestre": 7, "prioridade": False, "em_and": 1, "conc": 0}]
    html = _render("partials/alunos_conteudo.html", {"fase7": rows7, "fase910": []})
    assert "aluno(s)" in html                    # item 10: contador
    assert 'oninput="filtrarLista' in html        # item 13: busca
    assert "max-height:26rem" in html             # item 14: altura fixa + scroll
    assert 'data-nome="ana souza"' in html        # linha filtrável


def test_item16_montagem_separa_por_semestre():
    """Item 16: montagem agrupa áreas por semestre (7º vs 9º/10º)."""
    areas = [
        {"nome": "Audiologia I", "cor": "#14b8a6", "fase": "7", "slots": []},
        {"nome": "Voz", "cor": "#f97316", "fase": "9_10", "slots": []},
    ]
    html = _render("partials/montagem.html", {"montagem_areas": areas, "banco": []})
    assert "7º semestre — mini-ciclo" in html
    assert "9º/10º semestre — demais estágios" in html


def test_item17_revisao_tem_filtro_de_locais():
    """Item 17: etapa 10 tem seletor de locais e caixas marcadas por data-filtro-local."""
    grupos = {"areas": [{"id": 1, "nome": "Voz", "cor": "#f97316", "locais": [
        {"local_id": 5, "campo": "Clínica X", "unidade": None, "dia": "segunda", "turno": "manha",
         "hora_inicio": __import__("datetime").time(8, 0), "hora_fim": __import__("datetime").time(12, 0),
         "cap": 4, "numero_encontros": 10, "ondas": []}]}]}
    rel = {"alocados": 1, "alunos_ok": 1, "alunos_parcial": 0, "aguardando": [], "avisos": []}
    html = _render("partials/revisao.html", {"relatorio": rel, "grupos": grupos})
    assert "filtrarGruposLocal" in html
    assert 'data-filtro-local="5"' in html
    assert "Todos os locais" in html


def test_item18_busca_alunos_operacao():
    """Item 18: listagem de alunos da operação tem busca por nome."""
    matric = [{"id": 1, "nome": "Bruno Lima", "matricula": "2", "semestre": 9, "email": None,
               "ordenamento": 1, "pct_carga": 50, "concluidas": 1, "total_areas": 2,
               "em_and": 1, "aguardando": 0, "risco": False}]
    html = _render("partials/alunos_op_conteudo.html",
                   {"vista": "matriculados", "fase": "todos", "matriculados": matric})
    assert 'oninput="filtrarLista' in html
    assert 'data-nome="bruno lima"' in html


# ----------------------------- Etapa de Eventos -----------------------------
def test_item15_importar_feriados_br_rs(db_session):
    """Item 15: feriados nacionais (BR) + estaduais (RS) do período viram eventos."""
    from app.models.calendario import Evento
    from app.models.enums import OrigemEvento, TipoEvento
    from app.services import feriados as fs
    from app.services.common import get_ciclo_ativo
    ciclo = get_ciclo_ativo(db_session)
    n = fs.importar_feriados(db_session, ciclo)
    assert n >= 8
    evs = db_session.scalars(select(Evento).where(Evento.ciclo_id == ciclo.id)).all()
    nomes = [e.nome for e in evs]
    assert any("Gaúcho" in x for x in nomes)          # feriado ESTADUAL do RS
    assert any("Independência" in x for x in nomes)   # feriado NACIONAL
    for e in evs:
        assert ciclo.data_inicio <= e.data_inicio <= ciclo.data_fim  # dentro do período
        assert e.tipo == TipoEvento.feriado and e.origem == OrigemEvento.api_feriados
        assert e.bloqueia_estagio is True
    # idempotente: reimportar não duplica
    assert fs.importar_feriados(db_session, ciclo) == 0


def test_item15_feriados_do_periodo_filtra_intervalo():
    from datetime import date
    from app.services.feriados import feriados_do_periodo
    fer = feriados_do_periodo(date(2026, 3, 2), date(2026, 12, 11))
    datas = [d for d, _ in fer]
    assert date(2026, 9, 20) in datas       # Dia do Gaúcho (RS)
    assert date(2026, 1, 1) not in datas     # fora do período (antes do início)


# ----------------------------- Etapa 19 — Eventos (ano → mês → lista) -----------------------------
EVP = {"HX-Current-URL": "http://test/ui/eventos"}


def test_item19_eventos_agrupados_por_ano_e_mes(client):
    """Item 19: a vista de eventos agrupa por ano → mês em formato de lista."""
    _login(client)
    client.post("/ui/eventos", headers=EVP, data={
        "nome": "Jornada de Fono", "tipo": "academico", "data_inicio": "2026-05-21", "data_fim": "2026-05-22"})
    r = client.post("/ui/eventos", headers=EVP, data={
        "nome": "Reunião Colegiado", "tipo": "reuniao", "data_inicio": "2026-06-04"})
    # a resposta do cadastro já é a lista agrupada (não a tabela genérica)
    assert "fechar-modal" in r.headers.get("HX-Trigger", "")
    assert "2026" in r.text and "Maio" in r.text and "Junho" in r.text
    # página de lista mostra os dois, na ordem cronológica (Maio antes de Junho)
    r2 = client.get("/ui/eventos?vista=lista")
    assert "Jornada de Fono" in r2.text and "Reunião Colegiado" in r2.text
    assert r2.text.index("Maio") < r2.text.index("Junho")


def test_item19_form_evento_na_pagina_aponta_para_conteudo(client):
    """Item 19: na página de eventos o modal aponta para #eventos-conteudo (alvo existente)."""
    _login(client)
    r = client.get("/ui/eventos/form", headers=EVP)
    assert 'hx-target="#eventos-conteudo"' in r.text


def test_item19_remover_evento_atualiza_lista(client, db_session):
    """Item 19: remover um evento re-renderiza a lista agrupada."""
    _login(client)
    client.post("/ui/eventos", headers=EVP, data={
        "nome": "Evento Para Remover", "tipo": "academico", "data_inicio": "2026-07-10"})
    from app.models.calendario import Evento
    ev = db_session.scalars(select(Evento).where(Evento.nome == "Evento Para Remover")).first()
    r = client.delete(f"/ui/eventos/{ev.id}", headers=EVP)
    assert r.status_code == 200
    assert "Evento Para Remover" not in r.text  # sumiu da lista re-renderizada
