"""Smoke da camada de apresentação (FASE 5) — TestClient + savepoint (não toca o banco)."""
from __future__ import annotations

import tests.factories as f
from app.models.enums import PerfilUsuario


def test_login_redireciona_sem_sessao(cliente_anonimo):
    r = cliente_anonimo.get("/ui/painel", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_login_por_senha_abre_sessao_e_painel(cliente_anonimo, db_session):
    u = f.usuario(db_session, PerfilUsuario.coordenacao)
    r = cliente_anonimo.post("/login", data={"email": u.email, "senha": "senha1234"},
                             follow_redirects=False)
    assert r.status_code == 303 and "sessao" in r.headers.get("set-cookie", "")
    p = cliente_anonimo.get("/ui/painel")
    assert p.status_code == 200 and "Painel de Operação" in p.text and 'class="sidebar"' in p.text


def test_login_com_senha_errada_reexibe_o_form_com_erro(cliente_anonimo, db_session):
    """Reexibe a MESMA tela (não redireciona): redirecionar perderia a mensagem e a
    comissão não saberia se errou a senha ou se o sistema caiu."""
    u = f.usuario(db_session, PerfilUsuario.coordenacao)
    r = cliente_anonimo.post("/login", data={"email": u.email, "senha": "errada12"},
                             follow_redirects=False)
    assert r.status_code == 401 and "login-split" in r.text
    assert "inválidos" in r.text and "sessao" not in r.headers.get("set-cookie", "")


def test_paginas_de_cadastro_abrem(client):
    for r in ["alunos", "docentes", "preceptores", "afastamentos", "locais", "eventos"]:
        pg = client.get(f"/ui/{r}")
        assert pg.status_code == 200
        # eventos agora é lista agrupada por ano/mês (item 19), sem tabela genérica
        assert ("Novo evento" in pg.text) if r == "eventos" else ('class="tbl"' in pg.text)
        form = client.get(f"/ui/{r}/form")
        assert form.status_code == 200 and "modal-backdrop" in form.text


def test_criar_docente_via_htmx(client):
    r = client.post("/ui/docentes", data={"nome": "Docente UI Teste", "email": "z@ufcspa.edu.br", "ativo": "on"})
    assert r.status_code == 200
    assert "fechar-modal" in r.headers.get("HX-Trigger", "")
    assert "Docente UI Teste" in r.text  # linha nova na tabela


def test_docente_duplicado_reexibe_form_com_erro(client):
    client.post("/ui/docentes", data={"nome": "Dup UI", "email": "a@a.com"})
    r = client.post("/ui/docentes", data={"nome": "Dup UI", "email": "b@b.com"})
    assert r.status_code == 200
    assert r.headers.get("HX-Retarget") == "#modal-root"
    assert "field-err" in r.text and "Já existe" in r.text


def test_busca_ao_vivo_filtra(client):
    r = client.get("/ui/docentes/linhas", params={"q": "zzz-nao-existe"})
    assert r.status_code == 200 and "data-nofilter" in r.text  # estado vazio


def test_estagios_e_so_visualizacao_3_abas(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    f.local(db_session, c, ar, capacidade=4)
    al = f.aluno(db_session, c, nome="Aluno Board UI")
    f.matricular(db_session, al, ar)
    from app.services.motor import escala as motor
    motor.gerar_escala(db_session, c)  # gerar é fora da tela (bootstrap/remanejar)

    pg = client.get("/ui/estagios")
    assert pg.status_code == 200 and "Estágios" in pg.text
    assert "segmented" in pg.text  # 3 abas
    assert "Gerar escala" not in pg.text  # NÃO gera aqui (só visualiza)
    assert "area-pill" in pg.text and "Aluno Board UI" in pg.text  # por aluno, com cor de área

    # aba grupos
    g = client.get("/ui/estagios/conteudo?vista=grupos")
    assert g.status_code == 200
    # aba por campo (calendário)
    cp = client.get("/ui/estagios/conteudo?vista=campo")
    assert cp.status_code == 200 and "cal-grid" in cp.text


def _sem_ciclo_ativo(db):
    """Encerra qualquer ciclo ativo do seed (revertido no teardown do savepoint)."""
    from sqlalchemy import select
    from app.models.ciclo import Ciclo
    from app.models.enums import StatusCiclo
    for c in db.scalars(select(Ciclo).where(Ciclo.status.in_([StatusCiclo.rascunho, StatusCiclo.em_andamento]))):
        c.status = StatusCiclo.encerrado
    db.flush()


def test_welcome_hero_e_modal(client, db_session):
    _sem_ciclo_ativo(db_session)
    r = client.get("/ui/bem-vindo")
    assert r.status_code == 200
    assert "Nenhum ciclo ativo" in r.text  # hero (não mais form inline)
    assert 'hx-get="/ui/ciclos/abrir-modal"' in r.text  # botão abre modal
    assert 'name="data_inicio"' not in r.text  # as datas saíram do hero (foram pro modal)
    # o modal traz o formulário de datas
    m = client.get("/ui/ciclos/abrir-modal")
    assert m.status_code == 200 and "modal-backdrop" in m.text
    assert 'name="data_inicio"' in m.text and 'name="data_fim"' in m.text
    assert "Criar e iniciar bootstrap" in m.text


def test_welcome_abrir_ciclo_redireciona_bootstrap(client, db_session):
    _sem_ciclo_ativo(db_session)
    r = client.post("/ui/ciclos/abrir",
                    data={"data_inicio": "2027-03-01", "data_fim": "2027-12-10"})
    assert r.status_code == 204 and r.headers.get("HX-Redirect") == "/ui/bootstrap"


def test_welcome_abrir_ciclo_datas_invalidas_reexibe_modal(client, db_session):
    r = client.post("/ui/ciclos/abrir",
                    data={"data_inicio": "2027-12-10", "data_fim": "2027-03-01"})
    assert r.status_code == 200 and "modal-backdrop" in r.text and "field-err" in r.text


def test_estagios_mover_e_remover_por_campo(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    f.local(db_session, c, ar, capacidade=2, campo="Campo A")
    f.local(db_session, c, ar, capacidade=2, campo="Campo B")
    al = f.aluno(db_session, c, nome="Mover Aluno")
    f.matricular(db_session, al, ar)
    from app.services.motor import escala as motor
    motor.gerar_escala(db_session, c)

    from sqlalchemy import select
    from app.models.escala import Alocacao
    from app.routers.ui.estagios_dados import destinos_mover_campo, grupo_do_aluno_no_local
    aloc = db_session.scalars(select(Alocacao).where(Alocacao.aluno_id == al.id)).first()
    assert aloc is not None

    # modal de mover lista o OUTRO local da área
    m = client.get(f"/ui/estagios/mover-campo-modal?aloc={aloc.id}")
    assert m.status_code == 200 and "modal-backdrop" in m.text
    assert "Campo A" in m.text or "Campo B" in m.text

    # mover de fato → conteúdo re-renderiza e fecha o modal
    go = grupo_do_aluno_no_local(db_session, c, aloc.local_id)[al.id]
    gd = destinos_mover_campo(db_session, c, al.id, go)["destinos"][0]["grupo_id"]
    r = client.post("/ui/estagios/mover", data={
        "aluno_id": al.id, "grupo_origem": go, "grupo_destino": gd, "vista": "campo", "local": aloc.local_id})
    assert r.status_code == 200 and "fechar-modal" in r.headers.get("HX-Trigger", "")


def test_estagios_remover_libera_vaga(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    f.local(db_session, c, ar, capacidade=2, campo="Campo Solo")
    al = f.aluno(db_session, c, nome="Remover Aluno")
    f.matricular(db_session, al, ar)
    from app.services.motor import escala as motor
    motor.gerar_escala(db_session, c)
    from sqlalchemy import select
    from app.models.escala import Alocacao
    from app.models.enums import StatusAlocacao
    from app.routers.ui.estagios_dados import grupo_do_aluno_no_local
    aloc = db_session.scalars(select(Alocacao).where(Alocacao.aluno_id == al.id)).first()
    gid = grupo_do_aluno_no_local(db_session, c, aloc.local_id)[al.id]
    r = client.post("/ui/estagios/remover", data={
        "aluno_id": al.id, "grupo_id": gid, "vista": "campo", "local": aloc.local_id})
    assert r.status_code == 200 and "fechar-modal" in r.headers.get("HX-Trigger", "")
    ativa = db_session.scalars(select(Alocacao).where(
        Alocacao.aluno_id == al.id, Alocacao.status == StatusAlocacao.ativa)).first()
    assert ativa is None  # vaga liberada


def test_estagios_mover_onda_modal_na_aba_grupos(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    lc = f.local(db_session, c, ar, capacidade=1, campo="Campo Ondas")
    a1 = f.aluno(db_session, c, nome="Onda Um", ordenamento=1)
    a2 = f.aluno(db_session, c, nome="Onda Dois", ordenamento=2)
    f.matricular(db_session, a1, ar)
    f.matricular(db_session, a2, ar)
    from app.services.motor import escala as motor
    motor.gerar_escala(db_session, c)
    # com capacidade 1 e 2 alunos, há 2 ondas no mesmo local → botão/modal de mover-onda
    m = client.get(f"/ui/estagios/mover-onda-modal?aluno={a1.id}&local={lc.id}&area={ar.id}")
    assert m.status_code == 200 and "modal-backdrop" in m.text and "Grupo" in m.text


def test_bootstrap_subareas_inline(client, db_session):
    from sqlalchemy import select
    from app.models.catalogo import Area
    from app.models.enums import FaseArea
    mae = Area(nome="Composta Fidelidade", carga_exigida=40, fase=FaseArea._9_10, composta=True, cor="#14b8a6")
    db_session.add(mae)
    db_session.flush()
    # o form da composta traz a seção de sub-áreas inline
    fform = client.get(f"/ui/areas/{mae.id}/form")
    assert fform.status_code == 200 and "Sub-áreas" in fform.text
    # adicionar sub-área re-renderiza o modal já com ela
    r = client.post(f"/ui/areas/{mae.id}/subareas", data={"sub_nome": "SubFidelidade Adulto", "sub_carga": 20})
    assert r.status_code == 200 and "SubFidelidade Adulto" in r.text
    subs = db_session.scalars(select(Area).where(Area.area_mae_id == mae.id)).all()
    assert len(subs) == 1
    # remover
    r2 = client.delete(f"/ui/areas/{subs[0].id}/subarea")
    assert r2.status_code == 200
    assert db_session.scalars(select(Area).where(Area.area_mae_id == mae.id)).all() == []


def test_bootstrap_overlay_gerando_so_no_request(client, db_session):
    from app.core.templates import templates as _t
    # o overlay "Gerando…" é htmx-indicator (invisível até o request) — não some do DOM,
    # mas fica escondido; o botão o aciona via hx-indicator.
    html = _t.get_template("partials/revisao.html").render(
        resumo={"alunos": 0, "docentes": 0, "locais": 0}, avisos=[], relatorio=None)
    assert 'id="gen-stage"' in html and 'class="htmx-indicator"' in html
    assert "Gerando a escala" in html and 'hx-indicator="#gen-stage"' in html


def test_form_area_sem_cor_composta_com_subareas(client, db_session):
    fform = client.get("/ui/areas/form")
    assert fform.status_code == 200 and "Sub-áreas" in fform.text
    # o form do versao_2 não tem seletor de cor, checkbox composta nem select de área-mãe
    assert 'name="cor"' not in fform.text
    assert 'name="composta"' not in fform.text
    assert 'name="area_mae_id"' not in fform.text


def test_aluno_detalhe_mostra_curriculo_completo(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16, nome="Área Cursada Fidelidade")
    al = f.aluno(db_session, c, nome="Currículo Aluno")
    f.matricular(db_session, al, ar)
    r = client.get(f"/ui/alunos/{al.id}")
    assert r.status_code == 200
    assert "Área Cursada Fidelidade" in r.text          # a área cursada
    assert "Não faz neste ciclo" in r.text              # as demais do currículo aparecem


def _checkboxes_area(html: str) -> dict[int, dict]:
    """{area_id: {'marcado': bool, 'desabilitado': bool}} a partir dos <input name="area">."""
    import re
    saida = {}
    for tag in re.findall(r'<input type="checkbox" name="area"[^>]*>', html):
        aid = int(re.search(r'value="(\d+)"', tag).group(1))
        saida[aid] = {"marcado": "checked" in tag, "desabilitado": "disabled" in tag}
    return saida


def test_form_aluno_semestre_prefill_e_gate_por_fase(client, db_session):
    """Gate por fase (§4) + pré-marcação: aluno NOVO já vem com todas as áreas da sua fase
    marcadas (a comissão só desmarca as exceções); o que não é da fase vem desabilitado."""
    from sqlalchemy import select
    from app.models.catalogo import Area
    prereq = db_session.scalars(select(Area).where(Area.pre_requisito.is_(True))).first()
    assert prereq is not None  # seed: Audiologia I
    # botão do mini-ciclo abre o form com semestre 7 pré-preenchido
    m7 = client.get("/ui/alunos/form?semestre=7")
    assert m7.status_code == 200 and 'value="7"' in m7.text
    m9 = client.get("/ui/alunos/form?semestre=9")
    assert 'value="9"' in m9.text

    # 7º novo → SÓ o pré-requisito (Audiologia I) marcado e habilitado; as demais desabilitadas
    c7 = _checkboxes_area(client.get("/ui/alunos/matriculas-check?semestre=7").text)
    assert c7[prereq.id] == {"marcado": True, "desabilitado": False}
    outras7 = [v for aid, v in c7.items() if aid != prereq.id]
    assert outras7 and all(v["desabilitado"] and not v["marcado"] for v in outras7)

    # 9/10 novo → o inverso: pré-requisito desabilitado, TODAS as demais pré-marcadas
    c9 = _checkboxes_area(client.get("/ui/alunos/matriculas-check?semestre=9").text)
    assert c9[prereq.id] == {"marcado": False, "desabilitado": True}
    outras9 = [v for aid, v in c9.items() if aid != prereq.id]
    assert outras9 and all(v["marcado"] and not v["desabilitado"] for v in outras9)


def test_login_split_fiel(cliente_anonimo):
    r = cliente_anonimo.get("/login")
    assert r.status_code == 200 and "login-split" in r.text and "Entrar com Google" in r.text
    # sem credencial de exemplo chumbada no HTML (ia para produção como senha na tela)
    assert "senha123" not in r.text and "coordenacao@ufcspa.edu.br" not in r.text


def test_alunos_por_fase(client, db_session):
    r = client.get("/ui/alunos")
    assert r.status_code == 200
    assert "7º semestre" in r.text and "9º/10º semestre" in r.text


def test_locais_com_cor_de_area(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    f.local(db_session, c, ar)
    r = client.get("/ui/locais")
    assert r.status_code == 200 and "area-pill" in r.text and "indisponibilidade" in r.text.lower()


def test_eventos_tem_aba_calendario(client, db_session):
    c = f.ciclo(db_session)
    f.evento(db_session, c, __import__("datetime").date(2026, 6, 1), __import__("datetime").date(2026, 6, 1), nome="Feriado X")
    r = client.get("/ui/eventos/conteudo?vista=calendario")
    assert r.status_code == 200 and "cal-grid" in r.text


def test_painel_acoes_abrem_modal(client):
    r = client.get("/ui/painel")
    assert r.status_code == 200 and '/ui/alunos/form' in r.text  # ação rápida abre modal


def test_painel_fila_sem_vaga_nao_oferece_remanejar(client, db_session):
    """Fila sem vaga é alerta informativo (§9): o CTA é abrir oferta (§8.4), não remanejar
    — o Remanejar só reajusta o que a infraestrutura mudou (§7.1)."""
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    f.local(db, c, ar)
    alocado = f.aluno(db, c, nome="Aluno Alocado UI")
    f.matricular(db, alocado, ar)
    aluno = f.aluno(db, c, nome="Aluno Na Fila", ordenamento=2)
    f.matricular(db, aluno, f.area(db, carga=40))   # área sem local → aguardando vaga
    from app.services.motor import escala as motor
    motor.gerar_escala(db, c)                       # molde materializado: só a fila sobra

    r = client.get("/ui/painel")
    assert r.status_code == 200
    assert "aguardando vaga" in r.text
    # o banner da fila não promete remanejo; o CTA leva a cadastrar oferta
    assert "banner-remanejo info" in r.text
    assert "/ui/locais/form" in r.text
    # e, sem pendência de infra, o modal do Remanejar não tem o que aplicar
    assert not c.escala_desatualizada
    m = client.get("/ui/remanejar-modal")
    assert m.status_code == 200 and "Nada a revisar" in m.text


def test_remanejar_e_modal(client):
    r = client.get("/ui/remanejar-modal")
    assert r.status_code == 200 and "modal-backdrop" in r.text


def test_historico_e_remanejar_abrem(client):
    h = client.get("/ui/historico")
    assert h.status_code == 200 and "Histórico" in h.text
    r = client.get("/ui/remanejar")
    assert r.status_code == 200 and "Remanejar" in r.text


def test_alunos_operacional_tabela_rica_e_ofertas(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    f.local(db_session, c, ar, capacidade=4)
    al = f.aluno(db_session, c, nome="Op Aluno")
    f.matricular(db_session, al, ar)
    from app.services.motor import escala as motor
    motor.gerar_escala(db_session, c)

    r = client.get("/ui/alunos")
    assert r.status_code == 200
    assert "Prioridade" in r.text and "da carga" in r.text  # tabela rica (evidencia_5)
    assert "Matriculados" in r.text and "Ofertas" in r.text  # abas
    o = client.get("/ui/alunos/conteudo?vista=ofertas")
    assert o.status_code == 200 and "Situação" in o.text


def test_ofertas_card_com_alocados_e_fila(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    f.local(db_session, c, ar, capacidade=1, campo="Campo Único")
    a1 = f.aluno(db_session, c, nome="Alocado Um", ordenamento=1)
    a2 = f.aluno(db_session, c, nome="Fila Dois", ordenamento=2)
    f.matricular(db_session, a1, ar)
    f.matricular(db_session, a2, ar)
    from app.services.motor import escala as motor
    motor.gerar_escala(db_session, c)
    # linha de oferta é clicável → abre o card com previsão
    o = client.get("/ui/alunos/conteudo?vista=ofertas")
    assert o.status_code == 200 and 'hx-get="/ui/alunos/oferta-card?area=' in o.text
    card = client.get(f"/ui/alunos/oferta-card?area={ar.id}")
    assert card.status_code == 200 and "modal-backdrop" in card.text
    assert "Alocados" in card.text and "Fila de espera" in card.text
    assert "Previsão de início" in card.text


def test_detalhe_do_aluno(client, db_session):
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    f.local(db_session, c, ar, capacidade=4)
    al = f.aluno(db_session, c, nome="Aluno Detalhe UI")
    f.matricular(db_session, al, ar)
    r = client.get(f"/ui/alunos/{al.id}")
    assert r.status_code == 200
    assert "Aluno Detalhe UI" in r.text and "Áreas do currículo" in r.text


def test_estaticos_tem_cache_bust(client):
    """CSS/JS saem com `?v=<mtime>` — sem isso, mudança de estilo não chega ao navegador.

    Regressão real (28/07/2026): uma tela chegou ao usuário com markup NOVO e CSS
    ANTIGO — grade empilhada em coluna, chips sem estilo — porque o `StaticFiles` não
    manda `Cache-Control` e o HTMX troca só o HTML, nunca re-busca a folha de estilo da
    página já aberta. Nenhum erro no servidor; só a tela quebrada. Custou um diagnóstico
    inteiro errado (parecia problema de desenho).
    """
    import re
    r = client.get("/login")
    assert r.status_code == 200
    for arquivo in ("css/styles.css", "js/app.js"):
        m = re.search(rf'/static/{re.escape(arquivo)}\?v=(\d+)', r.text)
        assert m, f"{arquivo} sem cache-bust — CSS/JS novo não chegaria ao navegador"
        assert int(m.group(1)) > 0
    # e a URL versionada tem que servir o arquivo de verdade
    css = client.get(re.search(r'/static/css/styles\.css\?v=\d+', r.text).group(0))
    assert css.status_code == 200 and ".cal-grid" in css.text
