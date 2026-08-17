"""Divisão de acesso (FASE 6): quem alcança o quê.

O teste que sustenta os outros é o SWEEP: em vez de conferir rota por rota (o que envelhece
mal — rota nova nasce sem teste e ninguém percebe), ele varre `app.routes` e exige que TODA
rota declare gate, e que nenhuma rota de escrita fique acessível a perfil de leitura. Rota
pública é uma lista curta e explícita: se alguém precisar de uma nova, tem que vir aqui
escrever o porquê.
"""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

import tests.factories as f
from app.core.navegacao import menu_de
from app.core.seguranca import COOKIE_SESSAO, Sessao, criar_token
from app.main import app
from app.models.enums import PerfilUsuario, StatusCiclo
from app.routers.acesso import exigir_coordenacao, exigir_sessao

# Rotas sem gate, por natureza (e o motivo). Qualquer outra sem gate é bug.
ROTAS_PUBLICAS = {
    ("GET", "/health"),            # healthcheck do deploy
    ("GET", "/login"),             # o formulário
    ("POST", "/login"),            # a submissão (quem entra ainda não tem sessão)
    ("GET", "/logout"),            # limpar cookie não exige provar quem é
}

METODOS_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}


def _rotas(router, prefixo: str = ""):
    """Anda a árvore de routers. Esta versão do FastAPI guarda os `include_router` como
    nós (`original_router`) em vez de achatar as rotas em `app.routes`."""
    for r in getattr(router, "routes", []):
        if isinstance(r, APIRoute):
            yield prefixo + r.path, r
        elif hasattr(r, "original_router"):
            yield from _rotas(r.original_router, prefixo + (r.include_context.prefix or ""))


def _gates(rota: APIRoute) -> set:
    """Nomes das dependências da rota, incluindo as aninhadas (`exigir_coordenacao`
    depende de `exigir_sessao`)."""
    nomes: set[str] = set()

    def anda(deps):
        for d in deps:
            if d.call is not None:
                nomes.add(getattr(d.call, "__name__", str(d.call)))
            anda(d.dependencies)

    anda(rota.dependant.dependencies)
    return nomes


def _superficie() -> list[tuple[str, str, set]]:
    saida = []
    for caminho, rota in _rotas(app):
        for metodo in sorted(rota.methods - {"HEAD", "OPTIONS"}):
            saida.append((metodo, caminho, _gates(rota)))
    return saida


# ============================ O sweep ============================
def test_toda_rota_tem_gate():
    """Nenhuma rota fica sem exigir sessão, fora da lista pública explícita."""
    sem_gate = [
        f"{m} {c}" for m, c, g in _superficie()
        if (m, c) not in ROTAS_PUBLICAS and exigir_sessao.__name__ not in g
    ]
    assert not sem_gate, "rotas sem gate de sessão: " + ", ".join(sorted(sem_gate))


def test_toda_escrita_exige_coordenacao():
    """Perfil de leitura não escreve: método de escrita ⇒ `exigir_coordenacao` na rota."""
    frouxas = [
        f"{m} {c}" for m, c, g in _superficie()
        if m in METODOS_ESCRITA and (m, c) not in ROTAS_PUBLICAS
        and exigir_coordenacao.__name__ not in g
    ]
    assert not frouxas, "escrita sem gate de coordenação: " + ", ".join(sorted(frouxas))


def test_api_json_inteira_e_da_coordenacao():
    """A API REST (fora de /ui) é ferramenta da comissão — inclusive nos GETs, que
    devolvem a base toda (alunos, locais, escala) sem a moldura da tela."""
    abertas = [
        f"{m} {c}" for m, c, g in _superficie()
        if not c.startswith(("/ui", "/login", "/logout", "/health")) and c != "/"
        and exigir_coordenacao.__name__ not in g
    ]
    assert not abertas, "API JSON sem gate de coordenação: " + ", ".join(sorted(abertas))


# ============================ Sem sessão ============================
def test_pagina_sem_sessao_vai_para_login(cliente_anonimo):
    r = cliente_anonimo.get("/ui/estagios", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_api_sem_sessao_devolve_401_json(cliente_anonimo):
    """API não redireciona: um cliente de API seguindo 303 receberia o HTML do login
    com status 200 e acharia que deu certo."""
    r = cliente_anonimo.get("/alunos", follow_redirects=False)
    assert r.status_code == 401 and r.json()["detail"]


def test_htmx_sem_sessao_pede_navegacao_ao_htmx(cliente_anonimo):
    """HTMX recebe HX-Redirect; um 303 seria seguido e o login entraria como fragmento
    dentro da página."""
    r = cliente_anonimo.get("/ui/estagios/conteudo", headers={"HX-Request": "true"},
                   follow_redirects=False)
    assert r.status_code == 401 and r.headers["HX-Redirect"] == "/login"


def test_cookie_adulterado_nao_abre_sessao(cliente_anonimo, db_session):
    u = f.usuario(db_session, PerfilUsuario.coordenacao)
    token = criar_token(Sessao(u.id, u.nome, u.email, PerfilUsuario.coordenacao))
    cliente_anonimo.cookies.set(COOKIE_SESSAO, token[:-4] + "abcd")   # mexe na assinatura
    r = cliente_anonimo.get("/ui/painel", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"


def test_perfil_vem_do_token_assinado_nao_do_request(cliente_aluno):
    """Não existe como pedir outro perfil: o perfil só entra pelo token assinado.

    Tentativas óbvias (parâmetro, header, cookie solto) não mudam nada — e o cookie de
    sessão adulterado cai no teste acima.
    """
    assert cliente_aluno.get("/ui/painel?perfil=coordenacao").status_code == 403
    assert cliente_aluno.get("/ui/painel", headers={"X-Perfil": "coordenacao"}).status_code == 403
    cliente_aluno.cookies.set("perfil", "coordenacao")
    assert cliente_aluno.get("/ui/painel").status_code == 403


# ============================ Aluno ============================
def test_aluno_ve_estagios(cliente_aluno):
    r = cliente_aluno.get("/ui/estagios")
    assert r.status_code == 200 and "Estágios" in r.text


def test_aluno_ve_as_tres_abas(cliente_aluno):
    for vista in ("aluno", "campo", "grupos"):
        r = cliente_aluno.get(f"/ui/estagios/conteudo?vista={vista}")
        assert r.status_code == 200, vista


def test_aluno_nao_ve_cadastros_nem_painel(cliente_aluno):
    for caminho in ("/ui/alunos", "/ui/locais", "/ui/eventos", "/ui/painel",
                    "/ui/historico", "/ui/bootstrap", "/ui/remanejar", "/ui/encerrar"):
        assert cliente_aluno.get(caminho).status_code == 403, caminho


def test_aluno_nao_escreve(cliente_aluno):
    assert cliente_aluno.post("/ui/docentes", data={"nome": "X", "ativo": "on"}).status_code == 403
    assert cliente_aluno.delete("/ui/docentes/1").status_code == 403
    assert cliente_aluno.post("/ui/estagios/remover",
                              data={"aluno_id": 1, "grupo_id": 1}).status_code == 403


def test_aluno_nao_alcanca_api_json(cliente_aluno):
    assert cliente_aluno.get("/alunos").status_code == 403
    assert cliente_aluno.post("/areas", json={"nome": "X", "carga_exigida": 40}).status_code == 403


def test_aluno_nao_ve_menu_de_cadastro(cliente_aluno):
    """O menu é filtrado por perfil — não por CSS."""
    html = cliente_aluno.get("/ui/estagios").text
    assert "/ui/estagios" in html
    for url in ("/ui/locais", "/ui/docentes", "/ui/painel", "/ui/historico"):
        assert f'href="{url}"' not in html, url


def test_aluno_ve_a_escala_mas_nao_as_acoes_de_ajuste(cliente_aluno, cliente_coordenacao,
                                                      db_session):
    """Mesma tela e mesmos DADOS; só as ações mudam.

    Precisa de escala gerada: sem alocação a aba "Por campo" cai no vazio e o teste
    passaria por não ter botão nenhum a esconder — o controle com a coordenação é o que
    prova que o `pode_editar` do template está de fato ligado.
    """
    c = f.ciclo(db_session)
    ar = f.area(db_session, carga=16)
    f.local(db_session, c, ar, capacidade=2, campo="Campo Autorizacao A")
    f.local(db_session, c, ar, capacidade=2, campo="Campo Autorizacao B")
    al = f.aluno(db_session, c, nome="Aluno Da Escala")
    f.matricular(db_session, al, ar)
    from app.services.motor import escala as motor
    motor.gerar_escala(db_session, c)

    aluno = cliente_aluno.get("/ui/estagios/conteudo?vista=campo").text
    coord = cliente_coordenacao.get("/ui/estagios/conteudo?vista=campo").text

    # o dado é o mesmo para os dois
    assert "Aluno Da Escala" in aluno and "Aluno Da Escala" in coord
    # as ações, não
    assert "adicionar-modal" in coord and "mover-campo-modal" in coord
    assert "adicionar-modal" not in aluno and "mover-campo-modal" not in aluno


def test_aluno_baixa_a_escala(cliente_aluno):
    """Download é a mesma informação da tela em outro formato → segue o gate da tela."""
    r = cliente_aluno.get("/ui/estagios/grupos.xlsx")
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment")


# ============================ Docente ============================
def test_docente_ve_painel_e_historico_mas_nao_cadastros(cliente_docente):
    assert cliente_docente.get("/ui/painel").status_code == 200
    assert cliente_docente.get("/ui/historico").status_code == 200
    assert cliente_docente.get("/ui/estagios").status_code == 200
    for caminho in ("/ui/locais", "/ui/alunos", "/ui/eventos", "/ui/bootstrap"):
        assert cliente_docente.get(caminho).status_code == 403, caminho


def test_docente_nao_escreve(cliente_docente):
    assert cliente_docente.post("/ui/areas/1/subareas", data={"nome": "X"}).status_code == 403


# ============================ Coordenação ============================
def test_coordenacao_alcanca_tudo(cliente_coordenacao):
    for caminho in ("/ui/painel", "/ui/estagios", "/ui/alunos", "/ui/locais",
                    "/ui/eventos", "/ui/historico", "/ui/remanejar"):
        assert cliente_coordenacao.get(caminho).status_code == 200, caminho


def test_coordenacao_escreve(cliente_coordenacao):
    r = cliente_coordenacao.post("/ui/docentes",
                                 data={"nome": "Docente Autorizacao", "email": "da@ufcspa.edu.br",
                                       "ativo": "on"})
    assert r.status_code == 200 and "Docente Autorizacao" in r.text


# ============================ Ciclo não publicado ============================
def test_leitor_em_ciclo_rascunho_vai_para_aguarde(cliente_aluno, db_session):
    """Rascunho é escala em edição: o aluno não vê, e não pode cair no wizard."""
    f.ciclo(db_session).status = StatusCiclo.rascunho
    db_session.flush()
    r = cliente_aluno.get("/ui/estagios", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ui/aguarde"
    pagina = cliente_aluno.get("/ui/aguarde")
    assert pagina.status_code == 200 and "não publicada" in pagina.text


def test_coordenacao_em_rascunho_vai_para_o_bootstrap(cliente_coordenacao, db_session):
    f.ciclo(db_session).status = StatusCiclo.rascunho
    db_session.flush()
    r = cliente_coordenacao.get("/ui/estagios", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ui/bootstrap"


def test_aguarde_nao_e_beco_sem_saida(cliente_coordenacao, cliente_aluno):
    """Com ciclo em andamento ninguém fica na tela de espera."""
    r = cliente_aluno.get("/ui/aguarde", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ui/estagios"
    r = cliente_coordenacao.get("/ui/aguarde", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/ui/painel"


# ============================ Home por perfil ============================
@pytest.mark.parametrize("fixture,destino", [
    # Coordenação cai no painel (é a tela de OPERAR). Quem não edita cai na escala — o
    # painel continua no menu do docente, mas a primeira tela é o conteúdo, não a fila.
    ("cliente_coordenacao", "/ui/painel"),
    ("cliente_docente", "/ui/estagios"),
    ("cliente_aluno", "/ui/estagios"),
])
def test_home_roteia_por_perfil(request, fixture, destino):
    cli = request.getfixturevalue(fixture)
    r = cli.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == destino


# ============================ Menu ============================
def test_menu_do_aluno_tem_so_estagios():
    itens = [i.chave for g in menu_de(PerfilUsuario.aluno) for i in g.itens]
    assert itens == ["estagios"]


def test_menu_da_coordenacao_tem_tudo():
    itens = {i.chave for g in menu_de(PerfilUsuario.coordenacao) for i in g.itens}
    assert {"alunos", "locais", "painel", "estagios", "remanejar", "encerrar"} <= itens


def test_menu_sem_sessao_e_vazio():
    assert menu_de(None) == []
