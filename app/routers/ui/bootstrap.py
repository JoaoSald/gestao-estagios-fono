"""Ciclo de vida (FASE 8): welcome (abrir ciclo), wizard de bootstrap e encerrar.

Telas full-screen (sem a sidebar de operação). Exigem sessão, mas NÃO exigem ciclo em
andamento — são justamente as transições de estado.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import DomainError
from app.core.templates import templates
from app.models.ciclo import Ciclo
from app.models.enums import StatusCiclo
from app.routers.ui.deps import destino_por_estado, exigir_sessao
from app.schemas.ciclo import CicloCreate
from app.services import (
    area as area_service, ciclo as ciclo_service, docente as docente_service,
    local as local_service, preceptor as preceptor_service,
)
from app.services.common import get_ciclo_ativo

router = APIRouter(prefix="/ui", tags=["ui-ciclo"], dependencies=[Depends(exigir_sessao)])


# ============================ Welcome (abrir ciclo) ============================
def _anos_anteriores(db: Session) -> list[dict]:
    from app.models.enums import SituacaoHistorico
    from app.models.operacao import Historico
    anos: dict[int, dict] = {}
    for h in db.scalars(select(Historico)).all():
        a = anos.setdefault(h.ano, {"ano": h.ano, "egressos": 0, "completos": 0})
        a["egressos"] += 1
        if h.situacao == SituacaoHistorico.ciclo_completo:
            a["completos"] += 1
    return sorted(anos.values(), key=lambda x: x["ano"], reverse=True)


@router.get("/bem-vindo")
def bem_vindo(request: Request, db: Session = Depends(get_db)):
    if get_ciclo_ativo(db) is not None:
        return RedirectResponse(destino_por_estado(db), status_code=303)  # já há ciclo
    return templates.TemplateResponse(request, "bem_vindo.html", {
        "titulo": "Gestão de Estágios · Fonoaudiologia UFCSPA",
        "anos": _anos_anteriores(db),
    })


@router.get("/ciclos/abrir-modal")
def abrir_ciclo_modal(request: Request, db: Session = Depends(get_db)):
    ano = date.today().year
    return templates.TemplateResponse(request, "partials/abrir_ciclo_modal.html", {
        "ini": f"{ano}-03-02", "fim": f"{ano}-12-11", "erro": None,
    })


@router.post("/ciclos/abrir")
def abrir_ciclo(request: Request, db: Session = Depends(get_db),
                data_inicio: str = Form(...), data_fim: str = Form(...)):
    try:
        dados = CicloCreate(data_inicio=data_inicio, data_fim=data_fim)
        ciclo_service.abrir(db, dados)
    except (ValidationError, DomainError, ValueError) as exc:
        msg = exc.mensagem if isinstance(exc, DomainError) else "Datas inválidas: o fim deve ser posterior ao início."
        return templates.TemplateResponse(request, "partials/abrir_ciclo_modal.html", {
            "ini": data_inicio, "fim": data_fim, "erro": msg,
        }, status_code=200)
    resp = Response(status_code=204)
    resp.headers["HX-Redirect"] = "/ui/bootstrap"
    return resp


# ============================ Histórico standalone (acessível da welcome) ============================
@router.get("/historico-anteriores")
def historico_anteriores(request: Request, ano: int | None = None, db: Session = Depends(get_db)):
    from app.routers.ui.paginas import _ctx_historico
    ctx = _ctx_historico(db, ano)  # sem ciclo em andamento → modo 'egressos'
    ctx["titulo"] = "Histórico · Gestão de Estágios"
    return templates.TemplateResponse(request, "historico_anteriores.html", ctx)


@router.get("/historico-anteriores/{hist_id}")
def historico_anteriores_detalhe(hist_id: int, request: Request, db: Session = Depends(get_db)):
    from app.models.operacao import Historico
    h = db.get(Historico, hist_id)
    return templates.TemplateResponse(request, "partials/historico_detalhe.html", {"h": h})


# ============================ Wizard de bootstrap ============================
_TABELAS_POR_PASSO = {
    2: ["docentes"], 4: ["preceptores"], 6: ["afastamentos"], 8: ["eventos"],
}


def ctx_areas(db: Session) -> dict:
    """Contexto da etapa 3a (áreas simples + compostas). Usado no wizard e no
    re-render reativo (#bs-areas) após criar/editar/remover área/sub-área."""
    todas = area_service.listar(db)
    simples = [a for a in todas if not a.composta and not a.area_mae_id]
    compostas = []
    for m in [a for a in todas if a.composta]:
        subs = sorted([s for s in todas if s.area_mae_id == m.id], key=lambda s: s.nome)
        compostas.append({"mae": m, "subs": subs, "soma": sum(s.carga_exigida for s in subs)})
    return {"areas_simples": simples, "areas_compostas": compostas}


def ctx_locais(db: Session) -> dict:
    """Contexto da etapa 3b (tabela de locais + resumo de slots). Usado no wizard e
    no re-render reativo (#bs-locais) após criar/editar/desativar local."""
    from app.routers.ui.cadastros import META, dados_tabela
    # resumo de slots paralelos por sub-área (leaf) — espelha bootstrap.js passo 3b
    resumo: dict[int, dict] = {}
    for l in local_service.listar(db):
        if not l.ativo:
            continue
        ar = area_service.obter(db, l.area_id)
        r = resumo.setdefault(l.area_id, {"nome": ar.nome, "cor": ar.cor, "n": 0, "cap": 0, "enc": l.numero_encontros})
        r["n"] += 1
        r["cap"] += l.capacidade
    d = dados_tabela(db, "locais")
    _t, _s, _novo, _del = META["locais"]
    return {"locais_resumo": list(resumo.values()), "locais_tabela": {**d, "novo_label": _novo}}


def _ctx_passo(db: Session, ciclo: Ciclo, passo: int, erro: str | None = None) -> dict:
    from app.routers.ui.cadastros import META, dados_alunos, dados_tabela
    ctx: dict = {"passo": passo, "ano": ciclo.data_inicio.year, "ciclo": ciclo,
                 "erro": erro, "tabelas": []}
    for r in _TABELAS_POR_PASSO.get(passo, []):
        d = dados_tabela(db, r)
        titulo, sub, novo, _del = META[r]
        ctx["tabelas"].append({**d, "titulo": titulo, "sub": sub, "novo_label": novo})
    if passo == 3:
        # 3a — Áreas (simples + compostas); 3b — Locais + resumo de slots.
        ctx.update(ctx_areas(db))
        ctx.update(ctx_locais(db))
    if passo == 7:
        ctx.update(dados_alunos(db))
    if passo == 5:
        ctx["locais"] = local_service.listar(db)
        ctx["docentes"] = docente_service.listar(db, incluir_inativos=False)
        ctx["preceptores"] = preceptor_service.listar(db, incluir_inativos=False)
        ctx["areas_map"] = {a.id: a for a in area_service.listar(db)}
    if passo == 9:
        from app.routers.ui.montagem_dados import montar_montagem
        ctx.update(montar_montagem(db, ciclo))
    if passo == 10:
        from app.routers.ui.montagem_dados import montar_revisao
        ctx.update(montar_revisao(db, ciclo))
    return ctx


@router.get("/bootstrap")
def wizard(request: Request, db: Session = Depends(get_db)):
    ciclo = get_ciclo_ativo(db)
    if ciclo is None:
        return Redirecionar_para("/ui/bem-vindo")
    if ciclo.status == StatusCiclo.em_andamento:
        return Redirecionar_para("/ui/painel")
    if ciclo.status != StatusCiclo.rascunho:
        return Redirecionar_para("/")
    passo = ciclo.passo_bootstrap or 1
    return templates.TemplateResponse(request, "bootstrap.html", _ctx_passo(db, ciclo, passo))


@router.get("/bootstrap/passo3a")
def bootstrap_passo3a(request: Request, db: Session = Depends(get_db)):
    """Re-render reativo da etapa 3a (áreas) — disparado por `recarregar-areas`."""
    return templates.TemplateResponse(request, "partials/passo3a.html", ctx_areas(db))


@router.get("/bootstrap/passo3b")
def bootstrap_passo3b(request: Request, db: Session = Depends(get_db)):
    """Re-render reativo da etapa 3b (locais + slots) — disparado por `recarregar-locais`."""
    return templates.TemplateResponse(request, "partials/passo3b.html", ctx_locais(db))


@router.post("/bootstrap/passo/{n}")
def passo(n: int, request: Request, db: Session = Depends(get_db),
          data_inicio: str | None = Form(None), data_fim: str | None = Form(None)):
    ciclo = get_ciclo_ativo(db)
    if ciclo is None or ciclo.status != StatusCiclo.rascunho:
        return Redirecionar_para("/")
    if data_inicio and data_fim:  # veio do passo 1
        if data_fim <= data_inicio:
            ctx = _ctx_passo(db, ciclo, 1, erro="Datas inválidas: o fim deve ser posterior ao início.")
            return templates.TemplateResponse(request, "bootstrap.html", ctx)
        ciclo.data_inicio = date.fromisoformat(data_inicio)
        ciclo.data_fim = date.fromisoformat(data_fim)
        db.flush()
    ciclo_service.set_passo(db, ciclo.id, n)
    return Redirecionar_para("/ui/bootstrap")


def Redirecionar_para(destino: str) -> RedirectResponse:
    return RedirectResponse(destino, status_code=303)


# ============================ Passo 9 — Montagem (drag-drop) ============================
def _render_montagem(request: Request, db: Session, ciclo: Ciclo, toast: dict | None = None):
    from app.routers.ui.montagem_dados import montar_montagem
    resp = templates.TemplateResponse(request, "partials/montagem.html", montar_montagem(db, ciclo))
    if toast:
        import json
        resp.headers["HX-Trigger"] = json.dumps({"toast": toast})
    return resp


@router.post("/montagem/colocar")
async def montagem_colocar(request: Request, db: Session = Depends(get_db)):
    from app.services.motor import montagem
    ciclo = get_ciclo_ativo(db)
    form = await request.form()
    if not form.get("aluno_id"):
        return _render_montagem(request, db, ciclo)
    r = montagem.colocar(db, int(form["aluno_id"]), int(form["grupo_id"]))
    toast = ({"msg": "Aluno posicionado.", "tipo": "success"} if r.ok
             else {"msg": "; ".join(r.motivos), "tipo": "error"})
    return _render_montagem(request, db, ciclo, toast)


@router.post("/montagem/descolocar")
async def montagem_descolocar(request: Request, db: Session = Depends(get_db)):
    from app.services.motor import montagem
    ciclo = get_ciclo_ativo(db)
    form = await request.form()
    montagem.descolocar(db, int(form["aluno_id"]), int(form["grupo_id"]))
    return _render_montagem(request, db, ciclo, {"msg": "Aluno removido da caixa.", "tipo": "success"})


# ============================ Passo 10 — Gerar / Confirmar ============================
@router.post("/bootstrap/gerar")
def bootstrap_gerar(request: Request, db: Session = Depends(get_db)):
    from app.routers.ui.montagem_dados import montar_revisao
    from app.services.motor import escala as motor
    ciclo = get_ciclo_ativo(db)
    if ciclo is None or ciclo.status != StatusCiclo.rascunho:
        return Redirecionar_para("/")
    rel = motor.gerar_escala(db, ciclo)
    ctx = montar_revisao(db, ciclo, relatorio=rel)
    ctx["ciclo"] = ciclo
    return templates.TemplateResponse(request, "partials/revisao.html", ctx)


@router.post("/bootstrap/confirmar")
def bootstrap_confirmar(request: Request, db: Session = Depends(get_db)):
    ciclo = get_ciclo_ativo(db)
    if ciclo is None or ciclo.status != StatusCiclo.rascunho:
        return Redirecionar_para("/")
    ciclo_service.confirmar(db, ciclo.id)
    resp = Response(status_code=204)
    resp.headers["HX-Redirect"] = "/ui/painel"
    return resp


# ============================ Encerrar ciclo (3 etapas) ============================
def _montar_encerrar(db: Session, ciclo: Ciclo) -> dict:
    from app.models.aluno import Aluno
    from app.models.catalogo import Area
    from app.models.enums import StatusMatricula
    areas = {a.id: a for a in db.scalars(select(Area)).all()}
    alunos = db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo.id).order_by(Aluno.nome)).all()
    linhas, completos = [], 0
    for al in alunos:
        mats = al.matriculas
        total = len(mats)
        conc = sum(1 for m in mats if m.status == StatusMatricula.concluida)
        carga = sum((areas[m.area_id].carga_exigida if m.area_id in areas else 0)
                    for m in mats if m.status == StatusMatricula.concluida)
        faltam = [areas[m.area_id].nome for m in mats
                  if m.status in (StatusMatricula.em_andamento, StatusMatricula.incompleta) and m.area_id in areas]
        completo = total > 0 and conc == total
        if completo:
            completos += 1
        linhas.append({"nome": al.nome, "matricula": al.matricula, "conc": conc, "total": total,
                       "carga": carga, "faltam": faltam, "completo": completo})
    return {"linhas": linhas, "total_alunos": len(alunos), "completos": completos,
            "pendentes": len(alunos) - completos, "ano": ciclo.data_inicio.year}


@router.get("/encerrar")
def encerrar_view(request: Request, etapa: int = 1, db: Session = Depends(get_db)):
    ciclo = get_ciclo_ativo(db)
    if ciclo is None or ciclo.status != StatusCiclo.em_andamento:
        return Redirecionar_para("/")
    ctx = _montar_encerrar(db, ciclo)
    ctx.update(etapa=max(1, min(3, etapa)), ciclo=ciclo, erro=None)
    return templates.TemplateResponse(request, "encerrar.html", ctx)


@router.post("/ciclos/encerrar")
def encerrar_do(request: Request, db: Session = Depends(get_db), ano: str = Form(...)):
    ciclo = get_ciclo_ativo(db)
    if ciclo is None or ciclo.status != StatusCiclo.em_andamento:
        return Redirecionar_para("/")
    try:
        ciclo_service.encerrar(db, ciclo.id, int(ano.strip()))
    except (DomainError, ValueError):
        ctx = _montar_encerrar(db, ciclo)
        ctx.update(etapa=3, ciclo=ciclo, erro=f"Digite exatamente {ciclo.data_inicio.year} para confirmar.")
        return templates.TemplateResponse(request, "encerrar.html", ctx)
    return Redirecionar_para("/ui/bem-vindo")
