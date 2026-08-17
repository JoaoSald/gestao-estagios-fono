"""Páginas completas (GET) do app — server-rendered com Jinja2.

Convenção: TUDO da UI mora sob `/ui` (páginas e parciais), deixando a raiz para a API
JSON (FASES 3/4). Exceção: login/logout/home ficam na raiz por conveniência.

Tudo neste módulo é da COMISSÃO (cadastros, painel, histórico, remanejar). A superfície
que aluno e docente alcançam está em `consulta.py` — ver o cabeçalho de lá.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import DomainError
from app.core.rotulos import rotulo
from app.core.seguranca import Sessao
from app.core.templates import templates
from app.routers.ui.deps import (
    destino_por_estado, exigir_coordenacao, exigir_operacao, exigir_sessao,
    gravar_sessao, limpar_sessao, render, sessao_opcional,
)
from app.services import usuario as usuario_service

# Auth/home na raiz (público).
auth_router = APIRouter(tags=["ui-auth"])
# Páginas internas de OPERAÇÃO sob /ui (exigem coordenação + ciclo em andamento).
router = APIRouter(prefix="/ui", tags=["ui"],
                   dependencies=[Depends(exigir_coordenacao), Depends(exigir_operacao)])


# ============================ Login ============================
@auth_router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)):
    if sessao_opcional(request) is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"titulo": "Entrar · Gestão de Estágios"})


@auth_router.post("/login")
def login_submit(request: Request, email: str = Form(...), senha: str = Form(...),
                 manter: str | None = Form(None), db: Session = Depends(get_db)):
    """Login por senha — hoje o único caminho; na FASE B ele fica como acesso de exceção
    da coordenação e o normal passa a ser o SSO institucional.

    Falha volta para a MESMA tela com o erro (não redireciona): redirecionar perderia a
    mensagem, e a comissão não saberia se errou a senha ou se o sistema caiu.
    """
    try:
        sessao = usuario_service.autenticar(db, email, senha)
    except DomainError as exc:
        return templates.TemplateResponse(
            request, "login.html",
            {"titulo": "Entrar · Gestão de Estágios", "erro": exc.mensagem, "email": email},
            status_code=exc.status_code,
        )
    resp = RedirectResponse("/", status_code=303)  # "/" roteia pelo perfil + estado do ciclo
    # "Manter conectado" desmarcado → cookie de sessão curto (fecha o expediente, sai).
    gravar_sessao(resp, sessao, horas=None if manter else 2)
    return resp


@auth_router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    limpar_sessao(resp)
    return resp


@auth_router.get("/")
def home(sessao: Sessao = Depends(exigir_sessao), db: Session = Depends(get_db)):
    """Porta única: cada perfil cai na sua tela (ver `destino_por_estado`).

    O gate é DEPENDÊNCIA, não checagem no corpo: é assim que a auditoria de rotas
    (`tests/test_autorizacao.py`) consegue ver que esta rota exige sessão.
    """
    return RedirectResponse(destino_por_estado(db, sessao), status_code=303)


# Painel e Histórico são operação em LEITURA (comissão + docente) → `consulta.py`.
# `_ctx_historico` fica aqui, onde nasceu, e é importado por lá.


# ============================ Páginas de cadastro ============================
def _pagina_cadastro(request: Request, db: Session, recurso: str):
    from app.routers.ui.cadastros import META, dados_tabela
    titulo, sub, novo_label, _del = META[recurso]
    dados = dados_tabela(db, recurso)
    return render(request, db, "cadastro.html", recurso,
                  titulo=titulo, sub=sub, novo_label=novo_label, **dados)


@router.get("/alunos")
def pagina_alunos(request: Request, vista: str = "matriculados", fase: str = "todos",
                  db: Session = Depends(get_db)):
    from app.routers.ui.alunos_op import ctx_op
    return render(request, db, "alunos.html", "alunos", **ctx_op(db, vista, fase))


@router.get("/alunos/conteudo")
def alunos_conteudo(request: Request, vista: str = "matriculados", fase: str = "todos",
                    db: Session = Depends(get_db)):
    from app.core.templates import templates
    from app.routers.ui.alunos_op import ctx_op
    return templates.TemplateResponse(request, "partials/alunos_op_conteudo.html", ctx_op(db, vista, fase))


@router.get("/alunos/oferta-card")
def alunos_oferta_card(area: int, request: Request, db: Session = Depends(get_db)):
    from app.core.templates import templates
    from app.routers.ui.alunos_op import previsao_inicio_area
    d = previsao_inicio_area(db, area)
    return templates.TemplateResponse(request, "partials/oferta_card.html", {"d": d})


@router.get("/alunos/{aluno_id:int}")
def pagina_aluno(aluno_id: int, request: Request, db: Session = Depends(get_db)):
    from app.routers.ui.aluno_dados import montar_aluno
    dados = montar_aluno(db, aluno_id)
    return render(request, db, "aluno.html", "alunos", **dados)


# `/ui/alunos/{id}/encontros` e `/encontros-cal` moraram aqui até a FASE 6: são o modal de
# calendário da aba "Por aluno", então acompanharam a escala para `consulta.py` (leitura).


@router.get("/areas")
def pagina_areas(request: Request, db: Session = Depends(get_db)):
    return _pagina_cadastro(request, db, "areas")


@router.get("/docentes")
def pagina_docentes(request: Request, db: Session = Depends(get_db)):
    return _pagina_cadastro(request, db, "docentes")


@router.get("/preceptores")
def pagina_preceptores(request: Request, db: Session = Depends(get_db)):
    return _pagina_cadastro(request, db, "preceptores")


@router.get("/afastamentos")
def pagina_afastamentos(request: Request, db: Session = Depends(get_db)):
    return _pagina_cadastro(request, db, "afastamentos")


@router.get("/locais")
def pagina_locais(request: Request, db: Session = Depends(get_db)):
    return _pagina_cadastro(request, db, "locais")


EV_COR = {"feriado": "#f43f5e", "academico": "#0ea5e9", "reuniao": "#8b5cf6", "recesso": "#f59e0b"}
_MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
_DOW_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


def _eventos_por_ano_mes(db) -> list[dict]:
    """Eventos agrupados ano → mês → lista (item 19). Espelha a hierarquia do protótipo."""
    from app.services import evento as evento_service
    from app.services.common import get_ciclo_ativo
    if get_ciclo_ativo(db) is None:
        return []
    anos: dict[int, dict[int, list]] = {}
    for e in evento_service.listar(db):  # já ordenado por data_inicio
        anos.setdefault(e.data_inicio.year, {}).setdefault(e.data_inicio.month, []).append(e)
    out = []
    for ano in sorted(anos):
        meses = []
        total_ano = 0
        for mes in sorted(anos[ano]):
            itens = []
            for e in anos[ano][mes]:
                multi = e.data_fim and e.data_fim != e.data_inicio
                itens.append({
                    "id": e.id, "nome": e.nome, "tipo": rotulo(e.tipo),
                    "cor": EV_COR.get(e.tipo.value, "#64748b"),
                    "dia": e.data_inicio.day, "dow": _DOW_PT[e.data_inicio.weekday()],
                    "periodo": (f"{e.data_inicio.strftime('%d/%m')} – {e.data_fim.strftime('%d/%m')}"
                                if multi else e.data_inicio.strftime("%d/%m")),
                    "multi": bool(multi), "bloqueia": e.bloqueia_estagio,
                    "origem": rotulo(e.origem),
                })
            total_ano += len(itens)
            meses.append({"mes": mes, "mes_nome": _MESES_PT[mes], "n": len(itens), "eventos": itens})
        out.append({"ano": ano, "n": total_ano, "meses": meses})
    return out


def _ctx_eventos(db: Session, vista: str, mes: str | None) -> dict:
    from datetime import date, timedelta
    from app.routers.ui import calendario as cal
    from app.routers.ui.cadastros import META, dados_tabela
    from app.services import evento as evento_service
    from app.services.common import get_ciclo_ativo
    ctx = {"vista": vista}
    if vista == "calendario":
        ciclo = get_ciclo_ativo(db)
        eventos = evento_service.listar(db) if ciclo else []
        if ciclo and eventos:
            min_mes = f"{ciclo.data_inicio.year}-01"
            max_mes = f"{ciclo.data_fim.year}-12"
            mes_ref = mes or cal.mes_inicial(min_mes, max_mes, date.today())
            y, m = int(mes_ref[:4]), int(mes_ref[5:7])
            chips: dict[date, list] = {}
            d = date(y, m, 1)
            while d.month == m:
                evs = [e for e in eventos if e.data_inicio <= d <= e.data_fim]
                if evs:
                    chips[d] = [{"kind": "sess", "label": e.nome, "cor": EV_COR.get(e.tipo.value, "#64748b"),
                                 "contorno": e.bloqueia_estagio} for e in evs]
                d += timedelta(days=1)
            tipos = {}
            for e in eventos:
                tipos.setdefault(e.tipo.value, 0)
                tipos[e.tipo.value] += 1
            legenda = [{"label": rotulo(t), "cor": EV_COR.get(t, "#64748b"), "n": n} for t, n in tipos.items()]
            ctx["cal"] = cal.montar(mes_ref, chips, host_id="ev-cal",
                                    nav_url="/ui/eventos/conteudo?vista=calendario",
                                    min_mes=min_mes, max_mes=max_mes, hoje=date.today(), legenda=legenda)
        else:
            ctx["cal"] = None
    else:
        titulo, sub, novo, delacao = META["eventos"]
        ctx.update(dados_tabela(db, "eventos"))
        ctx["novo_label"] = novo
        # item 19: agrupamento ano → mês → lista para a vista de operação
        ctx["eventos_ano_mes"] = _eventos_por_ano_mes(db)
    return ctx


@router.get("/eventos")
def pagina_eventos(request: Request, vista: str = "lista", mes: str | None = None,
                   db: Session = Depends(get_db)):
    return render(request, db, "eventos.html", "eventos", **_ctx_eventos(db, vista, mes))


@router.get("/eventos/conteudo")
def eventos_conteudo(request: Request, vista: str = "lista", mes: str | None = None,
                     db: Session = Depends(get_db)):
    from app.core.templates import templates
    ctx = _ctx_eventos(db, vista, mes)
    # a navegação do calendário troca só o #ev-cal; a aba troca o #eventos-conteudo
    tpl = "partials/_cal.html" if (vista == "calendario" and mes) else "partials/eventos_conteudo.html"
    return templates.TemplateResponse(request, tpl, ctx)


# Estágios (as 3 abas) é a superfície de LEITURA → `consulta.py`.


# ============================ Histórico ============================
def _ctx_historico(db: Session, ano: int | None):
    from sqlalchemy import select
    from app.models.enums import StatusCiclo
    from app.models.operacao import Historico
    from app.routers.ui.alunos_op import dados_matriculados
    from app.services.common import get_ciclo_ativo
    hist = db.scalars(select(Historico)).all()
    ciclo = get_ciclo_ativo(db)
    ano_corr = ciclo.data_inicio.year if (ciclo and ciclo.status == StatusCiclo.em_andamento) else None
    anos = sorted({h.ano for h in hist} | ({ano_corr} if ano_corr else set()), reverse=True)
    sel = ano if (ano in anos) else (anos[0] if anos else None)
    ctx = {"anos": anos, "ano_sel": sel, "ano_corr": ano_corr}
    if sel is not None and sel == ano_corr:
        ctx["modo"] = "corrente"
        ctx["linhas"] = dados_matriculados(db, "todos")
    else:
        egr = [h for h in hist if h.ano == sel]
        ctx["modo"] = "egressos"
        ctx["egressos"] = [{
            "id": h.id, "nome": h.aluno_nome, "matricula": h.matricula,
            "conc": sum(1 for a in (h.areas or []) if a.get("data_conclusao")),
            "total": len(h.areas or []), "carga": h.carga_horaria_total,
            "completo": h.situacao.value == "ciclo_completo",
            "encerramento": h.encerramento,
        } for h in egr]
    return ctx


# ============================ Remanejar ============================
@router.get("/remanejar")
def pagina_remanejar(request: Request, db: Session = Depends(get_db)):
    from app.services.common import get_ciclo_ativo
    from app.routers.ui.escala import ctx_remanejar
    ciclo = get_ciclo_ativo(db)
    if ciclo is None:
        return render(request, db, "remanejar.html", "remanejar",
                      pendente=False, fila=[], resumo=None)
    return render(request, db, "remanejar.html", "remanejar", **ctx_remanejar(db, ciclo))
