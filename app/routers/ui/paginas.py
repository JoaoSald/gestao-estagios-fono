"""Páginas completas (GET) do app — server-rendered com Jinja2.

Convenção: TUDO da UI mora sob `/ui` (páginas e parciais), deixando a raiz para a API
JSON (FASES 3/4). Exceção: login/logout/home ficam na raiz por conveniência.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.templates import templates
from app.routers.ui.deps import (
    COOKIE_SESSAO, destino_por_estado, exigir_operacao, exigir_sessao, render,
)

# Auth/home na raiz (público).
auth_router = APIRouter(tags=["ui-auth"])
# Páginas internas de OPERAÇÃO sob /ui (exigem sessão + ciclo em andamento).
router = APIRouter(prefix="/ui", tags=["ui"],
                   dependencies=[Depends(exigir_sessao), Depends(exigir_operacao)])


# ============================ Login (stub — FASE 6 substitui) ============================
@auth_router.get("/login")
def login_form(request: Request):
    if request.cookies.get(COOKIE_SESSAO) == "ok":
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"titulo": "Entrar · Gestão de Estágios"})


@auth_router.post("/login")
def login_submit():
    resp = RedirectResponse("/", status_code=303)  # "/" roteia pelo estado do ciclo
    resp.set_cookie(COOKIE_SESSAO, "ok", httponly=True, samesite="lax", max_age=60 * 60 * 12)
    return resp


@auth_router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_SESSAO)
    return resp


@auth_router.get("/", dependencies=[Depends(exigir_sessao)])
def home(db: Session = Depends(get_db)):
    return RedirectResponse(destino_por_estado(db), status_code=303)


# ============================ Painel ============================
@router.get("/painel")
def painel(request: Request, db: Session = Depends(get_db)):
    from app.routers.ui.painel_dados import montar_painel
    dados = montar_painel(db)
    return render(request, db, "painel.html", "painel", **dados)


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


@router.get("/alunos/{aluno_id:int}/encontros")
def aluno_encontros(aluno_id: int, request: Request, db: Session = Depends(get_db)):
    from app.core.templates import templates
    from app.routers.ui.aluno_dados import montar_encontros
    return templates.TemplateResponse(request, "partials/encontros_modal.html", montar_encontros(db, aluno_id, None))


@router.get("/alunos/{aluno_id:int}/encontros-cal")
def aluno_encontros_cal(aluno_id: int, request: Request, mes: str | None = None, db: Session = Depends(get_db)):
    from app.core.templates import templates
    from app.routers.ui.aluno_dados import montar_encontros
    return templates.TemplateResponse(request, "partials/_cal.html", {"cal": montar_encontros(db, aluno_id, mes)["cal"]})


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
_ORIGEM_LABEL = {"manual": "Manual", "google": "Google Calendar", "api_feriados": "Feriado"}


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
                    "id": e.id, "nome": e.nome, "tipo": e.tipo.value,
                    "cor": EV_COR.get(e.tipo.value, "#64748b"),
                    "dia": e.data_inicio.day, "dow": _DOW_PT[e.data_inicio.weekday()],
                    "periodo": (f"{e.data_inicio.strftime('%d/%m')} – {e.data_fim.strftime('%d/%m')}"
                                if multi else e.data_inicio.strftime("%d/%m")),
                    "multi": bool(multi), "bloqueia": e.bloqueia_estagio,
                    "origem": _ORIGEM_LABEL.get(e.origem.value, e.origem.value),
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
            legenda = [{"label": t, "cor": EV_COR.get(t, "#64748b"), "n": n} for t, n in tipos.items()]
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


# ============================ Estágios (só visualização — 3 abas) ============================
@router.get("/estagios")
def pagina_estagios(request: Request, vista: str = "aluno", local: str | None = None,
                    area: str | None = None, mes: str | None = None, fase: str = "todos",
                    db: Session = Depends(get_db)):
    from app.routers.ui.escala import _ctx_conteudo
    dados = _ctx_conteudo(db, vista, local, area, mes, fase)
    return render(request, db, "estagios.html", "estagios", **dados)


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


@router.get("/historico")
def pagina_historico(request: Request, ano: int | None = None, db: Session = Depends(get_db)):
    return render(request, db, "historico.html", "historico", **_ctx_historico(db, ano))


@router.get("/historico/{hist_id}")
def historico_detalhe(hist_id: int, request: Request, db: Session = Depends(get_db)):
    from app.core.templates import templates
    from app.models.operacao import Historico
    h = db.get(Historico, hist_id)
    return templates.TemplateResponse(request, "partials/historico_detalhe.html", {"h": h})


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
