"""Parciais HTMX de CRUD (alunos, docentes, preceptores, afastamentos, locais, eventos).

Cada handler chama o service da FASE 3 e devolve um FRAGMENTO de HTML (tabela ou form),
não JSON. Padrão único por recurso, despachado pelo path param `recurso`.
"""
from __future__ import annotations

import json
import unicodedata
from datetime import date, time

from fastapi import APIRouter, Depends, Form, Request
from markupsafe import Markup, escape
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import DomainError
from app.core.templates import templates
from app.models.catalogo import Area
from app.models.enums import DiaSemana, FaseArea, StatusMatricula, TipoAfastamento, TipoEvento, Turno
from app.routers.ui.deps import contexto_shell, exigir_sessao
from app.schemas.afastamento import AfastamentoCreate
from app.schemas.aluno import AlunoCreate, AlunoUpdate, MatriculaItem
from app.schemas.area import AreaCreate, AreaUpdate
from app.schemas.docente import DocenteCreate, DocenteUpdate
from app.schemas.evento import EventoCreate, EventoUpdate
from app.schemas.local import LocalConfigCampo, LocalCreate, LocalUpdate
from app.schemas.preceptor import PreceptorCreate, PreceptorUpdate
from app.services import (
    afastamento as afastamento_service,
    aluno as aluno_service,
    area as area_service,
    common,
    docente as docente_service,
    evento as evento_service,
    local as local_service,
    preceptor as preceptor_service,
)

router = APIRouter(prefix="/ui", tags=["ui-cadastros"], dependencies=[Depends(exigir_sessao)])

VALIDOS = {"alunos", "docentes", "preceptores", "afastamentos", "locais", "eventos", "areas"}
FORM_TEMPLATE = {
    "alunos": "partials/form_aluno.html",
    "docentes": "partials/form_docente.html",
    "preceptores": "partials/form_preceptor.html",
    "afastamentos": "partials/form_afastamento.html",
    "locais": "partials/form_local.html",
    "eventos": "partials/form_evento.html",
    "areas": "partials/form_area.html",
}

META = {
    "alunos": ("Alunos", "Alunos do ciclo — prioridade, matrículas e restrições.", "Novo aluno", "remover"),
    "docentes": ("Docentes", "Catálogo permanente (soft-delete).", "Novo docente", "desativar"),
    "preceptores": ("Preceptores", "Responsáveis de campo externos (AR-1).", "Novo preceptor", "desativar"),
    "afastamentos": ("Afastamentos", "Ausências de docente/preceptor no ciclo.", "Novo afastamento", "remover"),
    "locais": ("Locais", "Slots (campo · dia · turno) ofertados no ciclo.", "Novo local", "desativar"),
    "eventos": ("Eventos", "Calendário do ciclo — feriados/recessos que bloqueiam estágio.", "Novo evento", "remover"),
    "areas": ("Áreas", "Catálogo permanente — simples, compostas e sub-áreas.", "Nova área", "remover"),
}


def _norm(s) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower())
                   if unicodedata.category(c) != "Mn")


def _match(q: str, *campos) -> bool:
    if not q:
        return True
    alvo = " ".join(_norm(c) for c in campos)
    return _norm(q) in alvo


def _pill(txt: str, cor: str) -> str:
    return (f'<span class="badge" style="background:color-mix(in srgb,{cor} 18%,transparent);'
            f'color:{cor};border:1px solid color-mix(in srgb,{cor} 40%,transparent)">{escape(txt)}</span>')


def label_area(area, areas_map) -> str:
    """Rótulo "Mãe - Sub" para sub-áreas (espelha nomeComMae do versao_2); simples = nome."""
    if area.area_mae_id and area.area_mae_id in areas_map:
        return f"{areas_map[area.area_mae_id].nome} - {area.nome}"
    return area.nome


def _area_pill(nome: str, cor: str | None) -> Markup:
    c = cor or "#64748b"
    return Markup(f'<span class="area-pill" style="background:{c}22;color:{c}">'
                  f'<span class="dt" style="background:{c}"></span>{escape(nome)}</span>')


# Paleta de cores auto-atribuídas a áreas novas (o form do versao_2 não tem seletor de cor).
_PALETA_AREA = ["#14b8a6", "#0ea5e9", "#f97316", "#8b5cf6", "#ec4899",
                "#f43f5e", "#eab308", "#10b981", "#6366f1", "#06b6d4"]


def _proxima_cor_area(db: Session) -> str:
    """Cor distinta para a próxima área (cicla a paleta pelo total de áreas-mãe existentes)."""
    n = db.scalar(select(func.count()).select_from(Area).where(Area.area_mae_id.is_(None))) or 0
    return _PALETA_AREA[n % len(_PALETA_AREA)]


_IC_CALOFF = ('<span class="ic"><svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" '
              'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M8 2v4M16 2v4M3 10h18"/><rect x="3" y="4" width="18" height="18" rx="2"/>'
              '<path d="m9 15 6 -6"/></svg></span>')


# ----------------------------- Linhas (tabela) -----------------------------
def dados_tabela(db: Session, recurso: str, q: str | None = None) -> dict:
    """(colunas, itens, del_acao) para a página e o parcial de busca."""
    itens: list[dict] = []
    if recurso == "docentes":
        colunas = ["Nome", "E-mail", "Status"]
        for d in docente_service.listar(db):
            if not _match(q, d.nome, d.email):
                continue
            status = _pill("ativo", "var(--st-concluida)") if d.ativo else _pill("desligado", "var(--st-interrompida)")
            itens.append({"id": d.id, "cells": [escape(d.nome), escape(d.email or "—"), Markup(status)]})
    elif recurso == "preceptores":
        colunas = ["Nome", "E-mail", "Status"]
        for p in preceptor_service.listar(db):
            if not _match(q, p.nome, p.email):
                continue
            status = _pill("ativo", "var(--st-concluida)") if p.ativo else _pill("desligado", "var(--st-interrompida)")
            itens.append({"id": p.id, "cells": [escape(p.nome), escape(p.email), Markup(status)]})
    elif recurso == "eventos":
        colunas = ["Evento", "Período", "Tipo", "Estágio"]
        for e in evento_service.listar(db):
            if not _match(q, e.nome, e.tipo.value):
                continue
            periodo = f"{e.data_inicio.strftime('%d/%m')}–{e.data_fim.strftime('%d/%m')}"
            bloq = _pill("bloqueia", "var(--st-risco)") if e.bloqueia_estagio else _pill("não bloqueia", "var(--st-iniciar)")
            itens.append({"id": e.id, "cells": [escape(e.nome), periodo, escape(e.tipo.value), Markup(bloq)]})
    elif recurso == "afastamentos":
        colunas = ["Pessoa", "Tipo", "Motivo", "Período"]
        docs = {d.id: d.nome for d in docente_service.listar(db)}
        precs = {p.id: p.nome for p in preceptor_service.listar(db)}
        for a in afastamento_service.listar(db):
            nome = docs.get(a.docente_id) if a.docente_id else precs.get(a.preceptor_id, "?")
            papel = _pill("docente", "var(--st-andamento)") if a.docente_id else _pill("preceptor", "var(--st-iniciar)")
            if not _match(q, nome, a.tipo.value, a.motivo or ""):
                continue
            dias = (a.data_retorno - a.data_inicio).days + 1
            periodo = (f"{a.data_inicio.strftime('%d/%m/%Y')} → {a.data_retorno.strftime('%d/%m/%Y')}"
                       f"<div class='hint'>{dias} dia(s)</div>")
            itens.append({"id": a.id, "cells": [
                Markup(f"<b>{escape(nome)}</b> {papel}"), Markup(_pill(a.tipo.value, "var(--text-3)")),
                escape(a.motivo or "—"), Markup(periodo)], "editavel": False})
    elif recurso == "locais":
        from app.models.catalogo import Docente, Preceptor
        from app.models.enums import StatusAlocacao
        from app.models.escala import Alocacao
        from app.models.local import IndisponibilidadeLocal
        colunas = ["Área", "Campo / Docente", "Unidade", "Quando", "Ocupação", "Status"]
        areas = {a.id: a for a in db.scalars(select(Area)).all()}
        docs = {d.id: d.nome for d in db.scalars(select(Docente)).all()}
        for l in local_service.listar(db):
            ar = areas.get(l.area_id)
            an = label_area(ar, areas) if ar else "?"
            if not _match(q, l.campo, an, l.dia_semana.value):
                continue
            doc = docs.get(l.docente_id, "")
            prec = ""
            if l.preceptor_id:
                prec = docs.get(l.preceptor_id, "") if l.preceptor_tipo == "docente" \
                    else (db.get(Preceptor, l.preceptor_id).nome if db.get(Preceptor, l.preceptor_id) else "")
            uso = db.scalar(select(func.count()).select_from(Alocacao).where(
                Alocacao.local_id == l.id, Alocacao.status == StatusAlocacao.ativa)) or 0
            indisp = db.scalar(select(func.count()).select_from(IndisponibilidadeLocal).where(
                IndisponibilidadeLocal.local_id == l.id)) or 0
            campo = (f"<b>{escape(l.campo)}</b><div class='hint'>{escape(doc)}"
                     + (f" · <span class='dim'>preceptor:</span> {escape(prec)}" if prec else "") + "</div>")
            status = _pill("ativo", "var(--st-concluida)") if l.ativo else _pill("inativo", "var(--st-interrompida)")
            if indisp:
                status += " " + _pill(f"{indisp} indisp.", "var(--st-risco)")
            acoes = (f'<button class="icon-btn" title="Indisponibilidade" hx-get="/ui/locais/{l.id}/indisponibilidade"'
                     f' hx-target="#modal-root" hx-swap="innerHTML">{_IC_CALOFF}</button>')
            itens.append({"id": l.id, "cells": [
                _area_pill(an, ar.cor if ar else None), Markup(campo),
                escape(l.unidade or "—"),
                f"{l.dia_semana.value} · {l.turno.value} · {l.hora_inicio.strftime('%H:%M')}–{l.hora_fim.strftime('%H:%M')}",
                f"{uso}/{l.capacidade} vagas", Markup(status)], "acoes_html": Markup(acoes)})
    elif recurso == "alunos":
        colunas = ["Aluno", "Matrícula", "Sem.", "Prioridade", "Áreas"]
        for al in aluno_service.listar(db):
            if not _match(q, al.nome, al.matricula):
                continue
            n_mats = len([m for m in al.matriculas if m.status == StatusMatricula.em_andamento])
            link = f'<a href="/ui/alunos/{al.id}" style="color:var(--primary);font-weight:600">{escape(al.nome)}</a>'
            chk = ("checked" if al.prioridade else "")
            prio = (f'<label class="check {"on" if al.prioridade else ""}" style="margin:0;padding:.15rem .5rem">'
                    f'<input type="checkbox" {chk} hx-post="/ui/alunos/{al.id}/prioridade" hx-trigger="change" hx-swap="none">'
                    f'<span>prioridade</span></label>')
            itens.append({"id": al.id, "cells": [Markup(link), escape(al.matricula),
                          str(al.semestre or "—"), Markup(prio), str(n_mats)]})
    elif recurso == "areas":
        colunas = ["Área", "Carga", "Fase", "Tipo"]
        amap = {a.id: a for a in area_service.listar(db)}
        for a in area_service.listar(db):
            tipo = "composta" if a.composta else ("sub-área" if a.area_mae_id else "simples")
            if not _match(q, a.nome, tipo):
                continue
            # Item 7: pílula colorida cobrindo "Mãe - Sub" inteiro (padrão de Locais),
            # herdando a cor da mãe quando a sub-área não tem cor própria.
            cor = a.cor or (amap[a.area_mae_id].cor if a.area_mae_id in amap else None)
            pill = _area_pill(label_area(a, amap), cor)
            prereq = " <span class='badge b-iniciar'>pré-req</span>" if a.pre_requisito else ""
            itens.append({"id": a.id, "cells": [
                Markup(f"{pill}{prereq}"), f"{a.carga_exigida}h", a.fase.value, tipo]})
    else:
        colunas = []
    return {"recurso": recurso, "colunas": colunas, "itens": itens, "del_acao": META[recurso][3]}


def dados_alunos(db: Session) -> dict:
    """Alunos separados por FASE (7 / 9_10), com contagem de matrículas — espelha alunos.js."""
    from app.services.common import fase_do_aluno
    fase7, fase910 = [], []
    for al in aluno_service.listar(db):
        mats = al.matriculas
        row = {
            "id": al.id, "nome": al.nome, "matricula": al.matricula, "email": al.email,
            "semestre": al.semestre, "prioridade": al.prioridade,
            "em_and": sum(1 for m in mats if m.status == StatusMatricula.em_andamento),
            "conc": sum(1 for m in mats if m.status == StatusMatricula.concluida),
        }
        (fase7 if fase_do_aluno(al.semestre).value == "7" else fase910).append(row)
    return {"fase7": fase7, "fase910": fase910}


def _render_linhas(request: Request, db: Session, recurso: str, q: str | None = None):
    if recurso == "alunos":
        # bootstrap (rascunho) = seções por fase; operação (em_andamento) = tabela rica.
        from app.models.enums import StatusCiclo
        from app.routers.ui.alunos_op import ctx_op
        from app.services.common import get_ciclo_ativo
        ciclo = get_ciclo_ativo(db)
        if ciclo is not None and ciclo.status == StatusCiclo.em_andamento:
            return templates.TemplateResponse(request, "partials/alunos_op_conteudo.html", ctx_op(db))
        return templates.TemplateResponse(request, "partials/alunos_conteudo.html", dados_alunos(db))
    ctx = dados_tabela(db, recurso, q)
    resp = templates.TemplateResponse(request, "partials/linhas.html", ctx)
    return resp


def _ok(resp, msg: str):
    resp.headers["HX-Trigger"] = json.dumps({"fechar-modal": True, "toast": {"msg": msg, "tipo": "success"}})
    return resp


# ---- Bootstrap etapa 3: área/local re-renderizam a seção da própria etapa ----
def _no_bootstrap(request: Request) -> bool:
    """True quando a ação foi disparada de dentro do wizard (/ui/bootstrap)."""
    return "/bootstrap" in (request.headers.get("HX-Current-URL") or "")


def _na_pagina_eventos(request: Request) -> bool:
    """True quando a ação veio da página de operação /ui/eventos (vista agrupada, item 19)."""
    url = request.headers.get("HX-Current-URL") or ""
    return "/eventos" in url and "/bootstrap" not in url


def _evento_recarregar(recurso: str) -> str | None:
    return {"areas": "recarregar-areas", "locais": "recarregar-locais"}.get(recurso)


def _alvo_form(request: Request, recurso: str) -> str:
    """Alvo do modal por contexto. Na etapa 3 do bootstrap NÃO existe #tbody-*,
    então o modal aponta para o container da seção (senão o htmx nem envia o POST)."""
    if recurso in ("areas", "locais") and _no_bootstrap(request):
        return "#bs-areas" if recurso == "areas" else "#bs-locais"
    if recurso == "eventos" and _na_pagina_eventos(request):
        return "#eventos-conteudo"
    return f"#tbody-{recurso}"


def _render_secao3(request: Request, db: Session, recurso: str):
    """Conteúdo da etapa 3a (áreas) ou 3b (locais + slots) para re-render reativo."""
    from app.routers.ui.bootstrap import ctx_areas, ctx_locais
    if recurso == "areas":
        return templates.TemplateResponse(request, "partials/passo3a.html", ctx_areas(db))
    return templates.TemplateResponse(request, "partials/passo3b.html", ctx_locais(db))


def _render_pos_mutacao(request: Request, db: Session, recurso: str):
    """Após criar/editar área ou local: no bootstrap devolve a seção 3a/3b (atualiza
    tabela E slots); fora dele, a tabela genérica."""
    if recurso in ("areas", "locais") and _no_bootstrap(request):
        return _render_secao3(request, db, recurso)
    if recurso == "eventos" and _na_pagina_eventos(request):
        from app.routers.ui.paginas import _ctx_eventos
        return templates.TemplateResponse(request, "partials/eventos_conteudo.html",
                                          _ctx_eventos(db, "lista", None))
    return _render_linhas(request, db, recurso)


# ----------------------------- Form (modal) -----------------------------
def _areas_check(db: Session, amap: dict, leaf, semestre: int, matric: dict, is_edit: bool) -> list[dict]:
    """Checkboxes de matrícula gated por fase (§4): 7º cursa só o pré-requisito (Audiologia I);
    9/10 cursa as demais e tem o pré-requisito desabilitado. Aluno novo do 7º já vem com
    Audiologia I marcada; 9/10 começa tudo desmarcado."""
    from app.services.common import fase_do_aluno
    fase7 = fase_do_aluno(semestre).value == "7"
    out = []
    for a in leaf:
        relevante = a.pre_requisito if fase7 else (not a.pre_requisito)
        marcado = (a.id in matric) if is_edit else (fase7 and a.pre_requisito)
        out.append({
            "id": a.id, "label": label_area(a, amap), "cor": a.cor,
            "marcado": marcado, "disabled": not relevante,
            "concluida": matric.get(a.id) == StatusMatricula.concluida,
        })
    return out


def _obter(db: Session, recurso: str, id_: int):
    return {
        "docentes": docente_service.obter, "preceptores": preceptor_service.obter,
        "eventos": evento_service.obter, "locais": local_service.obter,
        "afastamentos": afastamento_service.obter, "areas": area_service.obter,
        "alunos": aluno_service.obter_model,
    }[recurso](db, id_)


def _form_ctx(db: Session, recurso: str, obj, semestre_novo: int = 9) -> dict:
    ctx: dict = {"obj": obj, "erro": ""}
    if recurso == "eventos":
        ctx["tipos"] = [(t.value, t.value) for t in TipoEvento]
    elif recurso == "afastamentos":
        pessoas = [(f"d:{d.id}", f"{d.nome} (docente)") for d in docente_service.listar(db, incluir_inativos=False)]
        pessoas += [(f"p:{p.id}", f"{p.nome} (preceptor)") for p in preceptor_service.listar(db, incluir_inativos=False)]
        ctx["pessoas"] = pessoas
        ctx["tipos"] = [(t.value, t.value) for t in TipoAfastamento]
    elif recurso == "areas":
        ctx["fases"] = [(FaseArea._9_10.value, "9º/10º (demais)"), (FaseArea._7.value, "7º (mini-ciclo)")]
        # sub-áreas geridas inline ao editar QUALQUER área (vira composta ao ganhar sub-áreas).
        subs = []
        if obj is not None:
            subs = db.scalars(select(Area).where(Area.area_mae_id == obj.id).order_by(Area.nome)).all()
        ctx["subs"] = subs
        ctx["subs_soma"] = sum(s.carga_exigida for s in subs)
    elif recurso in ("locais", "alunos"):
        leaf = db.scalars(select(Area).where(Area.composta.is_(False)).order_by(Area.nome)).all()
        ctx["areas"] = [(a.id, a.nome) for a in leaf]
        if recurso == "alunos":
            from app.models.local import Local
            from app.models.enums import StatusCiclo
            from app.services.common import fase_do_aluno, get_ciclo_ativo
            ciclo = get_ciclo_ativo(db)
            # Prioridade só faz sentido no bootstrap (marcar+arrastar na montagem);
            # no dia a dia (em_andamento) o checkbox some (item UI).
            ctx["is_bootstrap"] = bool(ciclo and ciclo.status == StatusCiclo.rascunho)
            amap = {a.id: a for a in db.scalars(select(Area)).all()}
            matric = {m.area_id: m.status for m in obj.matriculas} if obj else {}
            sem = obj.semestre if obj else semestre_novo
            ctx["semestre_default"] = sem
            # matrículas gated por fase (7º → só Audiologia I; 9/10 → Audiologia I desabilitada)
            ctx["areas_check"] = _areas_check(db, amap, leaf, sem, matric, obj is not None)
            # restrições: locais agrupados por área (leaf); disponível = marcado (padrão)
            bloq = {r.local_id for r in obj.restricoes_local} if obj else set()
            locs = db.scalars(select(Local).where(Local.ciclo_id == ciclo.id, Local.ativo.is_(True)).order_by(Local.campo)).all() if ciclo else []
            # item 9: aluno do mini-ciclo (7º) só cursa o pré-requisito (Audiologia I) →
            # mostra apenas a disponibilidade dos locais dessa área (leaf ou sub-área dela).
            if fase_do_aluno(sem).value == "7":
                prereq = {a.id for a in amap.values() if a.pre_requisito}
                prereq |= {a.id for a in amap.values() if a.area_mae_id in prereq}
                locs = [l for l in locs if l.area_id in prereq]
            grupos: dict[int, dict] = {}
            for l in locs:
                ar = amap.get(l.area_id)
                g = grupos.setdefault(l.area_id, {"label": label_area(ar, amap) if ar else "?",
                                                  "cor": ar.cor if ar else "#64748b", "locais": []})
                g["locais"].append({"id": l.id, "campo": l.campo, "dia": l.dia_semana.value,
                                    "turno": l.turno.value, "disponivel": l.id not in bloq})
            ctx["restr_areas"] = list(grupos.values())
        if recurso == "locais":
            ctx["dias"] = [(d.value, d.value) for d in DiaSemana]
            ctx["turnos"] = [(t.value, t.value) for t in Turno]
            # item 7: docentes já revisados nas etapas anteriores (select "Docente responsável")
            ctx["docentes"] = [(d.id, d.nome) for d in docente_service.listar(db, incluir_inativos=False)]
    return ctx


def _render_form(request: Request, db: Session, recurso: str, obj, erro: str = "", semestre_novo: int = 9):
    ctx = _form_ctx(db, recurso, obj, semestre_novo=semestre_novo)
    ctx["erro"] = erro
    ctx["target"] = _alvo_form(request, recurso)
    resp = templates.TemplateResponse(request, FORM_TEMPLATE[recurso], ctx)
    if erro:  # re-render dentro do modal (não na tabela)
        resp.headers["HX-Retarget"] = "#modal-root"
        resp.headers["HX-Reswap"] = "innerHTML"
    return resp


@router.get("/{recurso}/form")
def form_novo(recurso: str, request: Request, semestre: int = 9, db: Session = Depends(get_db)):
    if recurso not in VALIDOS:
        return templates.TemplateResponse(request, "partials/vazio.html", {}, status_code=404)
    return _render_form(request, db, recurso, None, semestre_novo=semestre)


@router.get("/alunos/matriculas-check")
def alunos_matriculas_check(request: Request, semestre: int = 9, aluno_id: int | None = None,
                            db: Session = Depends(get_db)):
    """Re-render reativo dos checkboxes de matrícula quando o semestre muda no form."""
    amap = {a.id: a for a in db.scalars(select(Area)).all()}
    leaf = db.scalars(select(Area).where(Area.composta.is_(False)).order_by(Area.nome)).all()
    obj = aluno_service.obter_model(db, aluno_id) if aluno_id else None
    matric = {m.area_id: m.status for m in obj.matriculas} if obj else {}
    checks = _areas_check(db, amap, leaf, semestre, matric, obj is not None)
    return templates.TemplateResponse(request, "partials/alunos_matriculas_check.html",
                                      {"areas_check": checks})


@router.get("/{recurso}/{id_}/form")
def form_editar(recurso: str, id_: int, request: Request, db: Session = Depends(get_db)):
    return _render_form(request, db, recurso, _obter(db, recurso, id_))


@router.get("/{recurso}/linhas")
def linhas(recurso: str, request: Request, q: str = "", db: Session = Depends(get_db)):
    return _render_linhas(request, db, recurso, q)


# ----------------------------- Sub-áreas inline (edição de área composta) -----------------------------
def _sincronizar_composta(db: Session, mae_id: int) -> None:
    """Uma área é composta SSE tem ≥1 sub-área (regra do §3 — composta derivada).

    COMMITA a flag: como `ctx_areas` decide simples/composta por `Area.composta`, um
    flush-sem-commit era revertido no fim do request e a área nunca aparecia como
    composta (a sub-área "sumia" do passo 3a) — causa do bug de "não reflete ao salvar".
    """
    mae = db.get(Area, mae_id)
    if mae is None:
        return
    tem_sub = db.scalar(select(func.count()).select_from(Area).where(Area.area_mae_id == mae_id)) or 0
    mae.composta = tem_sub > 0
    common.commit(db, "Não foi possível atualizar a área composta.")


@router.post("/areas/{mae_id}/subareas")
def area_add_subarea(mae_id: int, request: Request, sub_nome: str = Form(""),
                     sub_carga: int = Form(0), db: Session = Depends(get_db)):
    mae = area_service.obter(db, mae_id)
    if sub_nome.strip() and sub_carga > 0:
        try:
            area_service.criar(db, AreaCreate(nome=sub_nome.strip(), carga_exigida=sub_carga,
                                              fase=mae.fase, cor=mae.cor, area_mae_id=mae_id, composta=False))
            _sincronizar_composta(db, mae_id)  # ganhou sub-área → vira composta
        except DomainError:
            pass  # nome duplicado etc. — apenas re-renderiza o modal sem quebrar
    resp = _render_form(request, db, "areas", area_service.obter(db, mae_id))
    resp.headers["HX-Trigger"] = json.dumps({"recarregar-areas": True})  # reflete na etapa 3a
    return resp


@router.delete("/areas/{sub_id}/subarea")
def area_del_subarea(sub_id: int, request: Request, db: Session = Depends(get_db)):
    sub = area_service.obter(db, sub_id)
    mae_id = sub.area_mae_id
    try:
        area_service.remover(db, sub_id)
        if mae_id:
            _sincronizar_composta(db, mae_id)  # perdeu a última sub-área → volta a simples
    except DomainError:
        pass  # tem locais/matrículas dependentes — mantém e apenas re-renderiza
    mae = area_service.obter(db, mae_id) if mae_id else None
    resp = _render_form(request, db, "areas", mae)
    resp.headers["HX-Trigger"] = json.dumps({"recarregar-areas": True})  # reflete na etapa 3a
    return resp


# ----------------------------- Salvar (criar/editar) -----------------------------
def _salvar(db: Session, recurso: str, form, edit_id: int | None):
    """Chama o service da FASE 3. Levanta DomainError/ValueError em caso de problema."""
    g = form.get
    if recurso == "docentes":
        if edit_id:
            docente_service.atualizar(db, edit_id, DocenteUpdate(nome=g("nome"), email=g("email") or None, ativo="ativo" in form))
        else:
            docente_service.criar(db, DocenteCreate(nome=g("nome"), email=g("email") or None, ativo="ativo" in form))
    elif recurso == "preceptores":
        if edit_id:
            preceptor_service.atualizar(db, edit_id, PreceptorUpdate(nome=g("nome"), email=g("email"), ativo="ativo" in form))
        else:
            preceptor_service.criar(db, PreceptorCreate(nome=g("nome"), email=g("email"), ativo="ativo" in form))
    elif recurso == "eventos":
        payload = dict(nome=g("nome"), tipo=g("tipo"), data_inicio=g("data_inicio"),
                       data_fim=g("data_fim") or None, bloqueia_estagio="bloqueia_estagio" in form)
        if edit_id:
            evento_service.atualizar(db, edit_id, EventoUpdate(**payload))
        else:
            evento_service.criar(db, EventoCreate(**payload))
    elif recurso == "afastamentos":
        pessoa = g("pessoa") or ""
        docente_id = int(pessoa[2:]) if pessoa.startswith("d:") else None
        preceptor_id = int(pessoa[2:]) if pessoa.startswith("p:") else None
        afastamento_service.criar(db, AfastamentoCreate(
            docente_id=docente_id, preceptor_id=preceptor_id, tipo=g("tipo"),
            motivo=g("motivo") or None, data_inicio=g("data_inicio"), data_retorno=g("data_retorno")))
    elif recurso == "locais":
        hi = time.fromisoformat(g("hora_inicio"))
        hf = time.fromisoformat(g("hora_fim"))
        # item 4: horas/encontro NÃO é mais campo — deriva da janela do turno (fim − início).
        horas_sessao = round(((hf.hour * 60 + hf.minute) - (hi.hour * 60 + hi.minute)) / 60, 2)
        doc = g("docente_id")  # item 7: docente responsável escolhido no form
        payload = dict(area_id=int(g("area_id")), campo=g("campo"), unidade=g("unidade") or None,
                       dia_semana=g("dia_semana"), turno=g("turno"),
                       hora_inicio=hi, hora_fim=hf,
                       capacidade=int(g("capacidade")), carga_horaria=int(g("carga_horaria")),
                       horas_sessao=horas_sessao, docente_id=int(doc) if doc else None,
                       passagem_grupo="passagem_grupo" in form)
        if edit_id:
            local_service.atualizar(db, edit_id, LocalUpdate(**payload))
        else:
            local_service.criar(db, LocalCreate(**payload))
    elif recurso == "areas":
        carga = int(g("carga_exigida") or g("carga_horaria") or 0)
        if edit_id:
            # composta, cor e area_mae são derivados/preservados — não vêm do form.
            area_service.atualizar(db, edit_id, AreaUpdate(
                nome=g("nome"), carga_exigida=carga, fase=g("fase"),
                pre_requisito="pre_requisito" in form))
            area_id = edit_id
        else:
            # área nova nasce SIMPLES (vira composta ao ganhar sub-áreas); cor automática.
            nova = area_service.criar(db, AreaCreate(
                nome=g("nome"), carga_exigida=carga, fase=g("fase"),
                pre_requisito="pre_requisito" in form, composta=False,
                area_mae_id=None, cor=_proxima_cor_area(db)))
            area_id = nova.id
        # Item 1: sub-área digitada no form é persistida pelo Salvar principal (antes era
        # descartada — só o botão secundário "Salvar sub-área" a criava).
        sub_nome = (g("sub_nome") or "").strip()
        sub_carga = int(g("sub_carga") or 0)
        if sub_nome and sub_carga > 0:
            mae = db.get(Area, area_id)
            try:
                area_service.criar(db, AreaCreate(
                    nome=sub_nome, carga_exigida=sub_carga, fase=mae.fase, cor=mae.cor,
                    area_mae_id=area_id, composta=False))
            except DomainError:
                pass  # nome duplicado etc. — não quebra o Salvar da área
        _sincronizar_composta(db, area_id)  # reflete composta (com commit)
    elif recurso == "alunos":
        from app.models.local import Local
        from app.services.common import get_ciclo_ativo
        areas = [int(a) for a in form.getlist("area")]
        # restrições invertidas (versao_2): marcados = DISPONÍVEIS; blocklist = os NÃO marcados
        disp = {int(x) for x in form.getlist("disp")}
        ciclo = get_ciclo_ativo(db)
        ativos = db.scalars(select(Local).where(Local.ciclo_id == ciclo.id, Local.ativo.is_(True))).all() if ciclo else []
        bloq = [l.id for l in ativos if l.id not in disp]
        semestre = int(g("semestre")) if g("semestre") else None
        if edit_id:
            aluno_service.atualizar(db, edit_id, AlunoUpdate(
                nome=g("nome"), matricula=g("matricula"), email=g("email") or None,
                semestre=semestre, prioridade="prioridade" in form))
            aluno_service.sincronizar_matriculas(db, edit_id, [MatriculaItem(area_id=a) for a in areas])
            aluno_service.salvar_restricoes(db, edit_id, bloq)
        else:
            aluno_service.criar(db, AlunoCreate(
                nome=g("nome"), matricula=g("matricula"), email=g("email") or None, semestre=semestre,
                prioridade="prioridade" in form, matriculas=[MatriculaItem(area_id=a) for a in areas],
                locais_bloqueados=bloq))


def _mensagem_erro(exc: Exception) -> str:
    if isinstance(exc, DomainError):
        return exc.mensagem
    if isinstance(exc, ValidationError):
        e = exc.errors()[0]
        return e.get("msg", "Dados inválidos.")
    return "Não foi possível salvar. Verifique os dados."


@router.post("/{recurso}")
async def criar(recurso: str, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        _salvar(db, recurso, form, None)
    except (DomainError, ValidationError, ValueError) as exc:
        obj = _obter(db, recurso, int(form["id"])) if form.get("id") else None
        return _render_form(request, db, recurso, obj, _mensagem_erro(exc))
    return _ok(_render_pos_mutacao(request, db, recurso), "Registro criado.")


@router.put("/{recurso}/{id_}")
async def editar(recurso: str, id_: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    try:
        _salvar(db, recurso, form, id_)
    except (DomainError, ValidationError, ValueError) as exc:
        return _render_form(request, db, recurso, _obter(db, recurso, id_), _mensagem_erro(exc))
    return _ok(_render_pos_mutacao(request, db, recurso), "Alterações salvas.")


@router.delete("/{recurso}/{id_}")
def remover(recurso: str, id_: int, request: Request, db: Session = Depends(get_db)):
    if recurso in ("docentes", "preceptores", "locais"):
        {"docentes": docente_service.desativar, "preceptores": preceptor_service.desativar,
         "locais": local_service.desativar}[recurso](db, id_)
        msg = "Registro desativado."
    elif recurso == "eventos":
        evento_service.remover(db, id_); msg = "Evento removido."
    elif recurso == "afastamentos":
        afastamento_service.remover(db, id_); msg = "Afastamento removido."
    elif recurso == "alunos":
        aluno_service.remover(db, id_); msg = "Aluno removido."
    elif recurso == "areas":
        area_service.remover(db, id_); msg = "Área removida."
    else:
        raise DomainError("Ação de remoção não disponível para este recurso.")
    # No bootstrap (etapa 3b) o botão de lixeira aponta para #tbody-locais; devolver 204 e
    # deixar o container #bs-locais se re-renderizar via evento atualiza tabela E slots.
    if recurso in ("areas", "locais") and _no_bootstrap(request):
        from fastapi import Response
        resp = Response(status_code=204)
        resp.headers["HX-Trigger"] = json.dumps(
            {"toast": {"msg": msg, "tipo": "success"}, _evento_recarregar(recurso): True})
        return resp
    return _ok(_render_pos_mutacao(request, db, recurso), msg)


@router.post("/alunos/{aluno_id}/prioridade")
def toggle_prioridade(aluno_id: int, request: Request, db: Session = Depends(get_db)):
    al = aluno_service.obter_model(db, aluno_id)
    aluno_service.atualizar(db, aluno_id, AlunoUpdate(prioridade=not al.prioridade))
    return _ok(_render_linhas(request, db, "alunos"), "Prioridade atualizada.")


@router.post("/locais/{local_id}/config")
async def config_campo(local_id: int, request: Request, db: Session = Depends(get_db)):
    """Passo 5 do bootstrap: define docente + preceptor (polimórfico) do slot."""
    from fastapi import Response
    form = await request.form()
    doc = form.get("docente_id")
    docente_id = int(doc) if doc else None
    prec = form.get("preceptor") or ""
    ptipo = pid = None
    if prec:
        ptipo, _pid = prec.split(":", 1)
        pid = int(_pid)
    local_service.configurar_campo(
        db, local_id, LocalConfigCampo(docente_id=docente_id, preceptor_tipo=ptipo, preceptor_id=pid))
    resp = Response(status_code=204)
    resp.headers["HX-Trigger"] = json.dumps({"toast": {"msg": "Configuração salva.", "tipo": "success"}})
    return resp


@router.get("/locais/{local_id}/indisponibilidade")
def indisp_form(local_id: int, request: Request, db: Session = Depends(get_db)):
    local = local_service.obter(db, local_id)
    return templates.TemplateResponse(request, "partials/form_indisponibilidade.html",
                                      {"local": local, "erro": ""})


@router.post("/locais/{local_id}/indisponibilidade")
async def indisp_criar(local_id: int, request: Request, db: Session = Depends(get_db)):
    from app.schemas.local import IndisponibilidadeCreate
    from app.services import indisponibilidade as indisp_service
    form = await request.form()
    try:
        indisp_service.criar(db, local_id, IndisponibilidadeCreate(
            motivo=form.get("motivo") or None,
            data_inicio=form["data_inicio"], data_fim=form["data_fim"]))
    except (DomainError, ValidationError, ValueError, KeyError) as exc:
        local = local_service.obter(db, local_id)
        return templates.TemplateResponse(request, "partials/form_indisponibilidade.html",
                                          {"local": local, "erro": _mensagem_erro(exc) if not isinstance(exc, KeyError) else "Datas obrigatórias."},
                                          headers={"HX-Retarget": "#modal-root", "HX-Reswap": "innerHTML"})
    return _ok(_render_linhas(request, db, "locais"), "Indisponibilidade registrada.")


@router.post("/alunos/{aluno_id}/interromper/{area_id}")
def interromper(aluno_id: int, area_id: int, request: Request, db: Session = Depends(get_db)):
    from fastapi import Response
    from app.services import desmatricula as desmatricula_service
    desmatricula_service.desmatricular_area(db, aluno_id, area_id, None)
    resp = Response(status_code=204)
    resp.headers["HX-Redirect"] = f"/ui/alunos/{aluno_id}"  # recarrega o detalhe
    return resp
