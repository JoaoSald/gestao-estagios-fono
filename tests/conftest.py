"""Fixtures de teste.

Cada teste roda dentro de UMA transação externa que é revertida no teardown
(`join_transaction_mode="create_savepoint"`): os `commit()` dos services viram
releases de savepoint, então NADA é persistido no banco real `estagios_fono`.
Os catálogos e o ciclo do seed ficam legíveis (foram commitados antes).

O ciclo do seed nasce `encerrado` (é o estado inicial de deploy: nada ativo, ele só
existe para pendurar os locais e servir de fonte do clone — ver docs/seed_v2.sql), mas
a suíte pressupõe um ciclo OPERÁVEL. Por isso `db_session` o normaliza para
`em_andamento` dentro da transação revertida; quem precisa de outro status o define no
próprio teste (`cic.status = StatusCiclo.rascunho`), como já era o padrão.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import tests.factories as factories
from app.core.database import engine, get_db
from app.core.seguranca import COOKIE_SESSAO, criar_token
from app.main import app
from app.models.ciclo import Ciclo
from app.models.enums import PerfilUsuario, StatusCiclo
from app.services import usuario as usuario_service


@pytest.fixture
def db_session():
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        _ciclo_operavel(session)
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


def _ciclo_operavel(session: Session) -> None:
    """Põe o ciclo do seed em `em_andamento` (rollback no teardown desfaz)."""
    ciclo = session.scalars(select(Ciclo)).first()
    if ciclo is not None and ciclo.status != StatusCiclo.em_andamento:
        ciclo.status = StatusCiclo.em_andamento
        ciclo.encerrado_em = None
        session.flush()


@pytest.fixture
def _app_na_transacao(db_session):
    """O app com `get_db` apontando para a sessão revertida do teste."""
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def cliente_anonimo(_app_na_transacao):
    """TestClient SEM sessão — para o que se testa antes do login."""
    return TestClient(_app_na_transacao)


@pytest.fixture
def novo_cliente(_app_na_transacao, db_session):
    """Fábrica de clientes autenticados. Cada perfil ganha um TestClient PRÓPRIO: um teste
    que compara dois perfis (ex.: a mesma tela com e sem as ações) precisa dos dois
    cookies vivos ao mesmo tempo, e cookie é estado do cliente."""
    def _fazer(perfil: PerfilUsuario) -> TestClient:
        return autenticar(TestClient(_app_na_transacao), db_session, perfil)

    return _fazer


# ============================ Sessão (FASE 6) ============================
def autenticar(cliente: TestClient, db_session: Session, perfil: PerfilUsuario) -> TestClient:
    """Põe no cliente o cookie de sessão de um usuário do perfil pedido.

    O token é assinado direto (`criar_token`), sem passar pelo formulário de login: o que
    cada teste quer exercitar é a AUTORIZAÇÃO da rota, não o login — e na FASE B o caminho
    normal passa a ser o SSO institucional, que não teria como ser encenado aqui.
    """
    u = factories.usuario(db_session, perfil)
    cliente.cookies.set(COOKIE_SESSAO, criar_token(usuario_service.sessao_de(u)))
    return cliente


@pytest.fixture
def client(novo_cliente):
    """Cliente PADRÃO da suíte: coordenação.

    Quem opera o sistema é a comissão, e é o que a suíte inteira exercita (cadastros,
    geração, ajustes). Sessão anônima é o caso especial e tem fixture própria — assim
    nenhum teste de comportamento precisa falar de login.
    """
    return novo_cliente(PerfilUsuario.coordenacao)


@pytest.fixture
def cliente_coordenacao(client):
    return client


@pytest.fixture
def cliente_docente(novo_cliente):
    return novo_cliente(PerfilUsuario.docente)


@pytest.fixture
def cliente_aluno(novo_cliente):
    return novo_cliente(PerfilUsuario.aluno)
