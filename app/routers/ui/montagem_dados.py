"""Dados dos passos 9 (Montagem) e 10 (Revisão & Geração) do bootstrap."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area, Docente
from app.models.ciclo import Ciclo
from app.models.enums import StatusMatricula
from app.models.escala import Grupo
from app.models.local import Local
from app.services.motor import montagem


def montar_montagem(db: Session, ciclo: Ciclo) -> dict:
    """Materializa o molde vazio e monta o board (área → slot → caixas) + banco de prioridade."""
    montagem.materializar(db, ciclo)  # persiste o molde vazio (preserva pins)
    nomes = {a.id: a.nome for a in db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo.id)).all()}
    areas_map = {a.id: a for a in db.scalars(select(Area)).all()}
    areas_nome = {i: a.nome for i, a in areas_map.items()}
    locais = {l.id: l for l in db.scalars(select(Local).where(Local.ciclo_id == ciclo.id)).all()}

    grupos = db.scalars(select(Grupo).where(Grupo.ciclo_id == ciclo.id)
                        .order_by(Grupo.area_id, Grupo.local_id, Grupo.onda)).all()
    por_area: dict[int, dict[int, list]] = {}
    for g in grupos:
        loc = locais.get(g.local_id)
        cap = loc.capacidade if loc else len(g.membros)
        caixa = {
            "grupo_id": g.id, "onda": g.onda, "data_inicio": g.data_inicio, "data_fim": g.data_fim,
            "cap": cap, "ocupacao": len(g.membros), "cheia": len(g.membros) >= cap,
            "membros": [{"aluno_id": m.aluno_id, "nome": nomes.get(m.aluno_id, "?")} for m in g.membros],
        }
        por_area.setdefault(g.area_id, {}).setdefault(g.local_id, []).append(caixa)

    from app.routers.ui.cadastros import label_area
    from app.services.motor.calendario import horas_sessao
    areas = []
    for aid, locs in por_area.items():
        slots = []
        for lid, caixas in locs.items():
            loc = locais.get(lid)
            slots.append({
                "campo": loc.campo if loc else "?", "unidade": loc.unidade if loc else None,
                "enc": loc.numero_encontros if loc else "?",
                "horas": (round(horas_sessao(loc), 2) if loc else "?"),
                "dia": loc.dia_semana.value if loc else "", "turno": loc.turno.value if loc else "",
                "hora_inicio": loc.hora_inicio.strftime("%H:%M") if loc else "",
                "hora_fim": loc.hora_fim.strftime("%H:%M") if loc else "",
                "caixas": sorted(caixas, key=lambda c: c["onda"]),
            })
        _a = areas_map.get(aid)
        # fase da área (leaf ou herdada da mãe) para agrupar a montagem por semestre (item 16)
        _mae = areas_map.get(_a.area_mae_id) if (_a and _a.area_mae_id) else None
        _fase = (_mae.fase.value if _mae else (_a.fase.value if _a else "9_10"))
        areas.append({"nome": label_area(_a, areas_map) if _a else "?",
                      "cor": _a.cor if _a else "#64748b", "fase": _fase, "slots": slots})
    areas.sort(key=lambda a: a["nome"])

    return {"montagem_areas": areas, "banco": montagem.banco_prioridade(db, ciclo), "montagem_pronta": True}


def montar_revisao(db: Session, ciclo: Ciclo, relatorio=None) -> dict:
    """Avisos de completude (não impedem) + resumo. `relatorio` preenchido após Gerar."""
    avisos: list[str] = []
    locais = db.scalars(select(Local).where(Local.ciclo_id == ciclo.id, Local.ativo.is_(True))).all()
    areas_leaf = db.scalars(select(Area).where(Area.composta.is_(False))).all()
    areas_com_local = {l.area_id for l in locais}

    for ar in areas_leaf:
        # só alerta áreas com demanda (matrículas em_andamento) e sem local ativo
        dem = db.scalar(select(func.count()).select_from(Matricula)
                        .join(Aluno, Matricula.aluno_id == Aluno.id)
                        .where(Aluno.ciclo_id == ciclo.id, Matricula.area_id == ar.id,
                               Matricula.status == StatusMatricula.em_andamento)) or 0
        if dem and ar.id not in areas_com_local:
            avisos.append(f"Área <b>{ar.nome}</b> tem {dem} matrícula(s) e nenhum local ativo.")
        cap = sum(l.capacidade for l in locais if l.area_id == ar.id)
        if dem > cap and cap >= 0 and ar.id in areas_com_local:
            avisos.append(f"Área <b>{ar.nome}</b>: demanda ({dem}) maior que a capacidade total ({cap}).")

    for l in locais:
        if l.docente_id is None:
            avisos.append(f"Local <b>{l.campo}</b> ativo sem docente — defina em Configurações de campo.")

    alunos = db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo.id)).all()
    for al in alunos:
        if not al.matriculas:
            avisos.append(f"Aluno <b>{al.nome}</b> está sem matrícula.")

    resumo = {
        "alunos": len(alunos),
        "docentes": db.scalar(select(func.count()).select_from(Docente).where(Docente.ativo.is_(True))) or 0,
        "locais": len(locais),
    }
    ctx = {"avisos": avisos, "resumo": resumo, "relatorio": relatorio, "revisao_pronta": True}
    if relatorio is not None:  # relatório = MESMA view de Grupos (espelha bootstrap.js passo 10)
        from app.routers.ui.estagios_dados import dados_grupos
        ctx["grupos"] = dados_grupos(db, ciclo, "todas")
    return ctx
