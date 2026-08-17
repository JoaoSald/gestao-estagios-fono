"""Instância única de Jinja2Templates, compartilhada por main.py e pelos routers UI (FASE 5)."""
from __future__ import annotations

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.core.config import BASE_DIR
from app.core.navegacao import menu_de
from app.core.rotulos import rotulo
from app.core.seguranca import COOKIE_SESSAO, ler_token

TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"


def _contexto_usuario(request: Request) -> dict:
    """Injeta `usuario`/`pode_editar` em TODO render, inclusive nas parciais HTMX.

    Precisa ser um processador de contexto, não um extra do `contexto_shell`: as parciais
    (`partials/estagios_campo.html` e cia.) são renderizadas direto pelos routers, sem o
    shell. Se `pode_editar` faltasse ali, o Jinja o trataria como falso e os botões de
    ação desapareceriam **também para a coordenação** — sem erro nenhum no log.
    """
    sessao = ler_token(request.cookies.get(COOKIE_SESSAO))
    return {"usuario": sessao, "pode_editar": bool(sessao and sessao.pode_editar)}


templates = Jinja2Templates(directory=str(TEMPLATES_DIR), context_processors=[_contexto_usuario])

# `{{ menu_de(usuario.perfil) }}` → itens da sidebar visíveis para o perfil (ver navegacao.py).
templates.env.globals["menu_de"] = menu_de

# `{{ valor|rot }}` → rótulo acentuado do valor de enum (ver app/core/rotulos.py).
templates.env.filters["rot"] = rotulo
templates.env.globals["rot"] = rotulo


def estatico(caminho: str) -> str:
    """URL de um arquivo estático com CACHE-BUST pela data de modificação.

    Sem isto, mudança em `styles.css`/`app.js` **não chega ao navegador**: o
    `StaticFiles` não manda `Cache-Control`, então o browser aplica cache heurístico —
    e, pior, o HTMX troca só o HTML, nunca re-busca a folha de estilo da página já
    aberta. O sintoma é cruel de diagnosticar: markup novo (com classes novas) sendo
    pintado por CSS velho, e a tela "quebrada" sem nenhum erro no servidor.

    A URL vira `/static/css/styles.css?v=<mtime>`, então cada versão do arquivo é uma
    URL nova e o cache passa a trabalhar a favor.
    """
    arq = STATIC_DIR / caminho
    try:
        versao = int(arq.stat().st_mtime)
    except OSError:            # arquivo ausente: serve sem versão em vez de estourar
        return f"/static/{caminho}"
    return f"/static/{caminho}?v={versao}"


templates.env.globals["estatico"] = estatico
