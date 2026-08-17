"""Gates de acesso compartilhados por TODOS os routers — JSON e UI (FASE 6).

Vive fora de `routers/ui/` de propósito: a API JSON precisa do mesmo gate e não deve
depender da camada de apresentação. Aqui só está "quem é" e "pode escrever"; o gate de
ESTADO DO CICLO (que é assunto de tela) fica em `routers/ui/deps.py`.

Duas perguntas, nesta ordem:

  1. quem é?        → `exigir_sessao`      (sem sessão → /login ou 401)
  2. o que alcança? → `exigir_coordenacao` (escrita) · `exigir_leitura_ampla` (operação em
                      leitura: painel e histórico) · nada (escala, que todo perfil vê)

São TRÊS alcances porque leitura não é um bloco só: o docente lê a operação (painel,
histórico), o aluno lê apenas a escala publicada. Um gate único de "leitura" obrigaria a
escolher entre mostrar a fila de remanejo ao aluno ou esconder o painel do docente.

O gate é de ROTA, no servidor. Esconder botão no template (`pode_editar`) é só cortesia
para não oferecer o que a rota vai recusar — nunca a proteção.
"""
from __future__ import annotations

from fastapi import Depends, Request, Response

from app.core.config import settings
from app.core.navegacao import LEITURA_AMPLA
from app.core.seguranca import COOKIE_SESSAO, Sessao, criar_token, ler_token


class RedirecionarLogin(Exception):
    """Sem sessão válida → o handler em main.py manda para /login (ou devolve 401)."""


class SemPermissao(Exception):
    """Autenticado, mas o perfil não alcança o recurso (HTTP 403).

    Distinto de `RedirecionarLogin` de propósito: mandar para /login quem JÁ está logado
    faz o usuário achar que a sessão caiu e tentar de novo para sempre.
    """

    def __init__(self, mensagem: str = "Seu perfil não tem acesso a esta parte do sistema.") -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


# ============================ Cookie de sessão ============================
def gravar_sessao(resp: Response, sessao: Sessao, horas: int | None = None) -> None:
    """Põe o JWT assinado no cookie. `secure` só em produção (em dev não há HTTPS)."""
    resp.set_cookie(
        COOKIE_SESSAO,
        criar_token(sessao, horas),
        httponly=True,
        samesite="lax",
        secure=settings.em_producao,
        max_age=(horas or settings.SESSAO_HORAS) * 3600,
    )


def limpar_sessao(resp: Response) -> None:
    resp.delete_cookie(COOKIE_SESSAO)


# ============================ 1. Quem é ============================
def sessao_opcional(request: Request) -> Sessao | None:
    """Sessão do request, ou `None`. Não levanta — para /login, /ui/aguarde e o shell."""
    return ler_token(request.cookies.get(COOKIE_SESSAO))


def exigir_sessao(request: Request) -> Sessao:
    """Gate das rotas autenticadas. Devolve a `Sessao` — o FastAPI cacheia a dependência
    por request, então usá-la como `dependencies=[...]` e como parâmetro do handler custa
    uma resolução só."""
    sessao = sessao_opcional(request)
    if sessao is None:
        raise RedirecionarLogin()
    return sessao


# ============================ 2. O que alcança ============================
def exigir_coordenacao(sessao: Sessao = Depends(exigir_sessao)) -> Sessao:
    """Só a comissão (coordenação/admin) escreve. Perfil de leitura → 403."""
    if not sessao.pode_editar:
        raise SemPermissao()
    return sessao


def exigir_leitura_ampla(sessao: Sessao = Depends(exigir_sessao)) -> Sessao:
    """Telas de OPERAÇÃO em leitura (painel, histórico): comissão + docente.

    O aluno fica fora: painel e histórico falam de fila, pendências e egressos — operação
    da comissão, não a escala dele. A lista é a mesma que filtra o menu (`navegacao.py`),
    para menu e rota nunca discordarem.
    """
    if sessao.perfil not in LEITURA_AMPLA:
        raise SemPermissao("Esta tela é da comissão de estágios e do corpo docente.")
    return sessao
