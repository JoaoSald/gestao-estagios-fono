"""Serviço de usuários e primitivas de sessão (FASE 6).

Complementa `test_autorizacao.py`: lá é "quem alcança o quê"; aqui é "quem é quem" —
autenticação, hash e token, testados sem passar por HTTP.
"""
from __future__ import annotations

import pytest

import tests.factories as f
from app.core import seguranca
from app.core.errors import Conflito, DomainError
from app.models.enums import PerfilUsuario
from app.services import usuario as su
from tests.factories import SENHA_TESTE


# ============================ Senha ============================
def test_hash_nao_guarda_a_senha_e_confere():
    h = seguranca.hash_senha("segredo123")
    assert "segredo123" not in h
    assert seguranca.senha_confere("segredo123", h)
    assert not seguranca.senha_confere("segredo124", h)


def test_dois_hashes_da_mesma_senha_sao_diferentes():
    """Salt por hash: banco vazado não revela quem repetiu senha."""
    assert seguranca.hash_senha("igual123") != seguranca.hash_senha("igual123")


def test_hash_corrompido_e_falso_nao_erro():
    """Registro estranho no banco não pode virar 500 na tela de login."""
    assert not seguranca.senha_confere("x", None)
    assert not seguranca.senha_confere("x", "")
    assert not seguranca.senha_confere("x", "isto-nao-e-um-hash")


def test_conta_so_de_sso_nao_abre_com_senha_nenhuma(db_session):
    """`senha=None` grava um hash que nenhuma senha digitada casa."""
    u = su.criar(db_session, nome="Só SSO", email="sso@ufcspa.edu.br",
                 perfil=PerfilUsuario.aluno)
    assert u.senha_hash                       # a coluna é NOT NULL
    for tentativa in ("", " ", "senha1234", u.email):
        assert not seguranca.senha_confere(tentativa, u.senha_hash)


# ============================ Token ============================
def test_token_leva_perfil_e_matricula():
    ses = seguranca.Sessao(7, "Ana Lima", "a@x", PerfilUsuario.aluno, matricula="20240007")
    volta = seguranca.ler_token(seguranca.criar_token(ses))
    assert volta == ses


def test_token_adulterado_ou_ausente_e_none():
    t = seguranca.criar_token(seguranca.Sessao(1, "X", "x@x", PerfilUsuario.coordenacao))
    assert seguranca.ler_token(t[:-3] + "aaa") is None
    assert seguranca.ler_token(None) is None
    assert seguranca.ler_token("") is None
    assert seguranca.ler_token("a.b.c") is None


def test_token_expirado_e_none():
    ses = seguranca.Sessao(1, "X", "x@x", PerfilUsuario.coordenacao)
    assert seguranca.ler_token(seguranca.criar_token(ses, horas=-1)) is None


def test_pode_editar_por_perfil():
    def sessao(p):
        return seguranca.Sessao(1, "X", "x@x", p)

    assert sessao(PerfilUsuario.coordenacao).pode_editar
    assert sessao(PerfilUsuario.administrador).pode_editar
    assert not sessao(PerfilUsuario.docente).pode_editar
    assert not sessao(PerfilUsuario.aluno).pode_editar


def test_iniciais_do_avatar():
    def ini(nome):
        return seguranca.Sessao(1, nome, "x@x", PerfilUsuario.aluno).iniciais

    assert ini("Maria Silva Souza") == "MS"
    assert ini("Madonna") == "MA"
    assert ini("  ") == "?"


# ============================ Autenticação ============================
def test_autentica_e_registra_o_acesso(db_session):
    u = f.usuario(db_session, PerfilUsuario.coordenacao)
    assert u.ultimo_acesso is None
    ses = su.autenticar(db_session, u.email, SENHA_TESTE)
    assert ses.usuario_id == u.id and ses.perfil == PerfilUsuario.coordenacao
    assert u.ultimo_acesso is not None


def test_email_no_login_ignora_caixa_e_espaco(db_session):
    u = f.usuario(db_session, PerfilUsuario.docente)
    ses = su.autenticar(db_session, f"  {u.email.upper()}  ", SENHA_TESTE)
    assert ses.usuario_id == u.id


def test_senha_errada_e_email_inexistente_dao_A_MESMA_mensagem(db_session):
    """Não contar a quem tenta quais e-mails existem."""
    u = f.usuario(db_session, PerfilUsuario.coordenacao)
    with pytest.raises(DomainError) as e1:
        su.autenticar(db_session, u.email, "outra-senha")
    with pytest.raises(DomainError) as e2:
        su.autenticar(db_session, "ninguem@ufcspa.edu.br", SENHA_TESTE)
    assert e1.value.mensagem == e2.value.mensagem == su.FALHA_LOGIN
    assert e1.value.status_code == 401


def test_usuario_desativado_nao_entra(db_session):
    u = f.usuario(db_session, PerfilUsuario.coordenacao)
    su.desativar(db_session, u.id)
    with pytest.raises(DomainError):
        su.autenticar(db_session, u.email, SENHA_TESTE)


# ============================ Cadastro ============================
def test_email_duplicado_e_conflito(db_session):
    u = f.usuario(db_session, PerfilUsuario.aluno)
    with pytest.raises(Conflito):
        su.criar(db_session, nome="Outro", email=u.email.upper(),
                 perfil=PerfilUsuario.aluno, senha="senha1234")


def test_senha_curta_e_recusada_em_pt_br(db_session):
    with pytest.raises(DomainError) as exc:
        su.criar(db_session, nome="X", email="curta@ufcspa.edu.br",
                 perfil=PerfilUsuario.coordenacao, senha="1234")
    assert "8 caracteres" in exc.value.mensagem


def test_senha_longa_demais_para_o_bcrypt_e_recusada(db_session):
    """bcrypt ignora o que passa de 72 bytes: aceitar em silêncio deixaria a senha do
    usuário mais fraca do que ele pensa."""
    with pytest.raises(DomainError) as exc:
        su.criar(db_session, nome="X", email="longa@ufcspa.edu.br",
                 perfil=PerfilUsuario.coordenacao, senha="a" * 73)
    assert "máximo" in exc.value.mensagem


def test_perfil_padrao_e_o_menor_privilegio(db_session):
    """Coluna com DEFAULT `aluno`: usuário criado sem perfil explícito não ganha acesso."""
    from app.models.usuario import Usuario
    u = Usuario(nome="Sem Perfil", email="sp@ufcspa.edu.br",
                senha_hash=seguranca.hash_sem_senha())
    db_session.add(u)
    db_session.flush()
    db_session.refresh(u)
    assert u.perfil == PerfilUsuario.aluno and not u.pode_editar


def test_troca_de_senha_invalida_a_anterior(db_session):
    u = f.usuario(db_session, PerfilUsuario.coordenacao)
    su.trocar_senha(db_session, u.id, "novasenha1")
    with pytest.raises(DomainError):
        su.autenticar(db_session, u.email, SENHA_TESTE)
    assert su.autenticar(db_session, u.email, "novasenha1").usuario_id == u.id


def test_existe_algum_editor_ve_so_editor_ativo(db_session):
    """Guarda do script de contas: não deixar o sistema trancado sem coordenação."""
    f.usuario(db_session, PerfilUsuario.aluno)
    f.usuario(db_session, PerfilUsuario.docente)
    assert su.existe_algum_editor(db_session) is False
    coord = f.usuario(db_session, PerfilUsuario.coordenacao)
    assert su.existe_algum_editor(db_session) is True
    su.desativar(db_session, coord.id)
    assert su.existe_algum_editor(db_session) is False
