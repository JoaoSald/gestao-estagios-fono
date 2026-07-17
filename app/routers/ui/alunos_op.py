"""Alunos — visão OPERACIONAL (Matriculados + Ofertas), espelha alunos.js."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area
from app.models.ciclo import Ciclo
from app.models.enums import StatusAlocacao, StatusMatricula
from app.models.escala import Alocacao
from app.models.local import Local
from app.services.common import fase_do_aluno, get_ciclo_ativo
from app.services.motor import encontros
from app.services.motor.calendario import horas_sessao


def _estado(db: Session, m: Matricula, fim) -> str:
    from app.routers.ui.painel_dados import _estado_matricula
    return _estado_matricula(db, m, fim)


def ctx_op(db: Session, vista: str = "matriculados", fase: str = "todos") -> dict:
    ctx = {"vista": vista, "fase": fase}
    if vista == "ofertas":
        ctx["ofertas"] = dados_ofertas(db)
    else:
        ctx["matriculados"] = dados_matriculados(db, fase)
    return ctx


def dados_matriculados(db: Session, fase: str = "todos") -> list[dict]:
    ciclo = get_ciclo_ativo(db)
    if ciclo is None:
        return []
    alunos = db.scalars(select(Aluno).where(Aluno.ciclo_id == ciclo.id).order_by(Aluno.ordenamento)).all()
    rows = []
    for al in alunos:
        f = fase_do_aluno(al.semestre).value
        if fase != "todos" and fase != f:
            continue
        total_areas = len(al.matriculas)
        conc = em_and = aguard = soma_f = soma_t = 0
        ch_em_and = 0.0  # item 5: horas POR ENCONTRO somadas das áreas em andamento
        risco = False
        for m in al.matriculas:
            est = _estado(db, m, ciclo.data_fim)
            cont = encontros.contar_encontros(db, m)
            soma_f += cont["feitos"]
            soma_t += cont["total"]
            if est == "concluida":
                conc += 1
            elif est == "aguardando":
                aguard += 1
            elif est in ("em_andamento", "em_risco"):
                em_and += 1
                # CH do encontro (ex.: 8:00–12:30 = 4,5h), não a carga total da área.
                aloc = db.scalars(select(Alocacao).where(
                    Alocacao.matricula_id == m.id, Alocacao.status == StatusAlocacao.ativa)).first()
                if aloc is not None:
                    loc = db.get(Local, aloc.local_id)
                    if loc is not None:
                        ch_em_and += horas_sessao(loc)
                if est == "em_risco":
                    risco = True
        rows.append({
            "id": al.id, "ordenamento": al.ordenamento, "nome": al.nome, "matricula": al.matricula,
            "semestre": al.semestre, "email": al.email,
            "pct_carga": round(soma_f / soma_t * 100) if soma_t else 0,
            "concluidas": conc, "total_areas": total_areas,
            "em_and": em_and, "ch_em_and": ch_em_and, "aguardando": aguard, "risco": risco,
        })
    return rows


def previsao_inicio_area(db: Session, area_id: int) -> dict | None:
    """Read-model (projeção, NÃO é a saída do motor): alocados + fila com previsão de início.

    Espelha `previsaoInicioArea` do versao_2: a fila entra por prioridade à medida que os
    alocados concluem e liberam vaga. Estimativa por slots (data de liberação + duração).
    """
    from datetime import date, timedelta
    ciclo = get_ciclo_ativo(db)
    if ciclo is None:
        return None
    ar = db.get(Area, area_id)
    if ar is None:
        return None
    hoje = date.today()
    base = ciclo.data_inicio if ciclo.data_inicio > hoje else hoje
    locais = db.scalars(select(Local).where(
        Local.ciclo_id == ciclo.id, Local.area_id == area_id, Local.ativo.is_(True))).all()
    local_ids = {l.id for l in locais}
    if not local_ids:
        from app.routers.ui.cadastros import label_area
        amap = {a.id: a for a in db.scalars(select(Area)).all()}
        return {"area_nome": label_area(ar, amap), "area_cor": ar.cor, "capacidade": 0,
                "ocupadas": 0, "vagas_livres": 0, "alocados": [], "fila": []}

    def _nao_concluida(a: Alocacao) -> bool:
        m = db.get(Matricula, a.matricula_id)
        return not m or m.status != StatusMatricula.concluida

    ativas = db.scalars(select(Alocacao).where(
        Alocacao.status == StatusAlocacao.ativa, Alocacao.local_id.in_(local_ids))).all()

    alocados = []
    for a in ativas:
        al = db.get(Aluno, a.aluno_id)
        m = db.get(Matricula, a.matricula_id)
        lc = db.get(Local, a.local_id)
        concluida = bool(m and m.status == StatusMatricula.concluida)
        alocados.append({
            "nome": al.nome if al else "?", "ordenamento": al.ordenamento if al else 999,
            "data_inicio": a.data_inicio, "data_fim_prevista": a.data_fim_prevista,
            "concluida": concluida, "data_conclusao": m.data_conclusao if m else None,
            "campo": lc.campo if lc else "?",
        })
    alocados.sort(key=lambda x: x["ordenamento"])

    capacidade = sum(l.capacidade for l in locais)
    ocupadas = sum(1 for a in ativas if _nao_concluida(a))
    vagas_livres = max(0, capacidade - ocupadas)

    # slots com data de liberação: ocupado libera na conclusão prevista; livre já está livre.
    slots = []
    for l in locais:
        ocup_ativos = [a for a in ativas if a.local_id == l.id and _nao_concluida(a)]
        for a in ocup_ativos:
            slots.append({"livre_em": a.data_fim_prevista or base, "semanas": l.numero_encontros or 0, "por_conclusao": True})
        for _ in range(max(0, l.capacidade - len(ocup_ativos))):
            slots.append({"livre_em": base, "semanas": l.numero_encontros or 0, "por_conclusao": False})

    # fila: matrículas em_andamento da área sem alocação ativa, por prioridade
    mats = db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id).where(
        Aluno.ciclo_id == ciclo.id, Matricula.area_id == area_id,
        Matricula.status == StatusMatricula.em_andamento)).all()
    aguardando = []
    for m in mats:
        tem = db.scalars(select(Alocacao).where(
            Alocacao.matricula_id == m.id, Alocacao.status == StatusAlocacao.ativa)).first()
        if not tem:
            al = db.get(Aluno, m.aluno_id)
            aguardando.append({"nome": al.nome if al else "?", "ordenamento": al.ordenamento if al else 999})
    aguardando.sort(key=lambda x: x["ordenamento"])

    fila = []
    for f in aguardando:
        if not slots:
            fila.append({**f, "previsao": None, "remanejamento": False, "motivo": "sem oferta ativa"})
            continue
        slots.sort(key=lambda s: s["livre_em"])
        slot = slots[0]
        entrada = base if slot["livre_em"] < base else slot["livre_em"]
        if entrada > ciclo.data_fim:
            fila.append({**f, "previsao": None, "remanejamento": False, "motivo": "sem previsão neste ciclo"})
            continue
        remanejamento = slot["por_conclusao"]
        slot["livre_em"] = entrada + timedelta(days=(slot["semanas"] or 1) * 7)
        slot["por_conclusao"] = True
        fila.append({**f, "previsao": entrada, "remanejamento": remanejamento, "motivo": None})

    from app.routers.ui.cadastros import label_area
    amap = {a.id: a for a in db.scalars(select(Area)).all()}
    return {"area_nome": label_area(ar, amap), "area_cor": ar.cor, "capacidade": capacidade,
            "ocupadas": ocupadas, "vagas_livres": vagas_livres, "alocados": alocados, "fila": fila}


def dados_ofertas(db: Session) -> list[dict]:
    ciclo = get_ciclo_ativo(db)
    if ciclo is None:
        return []
    amap = {a.id: a for a in db.scalars(select(Area)).all()}
    from app.routers.ui.cadastros import label_area
    # áreas com locais ativos
    locais = db.scalars(select(Local).where(Local.ciclo_id == ciclo.id, Local.ativo.is_(True))).all()
    por_area: dict[int, list[Local]] = {}
    for l in locais:
        por_area.setdefault(l.area_id, []).append(l)
    out = []
    for aid, ls in por_area.items():
        cap = sum(l.capacidade for l in ls)
        ocup = db.scalar(select(func.count()).select_from(Alocacao)
                         .join(Local, Alocacao.local_id == Local.id)
                         .where(Local.area_id == aid, Alocacao.status == StatusAlocacao.ativa)) or 0
        # fila = matrículas em_andamento da área sem alocação ativa
        mats = db.scalars(select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id)
                          .where(Aluno.ciclo_id == ciclo.id, Matricula.area_id == aid,
                                 Matricula.status == StatusMatricula.em_andamento)).all()
        fila = []
        for m in mats:
            tem = db.scalars(select(Alocacao).where(Alocacao.matricula_id == m.id, Alocacao.status == StatusAlocacao.ativa)).first()
            if not tem:
                al = db.get(Aluno, m.aluno_id)
                fila.append({"nome": al.nome, "ordenamento": al.ordenamento})
        livres = max(0, cap - ocup)
        if fila and livres:
            sit, cls, txt = "ociosa_fila", "b-risco", "vaga ociosa + fila · conflito de horário"
        elif fila:
            sit, cls, txt = "reprimida", "b-risco", f"{len(fila)} aguardando · sem vaga"
        elif livres:
            sit, cls, txt = "sobrando", "b-andamento", f"{livres} vaga(s) livre(s) — pode matricular"
        else:
            sit, cls, txt = "equilibrio", "b-iniciar", "✓ equilíbrio"
        ar = amap.get(aid)
        out.append({"area_id": aid, "nome": label_area(ar, amap) if ar else "?",
                    "cap": cap, "ocup": ocup, "livres": livres,
                    "fila": sorted(fila, key=lambda x: x["ordenamento"]),
                    "sit_cls": cls, "sit_txt": txt})
    out.sort(key=lambda d: d["nome"])
    return out
