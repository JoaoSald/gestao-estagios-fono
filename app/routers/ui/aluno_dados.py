"""Dados do detalhe do aluno + calendário de encontros (tradução de aluno.js)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area
from app.models.enums import StatusAlocacao, StatusMatricula
from app.models.escala import Alocacao, Sessao
from app.services import aluno as aluno_service
from app.services.common import fase_do_aluno, get_ciclo_ativo
from app.services.matricula import area_pre_requisito, pre_requisito_concluido
from app.services.motor import encontros

_LABEL = {
    "a_iniciar": "não faz neste ciclo", "aguardando": "aguardando vaga",
    "em_andamento": "em andamento", "em_risco": "em risco",
    "concluida": "concluída", "interrompida": "interrompida", "incompleta": "incompleta",
}


def montar_aluno(db: Session, aluno_id: int) -> dict:
    from app.routers.ui.painel_dados import _estado_matricula
    aluno = aluno_service.obter_model(db, aluno_id)
    ciclo = get_ciclo_ativo(db)
    fim = ciclo.data_fim if ciclo else None
    fase = fase_do_aluno(aluno.semestre)

    # "Áreas do currículo" = TODAS as áreas leaf da fase do aluno (matriculadas ou não),
    # espelhando areasDaFase/progressoAluno do versao_2. As não-matriculadas aparecem como
    # "não faz neste ciclo"; áreas compostas entram pelas sub-áreas (rótulo "Mãe · Sub").
    amap = {a.id: a for a in db.scalars(select(Area)).all()}
    fase5 = fase == fase.__class__._7
    leaf = [a for a in amap.values()
            if not a.composta and (a.pre_requisito if fase5 else not a.pre_requisito)]
    leaf.sort(key=lambda a: ((amap[a.area_mae_id].nome if a.area_mae_id in amap else a.nome), a.nome))
    mat_por_area = {m.area_id: m for m in aluno.matriculas}

    areas_info = []
    concluidas = enrolled = 0
    soma_pct = 0
    motivos = []
    for area in leaf:
        mae_nome = amap[area.area_mae_id].nome if (area.area_mae_id and area.area_mae_id in amap) else None
        m = mat_por_area.get(area.id)
        if m is None:  # aluno não cursa esta área neste ciclo
            areas_info.append({
                "area_id": area.id, "area_nome": area.nome, "mae_nome": mae_nome,
                "area_cor": area.cor or "#64748b", "estado": "a_iniciar",
                "label": "Não faz neste ciclo", "feitos": 0, "total": 0, "pct": 0,
                "meta": "não faz neste ciclo", "pode_interromper": False,
            })
            continue
        enrolled += 1
        est = _estado_matricula(db, m, fim) if fim else "aguardando"
        cont = encontros.contar_encontros(db, m)
        total = cont["total"] or 0
        pct = 100 if est == "concluida" else (round(cont["feitos"] / total * 100) if total else 0)
        soma_pct += pct
        if est == "concluida":
            concluidas += 1
            meta = f"concluída em {m.data_conclusao.strftime('%d/%m/%Y')}" if m.data_conclusao else "concluída"
        elif est == "interrompida":
            meta = "interrompida" + (f" · {m.motivo_interrupcao}" if m.motivo_interrupcao else "")
        elif est == "aguardando":
            meta = "aguardando vaga (fila / próximo ciclo)"
            motivos.append(f"<b>{area.nome}</b> — aguardando vaga neste ciclo")
        elif m.data_conclusao_prevista:
            meta = f"previsão: {m.data_conclusao_prevista.strftime('%d/%m/%Y')}"
            if est == "em_risco":
                motivos.append(f"<b>{area.nome}</b> — conclusão prevista {m.data_conclusao_prevista.strftime('%d/%m/%Y')}, depois do fim do ciclo")
        else:
            meta = "—"
        areas_info.append({
            "area_id": area.id, "area_nome": area.nome, "mae_nome": mae_nome,
            "area_cor": area.cor or "#64748b",
            "estado": est, "label": _LABEL.get(est, est),
            "feitos": cont["feitos"], "total": total, "pct": pct, "meta": meta,
            "pode_interromper": est in ("em_andamento", "em_risco"),
        })

    hoje = date.today()
    dias_rest = max(0, (fim - hoje).days) if fim else 0
    pct_carga = round(soma_pct / enrolled) if enrolled else 0
    pr = area_pre_requisito(db)
    return {
        "aluno": aluno, "fase": fase.value,
        "iniciais": "".join(w[0] for w in aluno.nome.split()[:2]).upper(),
        "areas_info": areas_info, "concluidas": concluidas, "total_areas": enrolled,
        "pct_carga": pct_carga, "dias_rest": dias_rest,
        "risco": bool(motivos), "motivos": motivos,
        "pre_req_nome": pr.nome if pr else None,
        "pre_req_ok": pre_requisito_concluido(db, aluno_id),
        "mostra_pre_req": fase == fase.__class__._9_10 and pr is not None,
    }


def montar_encontros(db: Session, aluno_id: int, mes: str | None):
    """Resumo por área + calendário mensal (sessões coloridas por área + eventos bloqueantes)."""
    from datetime import timedelta
    from app.models.calendario import Evento
    from app.routers.ui import calendario as cal
    aluno = aluno_service.obter_model(db, aluno_id)
    ciclo = get_ciclo_ativo(db)
    alocs = db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == aluno_id, Alocacao.status != StatusAlocacao.cancelada)).all()

    resumo = []
    chips: dict[date, list] = {}
    for a in alocs:
        lc = a.local
        ar = db.get(Area, lc.area_id) if lc else None
        cor = ar.cor if ar else "#64748b"
        mat = db.get(Matricula, a.matricula_id)
        cont = encontros.contar_encontros(db, mat) if mat else {"total": 0, "feitos": 0}
        pct = round(cont["feitos"] / cont["total"] * 100) if cont["total"] else 0
        resumo.append({"area_nome": ar.nome if ar else "—", "cor": cor,
                       "feitos": cont["feitos"], "total": cont["total"], "pct": pct,
                       "concluida": bool(mat and mat.status == StatusMatricula.concluida)})
        for s in db.scalars(select(Sessao).where(Sessao.alocacao_id == a.id)).all():
            chips.setdefault(s.data, []).append({
                "kind": "sess", "label": ar.nome if ar else "", "cor": cor,
                "esmaece": s.status.value != "cumprida"})

    # eventos bloqueantes como cal-ev
    if ciclo:
        for e in db.scalars(select(Evento).where(Evento.ciclo_id == ciclo.id, Evento.bloqueia_estagio.is_(True))).all():
            d = e.data_inicio
            while d <= e.data_fim:
                chips.setdefault(d, []).append({"kind": "ev", "label": e.nome, "cor": None})
                d += timedelta(days=1)

    min_mes = ciclo.data_inicio.strftime("%Y-%m") if ciclo else "2026-01"
    max_mes = ciclo.data_fim.strftime("%Y-%m") if ciclo else "2026-12"
    mes_ref = mes or cal.mes_inicial(min_mes, max_mes, date.today())
    cal_ctx = cal.montar(mes_ref, chips, host_id="enc-cal",
                         nav_url=f"/ui/alunos/{aluno_id}/encontros-cal",
                         min_mes=min_mes, max_mes=max_mes, hoje=date.today())
    return {"aluno": aluno, "resumo": resumo, "cal": cal_ctx}
