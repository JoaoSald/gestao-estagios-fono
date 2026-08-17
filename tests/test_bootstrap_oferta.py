"""Wizard reordenado + validador de locais e análise da grade na UI.

A ordem dos passos passou a ser dirigida por `core/passos.py` (Eventos e Afastamentos ANTES
de Áreas e Locais), o que é o que permite validar a oferta no próprio passo de cadastro.
Estes testes travam essa ordem e o comportamento do painel.
"""
from __future__ import annotations

from datetime import time

from markupsafe import escape

from app.core import passos
from app.models.ciclo import Ciclo
from app.models.enums import DiaSemana, StatusCiclo, Turno
from app.services.motor import calendario
import tests.factories as f


def _rascunho(db) -> Ciclo:
    """Coloca o ciclo do seed em rascunho para abrir o wizard."""
    c = f.ciclo(db)
    c.status = StatusCiclo.rascunho
    c.passo_bootstrap = 1
    db.flush()
    return c


# ============================ Ordem dos passos ============================
def test_ordem_dos_passos_coloca_calendario_antes_da_oferta():
    """O validador só diz a verdade se eventos/afastamentos vierem antes dos locais."""
    ordem = [k for k, _ in passos.PASSOS]
    assert ordem.index("eventos") < ordem.index("oferta")
    assert ordem.index("afastamentos") < ordem.index("oferta")
    # amarras de dependência do wizard
    assert ordem.index("docentes") < ordem.index("afastamentos")
    assert ordem.index("preceptores") < ordem.index("afastamentos")
    assert ordem.index("oferta") < ordem.index("alunos")      # blocklist do aluno usa locais
    assert ordem[-1] == "revisao"
    assert passos.chave(passos.numero("oferta")) == "oferta"


def test_clamp_do_passo_fora_da_faixa():
    assert passos.chave(0) == passos.PASSOS[0][0]
    assert passos.chave(999) == passos.PASSOS[-1][0]


def test_wizard_abre_cada_passo_na_ordem_nova(client, db_session):
    ciclo = _rascunho(db_session)
    for n, (_chave, rotulo) in enumerate(passos.PASSOS, start=1):
        ciclo.passo_bootstrap = n
        db_session.flush()
        r = client.get("/ui/bootstrap")
        assert r.status_code == 200, (n, rotulo)
        assert f"passo {n} de {len(passos.PASSOS)}" in r.text
        assert str(escape(rotulo)) in r.text   # o stepper mostra todos os rótulos


def test_passo_da_oferta_traz_areas_locais_validador_e_analise(client, db_session):
    ciclo = _rascunho(db_session)
    ciclo.passo_bootstrap = passos.numero("oferta")
    f.local(db_session, ciclo, f.area(db_session, carga=16), numero_encontros=4)
    db_session.flush()

    r = client.get("/ui/bootstrap")
    assert r.status_code == 200
    assert "Áreas" in r.text and "Locais (slots)" in r.text
    assert 'id="validador-locais"' in r.text
    assert "Locais validados" in r.text      # oferta sã → confirmação, sem tabela
    assert "Quando cada estágio acontece" in r.text
    assert "tl-bloco" in r.text              # régua de horários desenhada


# ============================ Validador ============================
def test_validador_lista_so_o_local_com_problema(client, db_session):
    """Local saudável não entra na lista — e não ganha sugestão de nº de encontros."""
    ciclo = _rascunho(db_session)
    quebrado = f.local(db_session, ciclo, f.area(db_session, carga=40),
                       numero_encontros=999, campo="Campo Quebrado")
    # CH do slot casa com a exigida pela área (4 × 4h = 16h) → nada a resolver
    saudavel = f.local(db_session, ciclo, f.area(db_session, carga=16),
                       horas_sessao=4.0, numero_encontros=4, campo="Campo Saudável")

    r = client.get("/ui/bootstrap/validacao")
    assert r.status_code == 200
    assert "Locais a resolver" in r.text
    assert "Campo Quebrado" in r.text and "não fecha" in r.text
    assert "Campo Saudável" not in r.text
    assert "↧ usar" in r.text
    assert f'/ui/bootstrap/validacao/local/{quebrado.id}/encontros' in r.text
    assert f'/ui/bootstrap/validacao/local/{saudavel.id}/encontros' not in r.text


def test_validador_sem_problema_vira_uma_linha_de_confirmacao(client, db_session):
    ciclo = _rascunho(db_session)
    f.local(db_session, ciclo, f.area(db_session, carga=16), numero_encontros=4)

    r = client.get("/ui/bootstrap/validacao")
    assert r.status_code == 200
    assert "Locais validados" in r.text
    assert "Locais a resolver" not in r.text
    assert "↧ usar" not in r.text
    assert "<table" not in r.text          # confirmação, não tabela


def test_ajustar_encontros_no_validador_devolve_o_grupo(client, db_session):
    """O conserto do caso do print: 40 encontros → 37 (o que cabe) sem voltar passos."""
    ciclo = _rascunho(db_session)
    area = f.area(db_session, carga=40)
    local = f.local(db_session, ciclo, area, dia=DiaSemana.terca, numero_encontros=999)
    viaveis = len(calendario.ocorrencias_dia(DiaSemana.terca, ciclo.data_inicio, ciclo.data_fim))

    r = client.post(f"/ui/bootstrap/validacao/local/{local.id}/encontros",
                    data={"numero_encontros": str(viaveis)})
    assert r.status_code == 200
    assert "toast" in r.headers.get("HX-Trigger", "")
    assert local.numero_encontros == viaveis
    # o slot voltou a fechar grupo → não aparece mais como falha
    assert "não fecha" not in r.text


def test_encontros_invalido_no_validador_nao_quebra(client, db_session):
    ciclo = _rascunho(db_session)
    local = f.local(db_session, ciclo, f.area(db_session, carga=16), numero_encontros=4)

    r = client.post(f"/ui/bootstrap/validacao/local/{local.id}/encontros",
                    data={"numero_encontros": "abc"})
    assert r.status_code == 200
    assert "error" in r.headers.get("HX-Trigger", "")
    assert local.numero_encontros == 4          # nada foi gravado


def test_toggle_passagem_pelo_validador(client, db_session):
    ciclo = _rascunho(db_session)
    local = f.local(db_session, ciclo, f.area(db_session, carga=16), numero_encontros=4)
    assert local.passagem_grupo is False

    r = client.post(f"/ui/bootstrap/validacao/local/{local.id}/passagem")
    assert r.status_code == 200 and local.passagem_grupo is True


# ============================ Tabela de locais ============================
def test_coluna_passagem_na_tabela_de_locais(client, db_session):
    ciclo = f.ciclo(db_session)
    local = f.local(db_session, ciclo, f.area(db_session, carga=16), numero_encontros=4)

    pg = client.get("/ui/locais")
    assert pg.status_code == 200
    assert "Passagem" in pg.text
    assert f'/ui/locais/{local.id}/passagem' in pg.text

    r = client.post(f"/ui/locais/{local.id}/passagem")
    assert r.status_code == 200 and local.passagem_grupo is True
    r2 = client.post(f"/ui/locais/{local.id}/passagem")
    assert r2.status_code == 200 and local.passagem_grupo is False


def test_form_do_local_tem_preceptor(client, db_session):
    f.ciclo(db_session)
    r = client.get("/ui/locais/form")
    assert r.status_code == 200
    assert 'name="preceptor"' in r.text and 'name="docente_id"' in r.text


def test_criar_local_com_preceptor_docente(client, db_session):
    f.ciclo(db_session)
    area = f.area(db_session, carga=16)
    doc = f.docente(db_session)
    prec = f.docente(db_session)

    r = client.post("/ui/locais", data={
        "area_id": str(area.id), "campo": "Campo Com Preceptor", "unidade": "",
        "dia_semana": DiaSemana.quarta.value, "turno": Turno.manha.value,
        "hora_inicio": "08:00", "hora_fim": "12:00",
        "capacidade": "4", "numero_encontros": "4",
        "docente_id": str(doc.id), "preceptor": f"docente:{prec.id}",
    })
    assert r.status_code == 200, r.text[:400]

    from app.services import local as local_service
    novo = next(l for l in local_service.listar(db_session) if l.campo == "Campo Com Preceptor")
    assert novo.docente_id == doc.id
    assert novo.preceptor_tipo == "docente" and novo.preceptor_id == prec.id


# ============================ Demanda / revisão ============================
def test_passo_alunos_nao_mostra_vagas_por_area(client, db_session):
    """Oferta × demanda mora só na Revisão — no cadastro de alunos confunde."""
    ciclo = _rascunho(db_session)
    ciclo.passo_bootstrap = passos.numero("alunos")
    area = f.area(db_session, carga=16)
    f.local(db_session, ciclo, area, capacidade=2, numero_encontros=4)
    for _ in range(4):
        f.matricular(db_session, f.aluno(db_session, ciclo), area)
    db_session.flush()

    r = client.get("/ui/bootstrap")
    assert r.status_code == 200
    assert "Vagas × matrículas por área" not in r.text


def test_revisao_mostra_vagas_por_area(client, db_session):
    ciclo = _rascunho(db_session)
    ciclo.passo_bootstrap = passos.numero("revisao")
    area = f.area(db_session, carga=16)
    f.local(db_session, ciclo, area, capacidade=2, numero_encontros=4)
    for _ in range(4):
        f.matricular(db_session, f.aluno(db_session, ciclo), area)
    db_session.flush()

    r = client.get("/ui/bootstrap")
    assert r.status_code == 200
    assert "Vagas × matrículas por área" in r.text


def test_aviso_de_demanda_so_quando_falta_vaga_no_ciclo(client, db_session):
    """Demanda maior que UMA leva é normal (a turma se distribui pelas ondas do ano);
    só vira aviso quando não sobra vaga no ciclo inteiro."""
    from app.routers.ui.montagem_dados import montar_revisao
    ciclo = _rascunho(db_session)
    area = f.area(db_session, carga=16, nome="Área Cabe No Ciclo")
    local = f.local(db_session, ciclo, area, capacidade=2, numero_encontros=4)

    from app.services import analise_grade
    sv = {s.local.id: s for s in
          analise_grade.validar_locais(db_session, ciclo)["slots"]}[local.id]
    vagas = sv.ondas * 2
    assert sv.ondas > 1, "cenário precisa de várias ondas para valer o teste"

    # demanda maior que uma leva (2), mas dentro das vagas do ciclo → SEM aviso
    for _ in range(vagas):
        f.matricular(db_session, f.aluno(db_session, ciclo), area)
    db_session.flush()
    avisos = montar_revisao(db_session, ciclo)["avisos"]
    assert not any("Área Cabe No Ciclo" in a for a in avisos)

    # um a mais do que o ciclo comporta → aviso, dizendo quantos ficam de fora
    f.matricular(db_session, f.aluno(db_session, ciclo), area)
    db_session.flush()
    avisos = montar_revisao(db_session, ciclo)["avisos"]
    alvo = [a for a in avisos if "Área Cabe No Ciclo" in a]
    assert len(alvo) == 1
    assert "1 matrícula(s) sem vaga no ciclo" in alvo[0]


def test_revisao_nao_repete_a_tabela_do_validador_mas_avisa_no_botao(client, db_session):
    """A Revisão não duplica o validador: a tabela é o instrumento do passo "Áreas e
    Locais". Aqui sobra só o número — o botão avisa em vez de prometer."""
    ciclo = _rascunho(db_session)
    ciclo.passo_bootstrap = passos.numero("revisao")
    quebrado = f.local(db_session, ciclo, f.area(db_session, carga=40), numero_encontros=999)
    db_session.flush()

    r = client.get("/ui/bootstrap")
    assert r.status_code == 200
    assert "Locais a resolver" not in r.text
    assert 'id="validador-locais"' not in r.text
    # com local que não fecha, o botão avisa em vez de prometer
    assert "Gerar escala mesmo assim" in r.text
    assert "local(is) não vão gerar grupo" in r.text

    # resolvido o problema, o botão volta a prometer
    quebrado.ativo = False
    db_session.flush()
    r2 = client.get("/ui/bootstrap")
    assert "Gerar escala mesmo assim" not in r2.text
    assert "Gerar escala" in r2.text


def test_revisao_pos_geracao_pinta_locais_perdidos_por_area(client, db_session):
    ciclo = _rascunho(db_session)
    area = f.area(db_session, carga=40, nome="Área Sem Vaga UI")
    f.local(db_session, ciclo, area, numero_encontros=999, campo="Campo Perdido")
    al = f.aluno(db_session, ciclo)
    f.matricular(db_session, al, area)
    db_session.flush()

    r = client.post("/ui/bootstrap/gerar")
    assert r.status_code == 200
    assert "Locais que não geraram grupo" in r.text
    assert "Campo Perdido" in r.text
    assert "area-pill" in r.text          # pintado com a cor da área, não prosa cinza
    assert "cabe até" in r.text           # sugestão de nº de encontros


# ============================ "Todos fecham o ciclo?" ============================
def _anual(db, c, local):
    """Faz o slot fechar UM grupo que cobre o ciclo inteiro.

    É a patologia real da oferta: quando a carga da área consome todas as datas do dia,
    não existe onda 2 — é aritmética. Aí aquele dia da semana fica ocupado o ano todo e o
    mecanismo de ondas (que resolveria "8 alunos em 4 vagas") não tem como ajudar.
    """
    ctx = calendario.carregar_contexto(db, c)
    local.numero_encontros = len(ctx.datas_viaveis(local, c))
    db.flush()
    return local
def test_fecha_o_ciclo_ve_conflito_que_a_soma_de_vagas_nao_ve(db_session):
    """Vaga é contagem; fechar o ciclo é combinação — e a diferença é o relógio.

    Cenário: 2 áreas, cada uma com vaga de sobra, mas ambas ofertadas só na terça de
    manhã. `capacidade_vs_demanda` diz saldo POSITIVO nas duas; nenhum aluno consegue
    fazer as duas no ano.
    """
    from app.services import analise_grade
    db = db_session
    c = _rascunho(db)
    a1 = f.area(db, nome="Área Conflito A", carga=16)
    a2 = f.area(db, nome="Área Conflito B", carga=16)
    _anual(db, c, f.local(db, c, a1, dia=DiaSemana.terca, turno=Turno.manha, capacidade=4))
    _anual(db, c, f.local(db, c, a2, dia=DiaSemana.terca, turno=Turno.manha, capacidade=4))
    al = f.aluno(db, c, nome="Aluno Conflito")
    f.matricular(db, al, a1)
    f.matricular(db, al, a2)

    val = analise_grade.validar_locais(db, c)
    linhas = {r["nome"]: r for r in analise_grade.capacidade_vs_demanda(db, c, val["slots"])}
    assert linhas["Área Conflito A"]["saldo"] > 0        # a soma diz "sobra vaga"
    assert linhas["Área Conflito B"]["saldo"] > 0

    v = analise_grade.fecha_o_ciclo(db, c)
    meu = next(l for l in v["linhas"] if l.aluno_id == al.id)
    assert meu.matriculadas == 2 and meu.fecham == 1     # ...mas só 1 cabe
    assert not meu.completo
    assert v["incompletos"] >= 1


def test_fecha_o_ciclo_aponta_o_dia_que_destrava(db_session):
    """A resposta acionável para os professores: qual dia abrir."""
    from app.core.rotulos import rotulo
    from app.services import analise_grade
    db = db_session
    c = _rascunho(db)
    a1 = f.area(db, nome="Área Trava A", carga=16)
    a2 = f.area(db, nome="Área Trava B", carga=16)
    _anual(db, c, f.local(db, c, a1, dia=DiaSemana.terca, turno=Turno.manha))
    _anual(db, c, f.local(db, c, a2, dia=DiaSemana.terca, turno=Turno.manha))
    # um 3º local em outro dia dá ao ciclo um dia "útil" alternativo a testar
    f.local(db, c, f.area(db, nome="Área Solta", carga=16),
            dia=DiaSemana.quinta, turno=Turno.manha, numero_encontros=4)
    al = f.aluno(db, c, nome="Aluno Trava")
    f.matricular(db, al, a1)
    f.matricular(db, al, a2)

    v = analise_grade.fecha_o_ciclo(db, c)
    assert v["incompletos"] == 1
    dias = {d.dia for d in v["destravas"]}
    assert rotulo(DiaSemana.quinta) in dias             # abrir na quinta resolve
    # e nunca sugere dia em que o ciclo não oferta estágio nenhum
    assert rotulo(DiaSemana.domingo) not in dias
    assert rotulo(DiaSemana.sabado) not in dias

    # A destrava é ACRESCENTAR um dia, não mudar o do local existente — e a tabela precisa
    # do dia atual para poder dizer isso (era a dúvida do print: "mover ou criar outro?").
    d = v["destravas"][0]
    assert d.dias_atuais == [rotulo(DiaSemana.terca)]
    assert d.dia not in d.dias_atuais

    # Agrupado por ÁREA: os vários dias que servem são ALTERNATIVAS (escolha uma), não uma
    # lista de providências. Cru, o painel repetia 8 linhas com o mesmo nº de alunos.
    ag = v["destravas_agrupadas"]
    assert len(ag) <= len({x.area_nome for x in v["destravas"]})
    g = ag[0]
    assert g["dia"] not in g["alternativas"] and g["dia"] not in g["dias_atuais"]
    # todos os dias da área cabem na linha: o recomendado + as alternativas
    da_area = {x.dia for x in v["destravas"] if x.area_nome == g["area_nome"]}
    assert da_area == {g["dia"], *g["alternativas"]}


def test_sem_dia_novo_para_testar_o_painel_diz_isso_em_vez_de_tabela_vazia(client, db_session):
    """O vazio do print: aviso mandando "abrir a área em outro dia" e nenhuma sugestão.

    Quando a área da fila já é ofertada em TODOS os dias úteis não há dia novo a medir — a
    tela caía num "nenhum dia livre resolve" genérico que soava como contradição. Agora ela
    nomeia a área saturada, lista os dias que ela já tem e dá o remédio que sobra.
    """
    from app.services import analise_grade
    db = db_session
    uteis = (DiaSemana.segunda, DiaSemana.terca, DiaSemana.quarta,
             DiaSemana.quinta, DiaSemana.sexta)
    c = _rascunho(db)
    # 6 áreas anuais, cada uma ofertada em TODOS os dias úteis, no mesmo turno. O relógio do
    # aluno só cabe 5 (uma por manhã), então uma sobra na fila por CONFLITO — e não existe
    # dia novo para clonar em área nenhuma. Qual delas sobra é escolha do motor; o que o
    # teste exige é que a área que sobrou apareça como saturada.
    areas = [f.area(db, nome=f"Área Relógio {i}", carga=16) for i in range(6)]
    for ar in areas:
        for dia in uteis:
            _anual(db, c, f.local(db, c, ar, dia=dia, turno=Turno.manha, capacidade=5))
    al = f.aluno(db, c, nome="Aluno Saturado", ordenamento=950)
    for ar in areas:
        f.matricular(db, al, ar)

    v = analise_grade.fecha_o_ciclo(db, c)
    real = v["real"]
    assert real["completos"] < real["total"]
    assert real["fila_agrupada"]["conflito"] >= 1       # há vaga; o problema é o dia
    assert v["sugestoes"] == [] and v["escada"] == []   # não havia dia novo a medir
    # a área saturada NÃO sai da busca: sem dia a testar ainda resta a hipótese de vaga, e
    # ela é medida — aqui sem efeito (o problema é o relógio do aluno, não assento), então
    # cai em `descartadas` em vez de virar sugestão. Antes a área saía da busca inteira e a
    # tela mandava "mais capacidade" sem nunca ter medido se capacidade resolvia.
    assert all(s["tipo"] == "capacidade" for s in v["descartadas"])
    assert v["areas_saturadas"], "a área da fila já é ofertada em todos os dias"
    sat = v["areas_saturadas"][0]
    assert sat["area_nome"].startswith("Área Relógio")
    assert len(sat["dias_atuais"]) == len(uteis)

    # e a tela escreve isso, em vez do "nenhum dia livre resolve" solto
    c.passo_bootstrap = passos.numero("revisao")
    db.flush()
    r = client.get("/ui/bootstrap/fecha-ciclo")
    assert r.status_code == 200
    assert "Não há dia novo para testar" in r.text
    assert sat["area_nome"] in r.text
    # e não promete sugestões que não existem
    assert "as sugestões abaixo" not in r.text


def test_botao_de_verificacao_aparece_antes_de_gerar(client, db_session):
    c = _rascunho(db_session)
    c.passo_bootstrap = passos.numero("revisao")
    db_session.flush()
    r = client.get("/ui/bootstrap")
    assert r.status_code == 200
    assert "Verificar se todos conseguem fazer o ciclo" in r.text
    assert "/ui/bootstrap/fecha-ciclo" in r.text
    # o cálculo NÃO roda no render do wizard (é caro) — só quando pedido
    assert "Todos conseguem fazer o ciclo?" not in r.text

    p = client.get("/ui/bootstrap/fecha-ciclo")
    assert p.status_code == 200
    assert "Todos conseguem fazer o ciclo?" in p.text


def test_fecha_o_ciclo_mostra_o_teto_global_da_oferta(db_session):
    """O teto que diz quantos alunos a oferta sustenta — vagas do ciclo × matrículas.

    Vagas contam as ONDAS (2 por grupo × N ondas no ano), então "mais matrículas que
    vagas iniciais" não é estouro. O que importa é o total do ciclo. O seed já traz
    locais, então o que se afere é o DELTA de capacidade do slot novo.
    """
    from app.services import analise_grade
    from app.services.motor import molde
    db = db_session
    c = _rascunho(db)
    antes = analise_grade.fecha_o_ciclo(db, c)["vagas_ciclo"]

    ar = f.area(db, nome="Área Teto", carga=16)
    local = f.local(db, c, ar, dia=DiaSemana.terca, capacidade=2, numero_encontros=4)
    alunos = [f.aluno(db, c, nome=f"Aluno Teto {i}", ordenamento=500 + i) for i in range(3)]
    for al in alunos:
        f.matricular(db, al, ar)

    ctx = calendario.carregar_contexto(db, c)
    do_slot = sum(cx.capacidade for cx in molde.caixas_do_local(local, c, ctx))
    assert do_slot > local.capacidade, "capacidade do CICLO é por onda, não de um grupo só"

    v = analise_grade.fecha_o_ciclo(db, c)
    assert v["vagas_ciclo"] == antes + do_slot
    assert v["demanda_total"] == 3                 # 3 alunos × 1 área
    assert v["saldo_ciclo"] == v["vagas_ciclo"] - 3
    # com folga, os 3 fecham o ciclo — as ondas os distribuem no ano
    assert v["incompletos"] == 0
    assert v["sustenta"] >= 3


def test_sugere_vaga_a_mais_por_grupo_quando_a_fila_e_de_grupo_cheio(db_session):
    """Nem toda fila se resolve com dia novo — grupo cheio pede VAGA, e isso é medido.

    Dois alunos, uma área anual num único grupo de 1 vaga: o segundo fica na fila por
    capacidade. Abrir a área em outro dia não é a providência (o dia não é o problema);
    +1 aluno por grupo é. Antes o motor de sugestões só sabia propor dia, então esta fila
    não tinha resposta nenhuma na tela.
    """
    from app.services import analise_grade
    db = db_session
    c = _rascunho(db)
    ar = f.area(db, nome="Área Vaga Curta", carga=16)
    _anual(db, c, f.local(db, c, ar, dia=DiaSemana.terca, turno=Turno.manha, capacidade=1))
    for i, nome in enumerate(("Aluno Vaga 1", "Aluno Vaga 2")):
        f.matricular(db, f.aluno(db, c, nome=nome, ordenamento=970 + i), ar)

    v = analise_grade.fecha_o_ciclo(db, c)
    assert v["real"]["fila_agrupada"]["capacidade"] >= 1
    cap = [s for s in v["sugestoes"] if s["tipo"] == "capacidade"]
    assert cap, "fila por grupo cheio tem de receber a hipótese de vaga"
    s = cap[0]
    assert s["area_nome"] == "Área Vaga Curta"
    assert s["delta"] >= 1 and s["ganho"] > 0 and s["libera"] > 0
    # a linha diz o que a comissão vai mexer: quantos grupos e de quanto para quanto
    assert s["grupos"] == 1 and s["capacidades"] == [1]
    assert s["vagas_extra"] == s["delta"] * s["grupos"]
    # e o rótulo da escada descreve a vaga, não um dia
    assert "por grupo" in v["escada"][0]["mudancas"][0]


def test_escada_combina_mudancas_que_sozinhas_nao_valem_nada():
    """O caso que o filtro antigo tornava invisível: só a COMBINAÇÃO paga.

    A escada partia de `uteis` (ganho>0 ou libera>0), então uma mudança que sozinha não move
    nada e só paga junto com outra era descartada ANTES de haver com quem combinar — e num
    ciclo em que TODAS as hipóteses davam +0 sobrava uma escada de um degrau já visível na
    tabela. Agora ela parte de todas as hipóteses medidas, podando por "área ainda tem gente
    na fila".

    Simulador falso porque o que se testa é a BUSCA, não o motor: aqui, por construção,
    qualquer mudança isolada não muda nada e duas quaisquer fecham o ciclo. Montar isso com
    alunos reais exigiria uma disputa de assento de três pontas — frágil e ilegível.
    """
    from types import SimpleNamespace as NS

    from app.services.analise_grade import sugerir_dias

    def caixa(area_id, dia):
        local = NS(id=area_id, campo=f"Campo {area_id}", turno=Turno.manha,
                   hora_inicio=time(8, 0), hora_fim=time(12, 0),
                   numero_encontros=4, dia_semana=dia, capacidade=4)
        return NS(area_id=area_id, local=local, capacidade=4)

    por_area = {1: [caixa(1, DiaSemana.terca)], 2: [caixa(2, DiaSemana.terca)]}
    espera = [NS(area_id=1, tipo="conflito"), NS(area_id=2, tipo="conflito")]
    base = {"completos": 0, "total": 2, "fila": 2, "alocados": 0, "vagas": 8,
            "aguardando": espera}

    class SimFalso:
        nomes = {1: "Área Um", 2: "Área Dois"}
        rodadas = 0

        def rodar(self, hips):
            self.rodadas += 1
            if len({h.area_id for h in hips}) >= 2:      # duas áreas mexidas: fecha o ciclo
                return {"completos": 2, "total": 2, "fila": 0, "alocados": 4, "vagas": 12,
                        "aguardando": []}
            return {**base, "aguardando": list(espera)}   # uma só: não muda NADA

    r = sugerir_dias(SimFalso(), base, por_area)
    assert r["sugestoes"] == [], "por construção, nenhuma mudança isolada tem efeito"
    assert r["descartadas"], "e todas elas foram medidas"
    # ...e ainda assim a escada acha a combinação que fecha o ciclo
    assert len(r["escada"]) == 2
    assert r["escada"][-1]["completos"] == 2 and r["escada"][-1]["fila"] == 0
    assert {m.split(" também")[0].replace("+2 aluno(s) por grupo em ", "").split(" (")[0]
            for m in r["escada"][-1]["mudancas"]} == {"Área Um", "Área Dois"}


def test_simular_oferta_roda_o_motor_e_conta_conclusoes(db_session):
    """"Se eu abrir esse dia, quantos concluem?" — resposta pelo MOTOR, não por estimativa.

    Duas áreas anuais na terça travam o aluno em 1 de 2. Ofertar uma delas na quinta faz
    a simulação (que é `preencher` + `consolidar` de verdade) fechar as duas.
    """
    from app.models.enums import DiaSemana as D
    from app.services import analise_grade
    db = db_session
    c = _rascunho(db)
    a1 = f.area(db, nome="Área Sim A", carga=16)
    a2 = f.area(db, nome="Área Sim B", carga=16)
    _anual(db, c, f.local(db, c, a1, dia=D.terca, turno=Turno.manha, capacidade=4))
    _anual(db, c, f.local(db, c, a2, dia=D.terca, turno=Turno.manha, capacidade=4))
    al = f.aluno(db, c, nome="Aluno Sim", ordenamento=700)
    f.matricular(db, al, a1)
    f.matricular(db, al, a2)

    antes = analise_grade.simular_oferta(db, c, [])
    depois = analise_grade.simular_oferta(db, c, [(a2.id, D.quinta)])
    assert depois["completos"] > antes["completos"]
    assert depois["fila"] < antes["fila"]
    assert depois["vagas"] > antes["vagas"]      # o dia novo acrescenta grupos


def test_candidatos_sao_medidos_em_rodizio_entre_as_areas():
    """Quando o tempo acaba, o que fica de fora é alternativa — nunca uma área inteira.

    Medir área-a-área gastava todo o orçamento na primeira: a tela mostrava três dias da
    mesma área e calava sobre as outras cinco da fila (agrupada por área, virava UMA linha).
    """
    from app.services.analise_grade import Hipotese, _rodizio
    a = [Hipotese("dia", 10, dia=d) for d in ("seg", "qua", "sex")]
    b = [Hipotese("capacidade", 20, delta=2)]
    c = [Hipotese("dia", 30, dia=d) for d in ("qui", "sex")]
    ordem = _rodizio({10: a, 20: b, 30: c})
    assert ordem[:3] == [a[0], b[0], c[0]]        # 1ª volta: uma hipótese por área
    assert ordem[3:] == [a[1], c[1], a[2]]        # depois, as alternativas
    # e cortar em qualquer ponto da 1ª volta ainda deixa áreas distintas
    assert len({h.area_id for h in ordem[:2]}) == 2


def test_simulacao_clona_uma_copia_por_slot_nao_uma_por_dia(db_session):
    """Abrir um dia novo cadastra UM local por slot — não um por dia em que a área já existe.

    1 local = campo + dia + TURNO. A mesma sala no mesmo turno ofertada na terça E na
    quarta era clonada DUAS vezes na quinta: a simulação media o dobro da capacidade num
    slot que a comissão só consegue cadastrar uma vez, e a tela prometia um ganho que a
    providência sugerida não entregaria. Apareceu quando a linha passou a escrever o que
    cadastrar e saiu "2 locais: Manhã 08:00–12:00 U.I - SUS · Manhã 08:00–12:00 U.I - SUS".
    """
    from app.models.enums import DiaSemana as D
    from app.services import analise_grade
    from app.services.motor import molde
    db = db_session
    c = _rascunho(db)
    ar = f.area(db, nome="Área Slot Repetido", carga=16)
    for dia in (D.terca, D.quarta):
        _anual(db, c, f.local(db, c, ar, dia=dia, turno=Turno.manha,
                              campo="Mesmo Campo", capacidade=4))
    al = f.aluno(db, c, nome="Aluno Slot", ordenamento=960)
    f.matricular(db, al, ar)

    caixas = [cx for cx in molde.materializar_molde(db, c, calendario.carregar_contexto(db, c))
              if cx.area_id == ar.id]
    uma_copia = sum(cx.capacidade for cx in caixas if cx.local.dia_semana == D.terca)
    assert sum(cx.capacidade for cx in caixas) == 2 * uma_copia   # o mesmo slot em 2 dias

    antes = analise_grade.simular_oferta(db, c, [])
    depois = analise_grade.simular_oferta(db, c, [(ar.id, D.quinta)])
    assert depois["vagas"] - antes["vagas"] == uma_copia          # UMA cópia, não duas

    # e a tela descreve exatamente essa oferta: um local, não dois idênticos
    locais = analise_grade._locais_da_area(caixas)
    assert len(locais) == 1 and locais[0]["campo"] == "Mesmo Campo"
    assert locais[0]["horario"] == "08:00–12:00"


def test_painel_separa_sair_do_conflito_de_concluir(client, db_session):
    """A tabela de dias mede fim de CONFLITO; concluir depende também de vaga.

    Prometer conclusão na tabela de dias seria mentir: medido no seed, "destrava 10" pela
    forma virou "8 de 14 concluem" na simulação. O painel tem de dizer as duas coisas.
    """
    db = db_session
    c = _rascunho(db)
    a1 = f.area(db, nome="Área Painel A", carga=16)
    a2 = f.area(db, nome="Área Painel B", carga=16)
    _anual(db, c, f.local(db, c, a1, dia=DiaSemana.terca, turno=Turno.manha))
    _anual(db, c, f.local(db, c, a2, dia=DiaSemana.terca, turno=Turno.manha))
    f.local(db, c, f.area(db, nome="Área Painel Solta", carga=16),
            dia=DiaSemana.quinta, turno=Turno.manha, numero_encontros=4)
    al = f.aluno(db, c, nome="Aluno Painel", ordenamento=800)
    f.matricular(db, al, a1)
    f.matricular(db, al, a2)

    r = client.get("/ui/bootstrap/fecha-ciclo")
    assert r.status_code == 200
    assert "efeito medido com o motor" in r.text             # as sugestões vêm do motor
    # tirar da fila e concluir são colunas DIFERENTES, com a diferença escrita
    assert "Tira da fila" in r.text and "Concluem" in r.text
    assert "matrícula que passa a ter grupo" in r.text      # ≠ aluno que fecha tudo
    # a leitura por FORMA (que ignora vaga) desce para o detalhe e vem rotulada como tal —
    # antes ela era uma tabela irmã da medida, e as duas juntas é que confundiam
    assert "ainda sem contar vaga" in r.text


def test_diagnostico_do_ciclo_aparece_nos_tres_momentos(client, db_session):
    """O botão só existe DEPOIS do passo de alunos — a resposta é por aluno.

    (1) passo Áreas e Locais — NÃO tem o botão: os alunos ainda não foram cadastrados;
    (2) Revisão, antes de gerar — última chance de mudar sem refazer;
    (3) Revisão, depois de gerar — quando aparece "N aguardando" e nasce o "por quê?".
    """
    db = db_session
    c = _rascunho(db)
    ar = f.area(db, carga=16)
    f.local(db, c, ar, numero_encontros=4)
    al = f.aluno(db, c, nome="Aluno Momentos")
    f.matricular(db, al, ar)

    # (1) passo da oferta — sem o diagnóstico por aluno
    c.passo_bootstrap = passos.numero("oferta")
    db.flush()
    r = client.get("/ui/bootstrap")
    assert "/ui/bootstrap/fecha-ciclo" not in r.text
    assert "conseguem fazer o ciclo" not in r.text

    # (2) revisão antes de gerar
    c.passo_bootstrap = passos.numero("revisao")
    db.flush()
    r = client.get("/ui/bootstrap")
    assert "Verificar se todos conseguem fazer o ciclo" in r.text

    # (3) revisão depois de gerar — só quando há alerta de fechamento
    ar2 = f.area(db, nome="Área Sem Local Momentos", carga=16)
    f.matricular(db, al, ar2)                    # área sem local → cai na fila
    g = client.post("/ui/bootstrap/gerar")
    assert g.status_code == 200
    assert "aguardando" in g.text.lower()
    assert "Por que sobrou gente — e o que abrir para resolver" in g.text


# ============ A forma cabe, a disputa por assento não (o caso do print) ============
def _disputa_de_assento(db, c):
    """Oferta em que TODOS os currículos cabem pela forma e ainda assim sobra gente.

    A é ofertada na terça (2 vagas) e na quinta (1 vaga); B só na terça, no mesmo horário.
    Dois alunos cursam A e B. Pela forma cada um tem solução (A na quinta + B na terça).
    Na fila real, o 1º aluno leva a única vaga da quinta; para o 2º só resta A na terça, que
    conflita com B na terça — sobra por CONFLITO, com vaga sobrando na área.

    É exatamente o retrato que o painel mostrava como "10 de 10 fecham" e a geração
    entregava com gente na fila.
    """
    a1 = f.area(db, nome="Área Disputa A", carga=16)
    a2 = f.area(db, nome="Área Disputa B", carga=16)
    _anual(db, c, f.local(db, c, a1, dia=DiaSemana.terca, turno=Turno.manha, capacidade=2))
    _anual(db, c, f.local(db, c, a1, dia=DiaSemana.quinta, turno=Turno.manha, capacidade=1))
    _anual(db, c, f.local(db, c, a2, dia=DiaSemana.terca, turno=Turno.manha, capacidade=2))
    for i in range(2):
        al = f.aluno(db, c, nome=f"Aluno Disputa {i}", ordenamento=900 + i)
        f.matricular(db, al, a1)
        f.matricular(db, al, a2)
    return a1, a2


def test_forma_cabe_mas_simulacao_reprova_e_o_painel_lidera_pelo_real(db_session):
    """O número que a tela mostra tem de ser o mesmo que a geração vai entregar.

    A checagem por FORMA ignora capacidade de propósito (é o que separa "impossível pelo
    relógio" de "perdeu o assento"), então ela aprovava todo mundo enquanto o motor deixava
    gente na fila. Agora `real` (uma rodada do motor) vem no mesmo pacote, e a causa vem
    somada por tipo — "sem vaga" não servia como rótulo único.
    """
    from app.services import analise_grade
    db = db_session
    c = _rascunho(db)
    _disputa_de_assento(db, c)

    v = analise_grade.fecha_o_ciclo(db, c)
    assert v["incompletos"] == 0                       # pela forma, todos cabem
    assert v["destravas"] == []                        # e por isso não há o que "destravar"
    real = v["real"]
    assert real["completos"] < real["total"]           # mas a disputa por assento reprova
    assert real["fila_agrupada"]["conflito"] >= 1      # com vaga na área — é o DIA
    assert real["fila_agrupada"]["capacidade"] == 0
    assert v["gargalo"] == "conflito"


def test_sugestoes_dizem_qual_area_abrir_em_qual_dia_medindo_com_o_motor(db_session):
    """"O que eu abro?" — cada sugestão é uma rodada do motor, não uma estimativa."""
    from app.services import analise_grade
    db = db_session
    c = _rascunho(db)
    a1, a2 = _disputa_de_assento(db, c)

    v = analise_grade.fecha_o_ciclo(db, c)
    assert v["sugestoes"], "a simulação reprovou alguém, então tem de haver sugestão"
    # o remédio é tirar uma das duas áreas da terça — qual delas sobrou é escolha do motor,
    # então a sugestão pode ser sobre A ou sobre B; o que se exige é o GANHO medido.
    melhor = v["sugestoes"][0]
    assert melhor["ganho"] > 0 and melhor["libera"] > 0
    assert melhor["area_id"] in {a1.id, a2.id}
    # a sugestão é ACRESCENTAR um dia: os dias atuais viajam na linha para a tabela poder
    # dizer isso (sem eles a comissão não sabia se era para mover o local existente)
    assert melhor["dias_atuais"] and melhor["dia"] not in melhor["dias_atuais"]
    # a escada mede a combinação (não soma os ganhos individuais) e fecha o ciclo. O degrau
    # 0 ("como está hoje") NÃO é linha da escada — é `base_hoje`, a régua fora da tabela.
    assert v["escada"] and v["escada"][0]["n"] == 1
    assert v["base_hoje"]["completos"] == v["real"]["completos"]
    assert v["escada"][-1]["completos"] == v["escada"][-1]["total"]
    assert v["escada"][-1]["ganho"] == v["escada"][-1]["total"] - v["base_hoje"]["completos"]
    # e nunca sugere dia em que o ciclo não oferta estágio nenhum
    from app.core.rotulos import rotulo
    dias = {s["dia"] for s in v["sugestoes"]}
    assert rotulo(DiaSemana.domingo) not in dias and rotulo(DiaSemana.sabado) not in dias


def test_painel_nao_diz_que_todos_fecham_quando_a_simulacao_reprova(client, db_session):
    """Contradição do print: crachá "10 de 10 fecham" + "18 sem vaga" na mesma revisão."""
    db = db_session
    c = _rascunho(db)
    _disputa_de_assento(db, c)

    r = client.get("/ui/bootstrap/fecha-ciclo")
    assert r.status_code == 200
    assert "concluem" in r.text
    # o crachá agora é o número da simulação, não o da forma
    assert "de 2 concluem" in r.text
    assert "Todos os alunos conseguem concluir" not in r.text
    # a causa aparece separada, com o remédio
    assert "por <b>conflito de horário</b>" in r.text
    # e a reconciliação entre as duas contas está escrita na tela
    assert "disputa por assento" in r.text
    # e a sugestão é escrita como instrução ("abrir tal área também em tal dia"), não como
    # duas colunas soltas de área e dia — era isso que deixava a comissão sem saber o que fazer
    assert "O que mudar na oferta" in r.text
    assert "também na" in r.text
    # e a instrução diz o LOCAL a cadastrar, com TURNO e horário: 1 local = campo+dia+turno,
    # então só o dia da semana não é uma providência que dê para executar
    assert "Cadastrar 1 local na" in r.text
    from app.core.rotulos import rotulo
    assert rotulo(Turno.manha) in r.text and "08:00–12:00" in r.text


def test_fila_pos_geracao_separa_conflito_de_falta_de_vaga(client, db_session):
    """Depois de gerar, o título não pode chamar conflito de horário de "sem vaga"."""
    db = db_session
    c = _rascunho(db)
    _disputa_de_assento(db, c)
    c.passo_bootstrap = passos.numero("revisao")
    db.flush()

    g = client.post("/ui/bootstrap/gerar")
    assert g.status_code == 200
    assert "matrícula(s) não couberam neste ciclo" in g.text
    assert "sem vaga neste ciclo" not in g.text
    assert "por conflito de horário" in g.text


def test_revisao_preve_o_resultado_da_geracao_antes_de_gerar(client, db_session):
    """A Revisão tem de mostrar, ANTES de gerar, o número que a geração vai entregar.

    Sem isto a tela dizia "vagas cobrem tudo / todos fecham" e a geração seguinte entregava
    gente na fila — a comissão descobria a divergência depois. A prévia é uma rodada do motor
    (barata), então entra no render; o "o que abrir" continua sob demanda.
    """
    db = db_session
    c = _rascunho(db)
    _disputa_de_assento(db, c)
    c.passo_bootstrap = passos.numero("revisao")
    db.flush()

    r = client.get("/ui/bootstrap")
    assert r.status_code == 200
    assert "O que a geração vai entregar" in r.text
    assert "de 2 concluem" in r.text
    assert "não concluiriam" in r.text
    assert "por conflito de horário" in r.text

    # e o número da prévia é o mesmo que a geração entrega
    g = client.post("/ui/bootstrap/gerar")
    assert g.status_code == 200
    assert "1 matrícula(s) não couberam neste ciclo" in g.text
