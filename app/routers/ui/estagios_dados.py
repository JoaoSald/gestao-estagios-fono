"""Dados da tela Estágios (SÓ visualização, 3 abas) — espelha estagios.js.

Abas: por aluno (tabela), por campo (calendário + painel do cenário), grupos (ondas por
área/local). Nenhuma geração aqui — gerar é no bootstrap; reajuste pontual no Remanejar.
O status "em andamento/futuro" é derivado por DATA (§8.5), não por campo estático.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area, Docente
from app.models.ciclo import Ciclo
from app.models.enums import StatusAlocacao, StatusGrupo, StatusMatricula, StatusSessao
from app.models.escala import Alocacao, Grupo, Sessao
from app.models.local import Local
from app.services.common import get_ciclo_ativo

PALETA = ["#0ea5e9", "#f97316", "#8b5cf6", "#10b981", "#ec4899", "#f43f5e", "#eab308", "#14b8a6"]


def cor_grupo(onda: int) -> str:
    return PALETA[(onda - 1) % len(PALETA)]


def _maps(db: Session, ciclo: Ciclo):
    alunos = {a.id: a for a in db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo.id)).all()}
    areas = {a.id: a for a in db.scalars(select(Area)).all()}
    docentes = {d.id: d for d in db.scalars(select(Docente)).all()}
    locais = {l.id: l for l in db.scalars(select(Local).where(Local.ciclo_id == ciclo.id)).all()}
    return alunos, areas, docentes, locais


def _sessoes_conta(db: Session, alocacao_id: int) -> tuple[int, int]:
    total = db.scalar(select(func.count()).select_from(Sessao).where(Sessao.alocacao_id == alocacao_id)) or 0
    cumpr = db.scalar(select(func.count()).select_from(Sessao).where(
        Sessao.alocacao_id == alocacao_id, Sessao.status == StatusSessao.cumprida)) or 0
    return cumpr, total


def contexto_base(db: Session):
    ciclo = get_ciclo_ativo(db)
    n_ativas = 0
    if ciclo:
        n_ativas = db.scalar(select(func.count()).select_from(Alocacao)
                             .join(Aluno, Alocacao.aluno_id == Aluno.id)
                             .where(Aluno.ciclo_id == ciclo.id, Alocacao.status == StatusAlocacao.ativa)) or 0
    return {"ciclo": ciclo, "n_ativas": n_ativas,
            "escala_desatualizada": ciclo.escala_desatualizada if ciclo else False}


# ------------------------------- Por aluno -------------------------------
def dados_por_aluno(db: Session, ciclo: Ciclo, fase: str = "todos") -> list[dict]:
    """Item 6: agrupado por ALUNO (accordion). Inclui as áreas alocadas E as áreas
    em andamento SEM vaga (aluno matriculado que não conseguiu grupo), com o motivo.
    `fase`: 'todos' | '7' | '9_10' (filtro por semestre, item 3)."""
    from app.services.common import fase_do_aluno
    alunos, areas, docentes, locais = _maps(db, ciclo)
    por_aluno: dict[int, dict] = {}

    def _ensure(al) -> dict:
        return por_aluno.setdefault(al.id, {
            "aluno_id": al.id, "aluno_nome": al.nome, "matricula": al.matricula,
            "semestre": al.semestre, "areas": []})

    # 1. Áreas com alocação (ativa/concluída).
    vistas: set[tuple[int, int]] = set()
    alocs = db.scalars(select(Alocacao).join(Aluno, Alocacao.aluno_id == Aluno.id)
                       .where(Aluno.ciclo_id == ciclo.id, Alocacao.status != StatusAlocacao.cancelada)).all()
    for a in alocs:
        al = alunos.get(a.aluno_id)
        lc = locais.get(a.local_id)
        if not al or not lc:
            continue
        ar = areas.get(lc.area_id)
        doc = docentes.get(lc.docente_id)
        mat = db.get(Matricula, a.matricula_id)
        cumpr, total = _sessoes_conta(db, a.id)
        concluida = bool(mat and mat.status == StatusMatricula.concluida)
        situacao = "concluida" if concluida else ("em_risco" if a.data_fim_prevista > ciclo.data_fim else "em_andamento")
        _ensure(al)["areas"].append({
            "area_nome": ar.nome if ar else "?", "area_cor": ar.cor if ar else None,
            "campo": lc.campo, "docente": doc.nome if doc else "",
            "dia": lc.dia_semana.value, "turno": lc.turno.value,
            "hora_inicio": lc.hora_inicio, "hora_fim": lc.hora_fim,
            "cumpr": cumpr, "total": total, "conclusao": a.data_fim_prevista,
            "situacao": situacao, "motivo": None,
        })
        vistas.add((a.aluno_id, lc.area_id))

    # 2. Áreas em andamento SEM alocação (aguardando/sem vaga) — item 6b.
    mats = db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id)
                      .where(Aluno.ciclo_id == ciclo.id,
                             Matricula.status == StatusMatricula.em_andamento)).all()
    for m in mats:
        if (m.aluno_id, m.area_id) in vistas:
            continue
        al = alunos.get(m.aluno_id)
        ar = areas.get(m.area_id)
        if not al:
            continue
        _ensure(al)["areas"].append({
            "area_nome": ar.nome if ar else "?", "area_cor": ar.cor if ar else None,
            "campo": None, "docente": "", "dia": None, "turno": None,
            "hora_inicio": None, "hora_fim": None, "cumpr": 0, "total": 0,
            "conclusao": None, "situacao": "aguardando", "motivo": "sem vaga no ciclo",
        })

    for row in por_aluno.values():
        row["areas"].sort(key=lambda x: x["area_nome"])
        row["aguardando"] = sum(1 for x in row["areas"] if x["situacao"] == "aguardando")
    res = sorted(por_aluno.values(), key=lambda r: r["aluno_nome"])
    if fase != "todos":  # filtro por semestre (item 3)
        res = [r for r in res if fase_do_aluno(r["semestre"]).value == fase]
    return res


# ------------------------------- Grupos -------------------------------
def _sem_vaga_area(db: Session, ciclo: Ciclo, alunos: dict, area_id: int) -> list[dict]:
    """Item 9: alunos matriculados na área (em_andamento) SEM alocação ativa — não
    conseguiram vaga em nenhum grupo. Devolve {nome, ordenamento, motivo}."""
    mats = db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id).where(
        Aluno.ciclo_id == ciclo.id, Matricula.area_id == area_id,
        Matricula.status == StatusMatricula.em_andamento)).all()
    out = []
    for m in mats:
        tem = db.scalars(select(Alocacao).where(
            Alocacao.matricula_id == m.id, Alocacao.status == StatusAlocacao.ativa)).first()
        if tem:
            continue
        al = alunos.get(m.aluno_id)
        if al:
            out.append({"nome": al.nome, "ordenamento": al.ordenamento,
                        "motivo": "sem vaga viável no ciclo"})
    out.sort(key=lambda x: x["ordenamento"] or 999)
    return out


def dados_grupos(db: Session, ciclo: Ciclo, area_sel: str | None = None) -> dict:
    """area_sel: None → pré-seleciona a 1ª área (item 9); "todas" → mostra todas
    (usado pela Revisão do bootstrap, item 4); id → filtra aquela área."""
    hoje = date.today()
    alunos, areas, docentes, locais = _maps(db, ciclo)
    grupos = db.scalars(select(Grupo).where(Grupo.ciclo_id == ciclo.id)
                        .order_by(Grupo.area_id, Grupo.local_id, Grupo.onda)).all()
    por_area: dict[int, dict[int, list]] = {}
    for g in grupos:
        por_area.setdefault(g.area_id, {}).setdefault(g.local_id, []).append(g)

    ordenadas = sorted(por_area, key=lambda i: (areas[i].nome if i in areas else ""))
    if area_sel is None:  # pré-seleção: 1ª área com grupos
        area_sel = str(ordenadas[0]) if ordenadas else "todas"

    areas_lista = []
    for aid in ordenadas:
        ar = areas.get(aid)
        if area_sel != "todas" and str(aid) != str(area_sel):
            continue
        locs = []
        for lid, gs in por_area[aid].items():
            lc = locais.get(lid)
            if not lc:
                continue
            ondas = []
            for g in sorted(gs, key=lambda x: x.onda):
                membros = [{"nome": alunos[m.aluno_id].nome if m.aluno_id in alunos else "?",
                            "aluno_id": m.aluno_id, "fixado": m.fixado, "aviso": m.aviso,
                            "ordenamento": alunos[m.aluno_id].ordenamento if m.aluno_id in alunos else None}
                           for m in g.membros]
                ondas.append({
                    "onda": g.onda, "previsto": g.data_inicio > hoje,
                    "data_inicio": g.data_inicio, "data_fim": g.data_fim,
                    "cap": lc.capacidade, "ocup": len(membros), "cheia": len(membros) >= lc.capacidade,
                    "membros": membros,
                })
            locs.append({"local_id": lid, "campo": lc.campo, "unidade": lc.unidade,
                         "dia": lc.dia_semana.value, "turno": lc.turno.value,
                         "hora_inicio": lc.hora_inicio, "hora_fim": lc.hora_fim,
                         "cap": lc.capacidade, "numero_encontros": lc.numero_encontros, "ondas": ondas})
        areas_lista.append({"id": aid, "nome": ar.nome if ar else "?", "cor": ar.cor if ar else None,
                            "locais": locs, "sem_vaga": _sem_vaga_area(db, ciclo, alunos, aid)})

    # opções do filtro (todas as áreas com grupo)
    opcoes = [{"id": aid, "nome": areas[aid].nome if aid in areas else "?"}
              for aid in sorted(por_area, key=lambda i: (areas[i].nome if i in areas else ""))]
    return {"areas": areas_lista, "opcoes": opcoes, "area_sel": area_sel}


# ------------------------------- Por campo -------------------------------
def locais_com_estagio(db: Session, ciclo: Ciclo) -> list[Local]:
    ids = {a.local_id for a in db.scalars(select(Alocacao).join(Aluno, Alocacao.aluno_id == Aluno.id)
           .where(Aluno.ciclo_id == ciclo.id, Alocacao.status != StatusAlocacao.cancelada)).all()}
    return [l for l in db.scalars(select(Local).where(Local.ciclo_id == ciclo.id).order_by(Local.campo)).all()
            if l.id in ids]


def dados_por_campo(db: Session, ciclo: Ciclo, local_sel: int | None):
    from app.services.motor.calendario import horas_sessao  # noqa
    alunos, areas, docentes, locais = _maps(db, ciclo)
    with_est = locais_com_estagio(db, ciclo)
    if not with_est:
        return None
    if local_sel is None or local_sel not in {l.id for l in with_est}:
        local_sel = with_est[0].id
    local = locais.get(local_sel)
    ar = areas.get(local.area_id)
    doc = docentes.get(local.docente_id)
    alocs = db.scalars(select(Alocacao).where(
        Alocacao.local_id == local.id, Alocacao.status != StatusAlocacao.cancelada)).all()
    grupo_de = grupo_do_aluno_no_local(db, ciclo, local.id)  # aluno_id → grupo_id
    roster = []
    ini_geral = fim_geral = None
    for a in alocs:
        al = alunos.get(a.aluno_id)
        if not al:
            continue
        cumpr, total = _sessoes_conta(db, a.id)
        roster.append({"aluno_nome": al.nome, "aluno_id": al.id, "aloc_id": a.id, "travada": a.travada,
                       "grupo_id": grupo_de.get(al.id), "cumpr": cumpr, "total": total,
                       "pct": round(cumpr / total * 100) if total else 0,
                       "fim": a.data_fim_prevista, "risco": a.data_fim_prevista > ciclo.data_fim})
        ini_geral = a.data_inicio if ini_geral is None or a.data_inicio < ini_geral else ini_geral
        fim_geral = a.data_fim_prevista if fim_geral is None or a.data_fim_prevista > fim_geral else fim_geral

    # preceptor (polimórfico)
    prec_nome = None
    if local.preceptor_id:
        if local.preceptor_tipo == "docente":
            p = docentes.get(local.preceptor_id)
            prec_nome = (p.nome + " (docente)") if p else None
        else:
            from app.models.catalogo import Preceptor
            p = db.get(Preceptor, local.preceptor_id)
            prec_nome = p.nome if p else None

    opcoes = [{"id": l.id, "label": f"{(areas.get(l.area_id).nome if l.area_id in areas else '')} — {l.campo}",
               "n": len([a for a in alocs if a.local_id == l.id]) if l.id == local.id else
               (db.scalar(select(func.count()).select_from(Alocacao).where(
                   Alocacao.local_id == l.id, Alocacao.status != StatusAlocacao.cancelada)) or 0),
               "cap": l.capacidade} for l in with_est]

    return {
        "local": local, "local_sel": local_sel, "area_nome": ar.nome if ar else "?",
        "area_cor": ar.cor if ar else "#64748b", "docente": doc.nome if doc else "—",
        "preceptor": prec_nome, "roster": roster, "opcoes": opcoes,
        "ini_geral": ini_geral, "fim_geral": fim_geral,
        "vagas_livres": local.capacidade - len(roster), "ocupacao": len(roster),
    }


# ------------------------------- Ações manuais (§9) — dados dos modais -------------------------------
def grupo_do_aluno_no_local(db: Session, ciclo: Ciclo, local_id: int) -> dict[int, int]:
    """Mapeia aluno_id → grupo_id para os membros dos grupos de um local."""
    out: dict[int, int] = {}
    for g in db.scalars(select(Grupo).where(Grupo.ciclo_id == ciclo.id, Grupo.local_id == local_id)).all():
        for m in g.membros:
            out[m.aluno_id] = g.id
    return out


def _ocup_grupo(g: Grupo) -> int:
    return len(g.membros)


def destinos_mover_campo(db: Session, ciclo: Ciclo, aluno_id: int, grupo_origem: int | None) -> dict | None:
    """Para 'Mover para outro local da área': lista os grupos de OUTROS locais da mesma área."""
    g0 = db.get(Grupo, grupo_origem) if grupo_origem else None
    if g0 is None:
        return None
    alunos, areas, docentes, locais = _maps(db, ciclo)
    origem_local = locais.get(g0.local_id)
    if origem_local is None:
        return None
    # candidatos: grupos de locais DIFERENTES, mesma área — o de onda mais cedo por local
    grupos = db.scalars(select(Grupo).where(
        Grupo.ciclo_id == ciclo.id, Grupo.area_id == g0.area_id)).all()
    por_local: dict[int, list[Grupo]] = {}
    for g in grupos:
        if g.local_id != g0.local_id:
            por_local.setdefault(g.local_id, []).append(g)
    destinos = []
    for lid, gs in por_local.items():
        lc = locais.get(lid)
        if lc is None:
            continue
        g = sorted(gs, key=lambda x: x.onda)[0]
        ocup = _ocup_grupo(g)
        destinos.append({"grupo_id": g.id, "rotulo": lc.campo, "onda": g.onda,
                         "ocup": ocup, "cap": lc.capacidade, "vaga": ocup < lc.capacidade,
                         "sub": f"{lc.dia_semana.value} · {lc.turno.value} · {ocup}/{lc.capacidade}"})
    destinos.sort(key=lambda d: d["rotulo"])
    ar = areas.get(g0.area_id)
    return {"aluno_id": aluno_id, "aluno_nome": alunos[aluno_id].nome if aluno_id in alunos else "?",
            "grupo_origem": grupo_origem, "area_nome": ar.nome if ar else "?",
            "area_cor": ar.cor if ar else "#64748b", "campo_origem": origem_local.campo, "destinos": destinos}


def destinos_mover_onda(db: Session, ciclo: Ciclo, aluno_id: int, local_id: int) -> dict | None:
    """Para 'Mover para outra leva (grupo)' na aba Grupos: outras ondas do MESMO local."""
    alunos, areas, docentes, locais = _maps(db, ciclo)
    lc = locais.get(local_id)
    if lc is None:
        return None
    grupo_origem = grupo_do_aluno_no_local(db, ciclo, local_id).get(aluno_id)
    grupos = sorted(db.scalars(select(Grupo).where(
        Grupo.ciclo_id == ciclo.id, Grupo.local_id == local_id)).all(), key=lambda g: g.onda)
    destinos = []
    for g in grupos:
        if g.id == grupo_origem:
            continue
        ocup = _ocup_grupo(g)
        ini = g.data_inicio.strftime("%d/%m/%Y") if g.data_inicio else "—"
        destinos.append({"grupo_id": g.id, "rotulo": f"Grupo {g.onda}", "onda": g.onda,
                         "ocup": ocup, "cap": lc.capacidade, "vaga": ocup < lc.capacidade,
                         "sub": f"início {ini} · {ocup}/{lc.capacidade}"})
    ar = areas.get(lc.area_id)
    return {"aluno_id": aluno_id, "aluno_nome": alunos[aluno_id].nome if aluno_id in alunos else "?",
            "grupo_origem": grupo_origem, "area_nome": ar.nome if ar else "?",
            "area_cor": ar.cor if ar else "#64748b", "campo_origem": lc.campo, "destinos": destinos}


def fila_para_adicionar(db: Session, ciclo: Ciclo, local_id: int) -> dict | None:
    """Para 'Adicionar' (por campo): alunos em andamento na área SEM alocação ativa + o grupo com vaga."""
    alunos, areas, docentes, locais = _maps(db, ciclo)
    lc = locais.get(local_id)
    if lc is None:
        return None
    # grupo do local com vaga (onda mais cedo)
    grupos = sorted(db.scalars(select(Grupo).where(
        Grupo.ciclo_id == ciclo.id, Grupo.local_id == local_id)).all(), key=lambda g: g.onda)
    grupo_id = None
    for g in grupos:
        if _ocup_grupo(g) < lc.capacidade:
            grupo_id = g.id
            break
    # fila: matrículas em_andamento da área sem alocação ativa
    mats = db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id).where(
        Aluno.ciclo_id == ciclo.id, Matricula.area_id == lc.area_id,
        Matricula.status == StatusMatricula.em_andamento)).all()
    fila = []
    for m in mats:
        tem = db.scalars(select(Alocacao).where(
            Alocacao.matricula_id == m.id, Alocacao.status == StatusAlocacao.ativa)).first()
        if not tem:
            al = alunos.get(m.aluno_id)
            if al:
                fila.append({"aluno_id": al.id, "nome": al.nome, "ordenamento": al.ordenamento})
    fila.sort(key=lambda x: x["ordenamento"])
    ar = areas.get(lc.area_id)
    return {"local_id": local_id, "campo": lc.campo, "grupo_id": grupo_id,
            "area_nome": ar.nome if ar else "?", "area_cor": ar.cor if ar else "#64748b", "fila": fila}


def chips_por_campo(db: Session, ciclo: Ciclo, local: Local) -> dict[date, list[dict]]:
    """Sessões do local por dia, coloridas pela onda do aluno (aproxima o versao_2)."""
    # onda de cada aluno neste local
    onda_de = {}
    for g in db.scalars(select(Grupo).where(Grupo.ciclo_id == ciclo.id, Grupo.local_id == local.id)).all():
        for m in g.membros:
            onda_de[m.aluno_id] = g.onda
    chips: dict[date, dict[int, dict]] = {}
    alocs = db.scalars(select(Alocacao).where(
        Alocacao.local_id == local.id, Alocacao.status != StatusAlocacao.cancelada)).all()
    for a in alocs:
        onda = onda_de.get(a.aluno_id, 1)
        for s in db.scalars(select(Sessao).where(Sessao.alocacao_id == a.id)).all():
            if s.status in (StatusSessao.remanejada, StatusSessao.cancelada):
                continue
            rec = chips.setdefault(s.data, {})
            g = rec.setdefault(onda, {"kind": "sess", "cor": cor_grupo(onda), "n": 0, "cumprida": True})
            g["n"] += 1
            if s.status != StatusSessao.cumprida:
                g["cumprida"] = False
    out: dict[date, list[dict]] = {}
    for dia, ondas in chips.items():
        out[dia] = [{"kind": "sess", "label": f"G{o} ·{v['n']}", "cor": v["cor"], "esmaece": not v["cumprida"]}
                    for o, v in sorted(ondas.items())]
    return out
