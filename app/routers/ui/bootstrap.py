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

from app.core import passos
from app.core.database import get_db
from app.core.errors import DomainError
from app.core.templates import templates
from app.models.ciclo import Ciclo
from app.models.enums import StatusCiclo
from app.routers.ui.deps import destino_por_estado, exigir_coordenacao
from app.schemas.ciclo import CicloCreate
from app.schemas.local import LocalUpdate
from app.services import (
    analise_grade, area as area_service, ciclo as ciclo_service, docente as docente_service,
    local as local_service, preceptor as preceptor_service,
)
from app.services import common
from app.services.common import get_ciclo_ativo

router = APIRouter(prefix="/ui", tags=["ui-ciclo"], dependencies=[Depends(exigir_coordenacao)])


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
# Passos com tabela CRUD genérica — indexados pela CHAVE do passo (`core/passos.py`),
# não pelo número, para a ordem do wizard poder mudar em um só lugar.
_TABELAS_POR_PASSO = {
    "docentes": ["docentes"],
    "preceptores": ["preceptores"],
    "eventos": ["eventos"],
    "afastamentos": ["afastamentos"],
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


def ctx_locais(db: Session, ciclo: Ciclo | None = None) -> dict:
    """Contexto da etapa 6b (tabela de locais + resumo de slots + validador + análise).

    Usado no wizard e no re-render reativo (#bs-locais) após criar/editar/desativar local,
    então validador e análise da grade se atualizam junto com a tabela, de graça.
    """
    from app.routers.ui.cadastros import META, dados_tabela, label_area
    # Resumo agrupado por (ÁREA, CAMPO) — NÃO por área.
    # Dois campos da mesma área podem ter nº de encontros e capacidade diferentes
    # (Voz — Coral com 20 encontros vs. Voz — Ambulatório ORL com 16): somar tudo numa
    # linha "Voz" mostraria a capacidade de um campo com os encontros do outro. Os dias
    # do MESMO campo continuam somados — cada dia é um slot que roda em paralelo.
    areas = {a.id: a for a in area_service.listar(db)}
    resumo: dict[tuple, dict] = {}
    for l in local_service.listar(db):
        if not l.ativo:
            continue
        ar = areas.get(l.area_id)
        cor = None
        if ar is not None:  # sub-área sem cor própria herda a cor da mãe (padrão da tabela)
            cor = ar.cor or (areas[ar.area_mae_id].cor if ar.area_mae_id in areas else None)
        r = resumo.setdefault((l.area_id, l.unidade or "", l.campo), {
            "nome": label_area(ar, areas) if ar else "?", "cor": cor,
            "campo": l.campo, "unidade": l.unidade, "n": 0, "cap": 0,
            "enc_min": l.numero_encontros, "enc_max": l.numero_encontros,
        })
        r["n"] += 1
        r["cap"] += l.capacidade
        r["enc_min"] = min(r["enc_min"], l.numero_encontros)
        r["enc_max"] = max(r["enc_max"], l.numero_encontros)
    for r in resumo.values():
        # Dias do mesmo campo com nº de encontros diferente: mostra a faixa e avisa,
        # porque cada dia fecha grupos de tamanho diferente.
        r["enc"] = (str(r["enc_min"]) if r["enc_min"] == r["enc_max"]
                    else f"{r['enc_min']}–{r['enc_max']}")
        r["enc_varia"] = r["enc_min"] != r["enc_max"]
    ordenado = sorted(resumo.values(), key=lambda r: (r["nome"], r["campo"]))
    d = dados_tabela(db, "locais")
    _t, _s, _novo, _del = META["locais"]
    ctx = {"locais_resumo": ordenado, "locais_tabela": {**d, "novo_label": _novo}}
    if ciclo is None:
        ciclo = get_ciclo_ativo(db)
    if ciclo is not None:
        # Validador (só Fase 1 do motor, nada persistido) + análise da grade.
        ctx.update(analise_grade.analise_oferta(db, ciclo))
    return ctx


def _ctx_passo(db: Session, ciclo: Ciclo, passo: int, erro: str | None = None) -> dict:
    from app.routers.ui.cadastros import META, dados_alunos, dados_tabela
    ch = passos.chave(passo)
    ctx: dict = {"passo": passo, "chave": ch, "passos": passos.ROTULOS,
                 "ano": ciclo.data_inicio.year, "ciclo": ciclo, "erro": erro, "tabelas": []}
    for r in _TABELAS_POR_PASSO.get(ch, []):
        d = dados_tabela(db, r)
        titulo, sub, novo, _del = META[r]
        ctx["tabelas"].append({**d, "titulo": titulo, "sub": sub, "novo_label": novo})
    if ch == "oferta":
        # 6a — Áreas (simples + compostas); 6b — Locais + resumo de slots + validador + análise.
        ctx.update(ctx_areas(db))
        ctx.update(ctx_locais(db, ciclo))
    if ch == "alunos":
        ctx.update(dados_alunos(db))
    if ch == "campo":
        ctx["locais"] = local_service.listar(db)
        ctx["docentes"] = docente_service.listar(db, incluir_inativos=False)
        ctx["preceptores"] = preceptor_service.listar(db, incluir_inativos=False)
        ctx["areas_map"] = {a.id: a for a in area_service.listar(db)}
    if ch == "montagem":
        from app.routers.ui.montagem_dados import montar_montagem
        ctx.update(montar_montagem(db, ciclo))
    if ch == "revisao":
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
    """Re-render reativo da seção de áreas — disparado por `recarregar-areas`."""
    return templates.TemplateResponse(request, "partials/passo3a.html", ctx_areas(db))


@router.get("/bootstrap/passo3b")
def bootstrap_passo3b(request: Request, db: Session = Depends(get_db)):
    """Re-render reativo da seção de locais (tabela + slots + validador + análise) —
    disparado por `recarregar-locais`."""
    return templates.TemplateResponse(request, "partials/passo3b.html", ctx_locais(db))


# ============================ Validador de locais ============================
def _render_validador(request: Request, db: Session, toast: dict | None = None):
    """Só o bloco do validador (a tabela de locais e a análise não precisam recarregar)."""
    ciclo = common.exigir_ciclo_ativo(db)
    resp = templates.TemplateResponse(request, "partials/validador_locais.html",
                                      analise_grade.analise_oferta(db, ciclo))
    if toast:
        import json
        resp.headers["HX-Trigger"] = json.dumps({"toast": toast})
    return resp


@router.get("/bootstrap/validacao")
def validacao(request: Request, db: Session = Depends(get_db)):
    return _render_validador(request, db)


@router.post("/bootstrap/validacao/local/{local_id}/encontros")
async def validacao_encontros(local_id: int, request: Request, db: Session = Depends(get_db)):
    """Ajuste do nº de encontros direto no validador — sem voltar passos, sem gerar escala.

    Vale para o caso do espelho: o campo pede 40 encontros mas o ciclo só tem 37 datas
    viáveis; a comissão baixa para 37 e o slot volta a fechar grupo.
    """
    form = await request.form()
    bruto = (form.get("numero_encontros") or "").strip()
    try:
        n = int(bruto)
    except ValueError:
        return _render_validador(request, db,
                                 {"msg": "Informe um número de encontros válido.", "tipo": "error"})
    try:
        local_service.atualizar(db, local_id, LocalUpdate(numero_encontros=n))
    except (DomainError, ValidationError) as exc:
        msg = exc.mensagem if isinstance(exc, DomainError) else "Nº de encontros deve ser maior que zero."
        return _render_validador(request, db, {"msg": msg, "tipo": "error"})
    return _render_validador(request, db, {"msg": f"Nº de encontros salvo ({n}).", "tipo": "success"})


@router.post("/bootstrap/validacao/local/{local_id}/passagem")
def validacao_passagem(local_id: int, request: Request, db: Session = Depends(get_db)):
    """Alterna a passagem de grupo pelo validador — muda o passo entre ondas (§4), então
    pode fazer caber mais grupos no mesmo slot."""
    local = local_service.obter(db, local_id)
    local_service.atualizar(db, local_id, LocalUpdate(passagem_grupo=not local.passagem_grupo))
    return _render_validador(request, db, {"msg": "Passagem de grupo atualizada.", "tipo": "success"})


@router.get("/bootstrap/fecha-ciclo")
def bootstrap_fecha_ciclo(request: Request, db: Session = Depends(get_db)):
    """"Todos conseguem fazer o ciclo?" — verificação exata por aluno, SOB DEMANDA.

    Não entra no render normal do wizard: é uma busca por aluno (segundos no molde real),
    e a comissão pede quando quer conferir. Roda só a Fase 1 do motor, não persiste nada.
    """
    ciclo = common.exigir_ciclo_ativo(db)
    return templates.TemplateResponse(request, "partials/fecha_ciclo.html", {
        "fecha_ciclo": analise_grade.fecha_o_ciclo(db, ciclo),
    })


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


@router.get("/montagem/grade.pdf")
def montagem_grade_pdf(db: Session = Depends(get_db)) -> Response:
    """A grade das ondas por área em PDF, para levar impressa à reunião de prioridades.

    Vive no router do bootstrap (e não em `ui/exportacao.py`) porque a Montagem acontece com
    o ciclo em `rascunho` — o outro router exige `em_andamento` e redirecionaria o download.
    """
    from urllib.parse import quote

    from app.services import exportacao
    ciclo = common.exigir_ciclo_ativo(db)
    conteudo = exportacao.montagem_pdf(db, ciclo)
    nome = f"montagem_ondas_{ciclo.data_inicio.year}.pdf"
    return Response(content=conteudo, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename={nome}; "
                               f"filename*=UTF-8''{quote(nome)}",
    })


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
