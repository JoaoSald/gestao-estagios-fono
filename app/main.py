"""Ponto de entrada da API (FastAPI).

FASE 2 — esqueleto: app, CORS, estáticos, Jinja2, healthcheck e a home.
FASE 6 — divisão de acesso: cada router declara seu gate (ver `routers/ui/deps.py`) e os
handlers abaixo traduzem "sem sessão"/"sem permissão" para a resposta certa de cada
cliente (navegação, HTMX ou JSON).
Rodar em dev:  uvicorn app.main:app --reload
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.config import BASE_DIR, settings
from app.core.errors import DomainError
from app.core.seguranca import COOKIE_SESSAO, ler_token
from app.routers import (
    afastamentos, alunos, areas, ciclos, docentes, escala, eventos,
    health, locais, preceptores,
)
from app.routers.ui import bootstrap as ui_bootstrap
from app.routers.ui import cadastros as ui_cadastros
from app.routers.ui import consulta as ui_consulta
from app.routers.ui import escala as ui_escala
from app.routers.ui import paginas as ui_paginas
from app.routers.acesso import RedirecionarLogin, SemPermissao
from app.routers.ui.deps import Redirecionar

app = FastAPI(
    title="Gestão de Estágios — Fonoaudiologia UFCSPA",
    version="0.2.0",
    description="API do planejador de escala de estágios (server-rendered, Jinja2 + HTMX).",
)

# CORS: liberado em dev. Em produção, restringir aos domínios da faculdade.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "dev" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estáticos (CSS/JS/img reaproveitados do protótipo).
STATIC_DIR = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================ Rede de segurança da escrita ============================
# Rotas abertas por natureza (não têm o que proteger) — o `/login` precisa aceitar POST
# de quem ainda não tem sessão.
ROTAS_LIVRES = ("/login", "/logout", "/health", "/static", "/docs", "/openapi.json", "/redoc")


@app.middleware("http")
async def bloquear_escrita_de_leitor(request: Request, call_next):
    """Perfil de LEITURA não escreve, em nenhuma rota — nem nas que esquecerem o gate.

    O gate correto é a dependência de cada router (`exigir_coordenacao`); esta camada é a
    rede: se uma rota nova nascer no router errado, ela ainda assim não muda dados. Sem
    isso, a segurança do sistema passaria a depender de ninguém errar um `include_router`.

    Só barra quem TEM sessão e não pode editar — request sem sessão segue e é tratado pelo
    gate da rota (que sabe se o certo é redirecionar para /login ou devolver 401).
    """
    if request.method in ("GET", "HEAD", "OPTIONS") or request.url.path.startswith(ROTAS_LIVRES):
        return await call_next(request)
    sessao = ler_token(request.cookies.get(COOKIE_SESSAO))
    if sessao is not None and not sessao.pode_editar:
        return _resposta_sem_permissao(
            request, "Seu perfil é somente leitura: esta ação é da comissão de estágios."
        )
    return await call_next(request)


# ============================ Handlers de erro ============================
# A UI toda mora sob `/ui` (mais `/` e `/login`) e a raiz é a API JSON — invariante da
# FASE 5. É por ISSO que se decide "responder tela ou dado", e não pelo header `Accept`:
# Accept varia com o cliente (um navegador exótico levaria JSON; um cliente de API que
# manda `*/*` levaria HTML), enquanto o caminho é a própria arquitetura.
CAMINHOS_DE_TELA = ("/ui", "/login", "/logout")


def _e_tela(request: Request) -> bool:
    caminho = request.url.path
    return caminho == "/" or caminho.startswith(CAMINHOS_DE_TELA)


def _e_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _resposta_sem_permissao(request: Request, mensagem: str) -> Response:
    """403 na forma que cada cliente entende.

    HTMX ganha `HX-Reswap: none` porque, em resposta de erro, ele não troca o alvo — sem
    isso a tela ficaria muda, dando a impressão de que o clique não funcionou.
    """
    if _e_htmx(request):
        return Response(content=mensagem, status_code=403, headers={"HX-Reswap": "none"},
                        media_type="text/plain; charset=utf-8")
    if _e_tela(request):
        return HTMLResponse(status_code=403, content=(
            "<!doctype html><meta charset='utf-8'>"
            "<title>Sem permissão · Gestão de Estágios</title>"
            "<div style=\"font-family:system-ui;max-width:32rem;margin:20vh auto;text-align:center\">"
            f"<h1 style='font-size:1.2rem'>Sem permissão</h1><p>{mensagem}</p>"
            "<p><a href='/'>Voltar ao início</a></p></div>"
        ))
    return JSONResponse(status_code=403, content={"detail": mensagem})


@app.exception_handler(DomainError)
def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Regra de negócio violada → JSON pt-BR com o status certo (400/404/409)."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.mensagem})


@app.exception_handler(RedirecionarLogin)
def _redirecionar_login(request: Request, exc: RedirecionarLogin) -> Response:
    """Sem sessão. Navegação vai para /login; HTMX pede ao próprio htmx que navegue
    (senão o fragmento de login seria injetado dentro da página); API recebe 401."""
    if _e_htmx(request):
        return Response(status_code=401, headers={"HX-Redirect": "/login"})
    if _e_tela(request):
        return RedirectResponse("/login", status_code=303)
    return JSONResponse(status_code=401, content={"detail": "Autenticação necessária."})


@app.exception_handler(SemPermissao)
def _sem_permissao(request: Request, exc: SemPermissao) -> Response:
    """Logado, mas fora do alcance do perfil → 403 (nunca /login: quem já entrou acharia
    que a sessão caiu e tentaria de novo para sempre)."""
    return _resposta_sem_permissao(request, exc.mensagem)


@app.exception_handler(Redirecionar)
def _redirecionar(request: Request, exc: Redirecionar) -> RedirectResponse:
    """Gate por estado do ciclo → welcome/bootstrap/painel/aguarde."""
    return RedirectResponse(exc.destino, status_code=303)


# Routers
app.include_router(health.router)
app.include_router(areas.router)
app.include_router(docentes.router)
app.include_router(preceptores.router)
app.include_router(ciclos.router)
app.include_router(locais.router)
app.include_router(alunos.router)
app.include_router(afastamentos.router)
app.include_router(eventos.router)
app.include_router(escala.router)

# FASE 5/6 — camada de apresentação (páginas + parciais HTMX).
app.include_router(ui_paginas.auth_router)
# `consulta` (leitura) ANTES de `cadastros`: lá existem padrões gulosos (`/{recurso}/form`,
# `POST /{recurso}`) que capturariam caminhos de `/ui/estagios/...` se viessem primeiro.
app.include_router(ui_consulta.router)
app.include_router(ui_consulta.router_amplo)
app.include_router(ui_consulta.router_livre)
app.include_router(ui_bootstrap.router)
app.include_router(ui_paginas.router)
app.include_router(ui_cadastros.router)
app.include_router(ui_escala.router)
