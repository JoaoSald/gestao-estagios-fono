"""Estágios (SÓ visualização, 3 abas) + ações de operação (§8.5) e Remanejar (§7.3).

Nenhuma geração aqui: gerar é no bootstrap; o Remanejar aplica o reajuste PONTUAL das
pendências de infraestrutura (revisar impacto → aplicar só o afetado), nunca regera o
ciclo. Espelha estagios.js.
"""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.templates import templates
from app.routers.ui import calendario as calmod
from app.routers.ui import estagios_dados as ed
from app.routers.ui.deps import exigir_operacao, exigir_sessao
from app.services import common
from app.services.motor import ajuste

router = APIRouter(prefix="/ui", tags=["ui-escala"],
                   dependencies=[Depends(exigir_sessao), Depends(exigir_operacao)])


def _intervalo_meses(ciclo):
    return ciclo.data_inicio.strftime("%Y-%m"), ciclo.data_fim.strftime("%Y-%m")


def _cal_campo(db, ciclo, campo, mes_ref):
    """Monta o calendário (dados) da visão Por campo."""
    min_mes, max_mes = _intervalo_meses(ciclo)
    mes_ref = mes_ref or calmod.mes_inicial(min_mes, max_mes, date.today())
    chips = ed.chips_por_campo(db, ciclo, campo["local"])
    return calmod.montar(mes_ref, chips, host_id="campo-cal",
                         nav_url=f"/ui/estagios/campo-cal?local={campo['local_sel']}",
                         min_mes=min_mes, max_mes=max_mes, hoje=date.today())


def _ctx_conteudo(db: Session, vista: str, local: str | None, area: str | None,
                  mes: str | None, fase: str = "todos") -> dict:
    ciclo = common.exigir_ciclo_ativo(db)
    ctx: dict = {"vista": vista, "fase": fase, **ed.contexto_base(db)}
    if vista == "aluno":
        ctx["por_aluno"] = ed.dados_por_aluno(db, ciclo, fase)
    elif vista == "grupos":
        # area=None → dados_grupos pré-seleciona a 1ª área (item 9); "todas" mostra tudo.
        ctx["grupos"] = ed.dados_grupos(db, ciclo, area)
    else:
        campo = ed.dados_por_campo(db, ciclo, int(local) if local else None)
        ctx["campo"] = campo
        if campo:
            ctx["cal"] = _cal_campo(db, ciclo, campo, mes)
    return ctx


@router.get("/estagios/conteudo")
def conteudo(request: Request, vista: str = "aluno", local: str | None = None,
             area: str | None = None, mes: str | None = None, fase: str = "todos",
             db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "partials/estagios_conteudo.html",
                                      _ctx_conteudo(db, vista, local, area, mes, fase))


@router.get("/estagios/campo-cal")
def campo_cal(request: Request, local: int, mes: str | None = None, db: Session = Depends(get_db)):
    ciclo = common.exigir_ciclo_ativo(db)
    campo = ed.dados_por_campo(db, ciclo, local)
    return templates.TemplateResponse(request, "partials/_cal.html", {"cal": _cal_campo(db, ciclo, campo, mes)})


def ctx_remanejar(db: Session, ciclo) -> dict:
    """Contexto do Remanejar (§7.3): lista de pendências (fila) + PREVIEW do impacto
    (dry-run `simular_impacto`, sem persistir). Usado no modal e na página."""
    from sqlalchemy import select
    from app.models.operacao import FilaRemanejo
    from app.services.motor import eventos_ciclo
    fila = db.scalars(select(FilaRemanejo).where(FilaRemanejo.ciclo_id == ciclo.id)
                      .order_by(FilaRemanejo.id.desc())).all()
    resumo = eventos_ciclo.simular_impacto(db, ciclo)
    pendente = bool(ciclo.escala_desatualizada or resumo.tem_mudanca())
    return {"pendente": pendente, "fila": fila, "resumo": resumo}


@router.get("/remanejar-modal")
def remanejar_modal(request: Request, db: Session = Depends(get_db)):
    ciclo = common.exigir_ciclo_ativo(db)
    return templates.TemplateResponse(request, "partials/remanejar_modal.html",
                                      ctx_remanejar(db, ciclo))


@router.post("/remanejar/aplicar")
def remanejar_aplicar(request: Request, db: Session = Depends(get_db)):
    from fastapi import Response
    from app.services.motor import eventos_ciclo
    ciclo = common.exigir_ciclo_ativo(db)
    eventos_ciclo.aplicar_pendencias(db, ciclo)  # PONTUAL — não regera o ciclo (§7.3)
    resp = Response(status_code=204)
    resp.headers["HX-Redirect"] = "/ui/estagios"
    return resp


@router.post("/estagios/concluir-grupo")
async def concluir_grupo(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    local_id = int(form["local_id"])
    n = ajuste.concluir_grupo(db, local_id)
    resp = templates.TemplateResponse(request, "partials/estagios_conteudo.html",
                                      _ctx_conteudo(db, "campo", str(local_id), None, None))
    resp.headers["HX-Trigger"] = json.dumps({"toast": {"msg": f"Grupo concluído — {n} aluno(s), vagas liberadas.", "tipo": "success"}})
    return resp


# ============================ Ações manuais (§9): mover / remover / adicionar ============================
def _conteudo_ok(request: Request, db: Session, vista: str, local, area, msg: str):
    """Re-renderiza o conteúdo da aba + fecha o modal + toast de sucesso."""
    resp = templates.TemplateResponse(request, "partials/estagios_conteudo.html",
                                      _ctx_conteudo(db, vista, local or None, area or None, None))
    resp.headers["HX-Trigger"] = json.dumps({"fechar-modal": True, "toast": {"msg": msg, "tipo": "success"}})
    return resp


def _modal(request: Request, tpl: str, ctx: dict):
    return templates.TemplateResponse(request, tpl, ctx)


def _rebuild_mover_modal(request, db, ciclo, vista, aluno_id, grupo_origem, ctx_local, ctx_area, r):
    from app.models.escala import Grupo
    if vista == "grupos":
        g0 = db.get(Grupo, grupo_origem)
        d = ed.destinos_mover_onda(db, ciclo, aluno_id, g0.local_id) if g0 else None
        descricao = "Escolha a leva (grupo) para onde mover."
    else:
        d = ed.destinos_mover_campo(db, ciclo, aluno_id, grupo_origem)
        descricao = "Escolha o local (mesma área) para onde mover."
    resp = _modal(request, "partials/mover_modal.html",
                  {"d": d, "descricao": descricao, "vista": vista, "ctx_local": ctx_local,
                   "ctx_area": ctx_area, "motivos": r.motivos, "sugestao": r.sugestao})
    resp.headers["HX-Retarget"] = "#modal-root"
    resp.headers["HX-Reswap"] = "innerHTML"
    return resp


@router.get("/estagios/mover-campo-modal")
def mover_campo_modal(request: Request, aloc: int, db: Session = Depends(get_db)):
    from app.models.escala import Alocacao
    ciclo = common.exigir_ciclo_ativo(db)
    a = db.get(Alocacao, aloc)
    aluno_id = a.aluno_id if a else None
    grupo_origem = ed.grupo_do_aluno_no_local(db, ciclo, a.local_id).get(aluno_id) if a else None
    d = ed.destinos_mover_campo(db, ciclo, aluno_id, grupo_origem)
    return _modal(request, "partials/mover_modal.html",
                  {"d": d, "descricao": "Escolha o local (mesma área) para onde mover.",
                   "vista": "campo", "ctx_local": a.local_id if a else "", "ctx_area": "",
                   "motivos": None, "sugestao": None})


@router.get("/estagios/mover-onda-modal")
def mover_onda_modal(request: Request, aluno: int, local: int, area: str | None = None,
                     db: Session = Depends(get_db)):
    ciclo = common.exigir_ciclo_ativo(db)
    d = ed.destinos_mover_onda(db, ciclo, aluno, local)
    return _modal(request, "partials/mover_modal.html",
                  {"d": d, "descricao": "Escolha a leva (grupo) para onde mover.",
                   "vista": "grupos", "ctx_local": "", "ctx_area": area or "",
                   "motivos": None, "sugestao": None})


@router.get("/estagios/adicionar-modal")
def adicionar_modal(request: Request, local: int, db: Session = Depends(get_db)):
    ciclo = common.exigir_ciclo_ativo(db)
    d = ed.fila_para_adicionar(db, ciclo, local)
    return _modal(request, "partials/adicionar_modal.html", {"d": d, "motivos": None})


@router.post("/estagios/mover")
async def estagios_mover(request: Request, db: Session = Depends(get_db)):
    from app.core.errors import DomainError
    ciclo = common.exigir_ciclo_ativo(db)
    form = await request.form()
    aluno_id = int(form["aluno_id"]); go = int(form["grupo_origem"]); gd = int(form["grupo_destino"])
    vista = form.get("vista", "campo"); local = form.get("local"); area = form.get("area")
    try:
        r = ajuste.mover(db, aluno_id, go, gd)
    except DomainError as exc:
        r = ajuste.ResultadoAjuste(False, [exc.mensagem])
    if r.ok:
        return _conteudo_ok(request, db, vista, local, area, "Aluno movido.")
    return _rebuild_mover_modal(request, db, ciclo, vista, aluno_id, go, local, area, r)


@router.post("/estagios/remover")
async def estagios_remover(request: Request, db: Session = Depends(get_db)):
    from app.core.errors import DomainError
    form = await request.form()
    aluno_id = int(form["aluno_id"]); grupo_id = int(form["grupo_id"])
    vista = form.get("vista", "campo"); local = form.get("local"); area = form.get("area")
    try:
        ajuste.remover(db, aluno_id, grupo_id)
        return _conteudo_ok(request, db, vista, local, area, "Aluno removido — vaga liberada.")
    except DomainError as exc:
        resp = templates.TemplateResponse(request, "partials/estagios_conteudo.html",
                                          _ctx_conteudo(db, vista, local or None, area or None, None))
        resp.headers["HX-Trigger"] = json.dumps({"toast": {"msg": exc.mensagem, "tipo": "error"}})
        return resp


@router.post("/estagios/adicionar")
async def estagios_adicionar(request: Request, db: Session = Depends(get_db)):
    from app.core.errors import DomainError
    ciclo = common.exigir_ciclo_ativo(db)
    form = await request.form()
    aluno_id = int(form["aluno_id"]); grupo_id = int(form["grupo_id"]); local = form.get("local")
    try:
        r = ajuste.adicionar_da_fila(db, aluno_id, grupo_id)
    except DomainError as exc:
        r = ajuste.ResultadoAjuste(False, [exc.mensagem])
    if r.ok:
        return _conteudo_ok(request, db, "campo", local, "", "Aluno adicionado ao local.")
    d = ed.fila_para_adicionar(db, ciclo, int(local))
    resp = _modal(request, "partials/adicionar_modal.html", {"d": d, "motivos": r.motivos})
    resp.headers["HX-Retarget"] = "#modal-root"
    resp.headers["HX-Reswap"] = "innerHTML"
    return resp
