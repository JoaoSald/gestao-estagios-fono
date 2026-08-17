"""Dados dos passos 9 (Montagem) e 10 (Revisão & Geração) do bootstrap."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rotulos import rotulo
from app.models.aluno import Aluno, Matricula
from app.models.catalogo import Area, Docente
from app.models.ciclo import Ciclo
from app.models.enums import StatusMatricula
from app.models.escala import Grupo
from app.models.local import Local
from app.services import analise_grade
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
                "dia": rotulo(loc.dia_semana) if loc else "", "turno": rotulo(loc.turno) if loc else "",
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

    # Falta de vaga é comparada com as vagas do CICLO INTEIRO (grupos que fecham ×
    # alunos por grupo), não com uma leva. Comparar com a capacidade de uma onda
    # alertava toda área — é esperado que a turma não caiba de uma vez, ela se
    # distribui pelas ondas do ano. O que importa é: sobra alguém sem cursar no ciclo?
    val = analise_grade.validar_locais(db, ciclo)
    demanda_linhas = analise_grade.capacidade_vs_demanda(db, ciclo, val["slots"])
    for r in demanda_linhas:
        if r["saldo"] < 0 and r["slots"]:
            avisos.append(
                f"Área <b>{r['nome']}</b>: {abs(r['saldo'])} matrícula(s) sem vaga no ciclo "
                f"({r['demanda']} matriculado(s) para {r['vagas']} vaga(s) em {r['ondas']} grupo(s))."
            )

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
    if relatorio is None:
        # ANTES de gerar: o mesmo validador do passo "Áreas e Locais" como portão final —
        # afastamento cadastrado tarde ainda é pego aqui, e o ajuste do nº de encontros
        # continua a um clique (sem voltar passos). Reusa a validação já feita acima.
        ctx.update(analise_grade.analise_oferta(db, ciclo, validacao=val))
        ctx["demanda"] = demanda_linhas
        # O número que a geração vai entregar, uma rodada do motor (~0,3s). Fica no render
        # porque é o dado que faltava: os avisos acima contam VAGA, e vaga sobrando não
        # significa que todos concluem — o print da comissão tinha "2 matrículas sem vaga"
        # antes de gerar e 18 na fila depois. O "o que abrir" segue sob demanda (é caro).
        ctx["previsao"] = analise_grade.prever_geracao(db, ciclo)
    else:  # relatório = MESMA view de Grupos (espelha bootstrap.js passo 10)
        from app.routers.ui.estagios_dados import dados_grupos
        ctx["grupos"] = dados_grupos(db, ciclo, "todas")
        ctx["fechamento"] = _resumo_fechamento(db, ciclo, relatorio, alunos)
    return ctx


def _locais_perdidos(db: Session, relatorio) -> list[dict]:
    """Locais que não geraram grupo, AGRUPADOS POR ÁREA e com a cor do catálogo.

    O motor entrega `LocalSemGrupo` (fato apurado); rótulo de sub-área ("Mãe - Sub") e cor
    são resolvidos aqui, onde o catálogo está à mão — assim a lista usa a mesma pílula de
    área das demais telas em vez de um parágrafo de prosa cinza.
    """
    areas_map = {a.id: a for a in db.scalars(select(Area)).all()}
    from app.services import area as area_service
    por_area: dict[int, dict] = {}
    for p in relatorio.locais_perdidos:
        ar = areas_map.get(p.area_id)
        g = por_area.setdefault(p.area_id, {
            "nome": area_service.nome_completo(ar, areas_map) if ar else "?",
            "cor": area_service.cor_efetiva(ar, areas_map) if ar else None,
            "itens": [],
        })
        g["itens"].append(p)
    for g in por_area.values():
        g["itens"].sort(key=lambda p: (p.campo, p.dia))
    return sorted(por_area.values(), key=lambda g: g["nome"])


def _resumo_fechamento(db: Session, ciclo: Ciclo, relatorio, alunos) -> dict:
    """Dados do aviso 'nem tudo fecha' mostrado ANTES de confirmar (só informa, não trava).

    Junta o que o motor já apurou: locais que não geram grupo (capacidade perdida),
    matrículas que sobraram na fila (com nome de aluno/área e motivo) e turmas com
    conclusão prevista após o fim do ciclo (`em_risco`).
    """
    from app.services import area as area_service
    nomes = {al.id: al.nome for al in alunos}
    areas_map = {a.id: a for a in db.scalars(select(Area)).all()}
    # Nome COMPLETO ("Mãe - Sub"), o mesmo da tabela de vagas × matrículas e do diagnóstico:
    # a fila dizia "Ambulatório ORL — TAN" e a tabela "Audiologia II - Ambulatório ORL — TAN",
    # e as duas listas pareciam falar de áreas diferentes.
    areas_nome = {i: area_service.nome_completo(a, areas_map) for i, a in areas_map.items()}
    fila = [
        {"aluno": nomes.get(g.aluno_id, "?"),
         "area": areas_nome.get(g.area_id, "?"),
         "motivo": g.motivo, "tipo": g.tipo}
        for g in relatorio.aguardando
    ]
    fila.sort(key=lambda f: (f["area"], f["aluno"]))
    # agrupa a fila por área (a leitura das professoras é por área, não por aluno)
    por_area: dict[str, int] = {}
    for f in fila:
        por_area[f["area"]] = por_area.get(f["area"], 0) + 1
    fila_por_area = sorted(por_area.items(), key=lambda x: -x[1])
    # ... e por CAUSA: "sem vaga" como rótulo único era falso. O motor separa conflito de
    # horário (há vaga, o dia não serve), capacidade (grupos cheios) e área sem grupo —
    # remédios diferentes, então a tela precisa somar cada um.
    por_tipo: dict[str, int] = {}
    for f in fila:
        por_tipo[f["tipo"]] = por_tipo.get(f["tipo"], 0) + 1
    perdidos = _locais_perdidos(db, relatorio)
    return {
        "perdidos": perdidos,                       # locais sem grupo, por área (com cor)
        "n_perdidos": sum(len(g["itens"]) for g in perdidos),
        "fila": fila,
        "fila_por_area": fila_por_area,
        "fila_por_tipo": por_tipo,
        "n_conflito": por_tipo.get("conflito", 0),
        "n_capacidade": por_tipo.get("capacidade", 0),
        "n_sem_grupo": por_tipo.get("sem_grupo", 0),
        "em_risco": relatorio.em_risco,
        "tem_alerta": bool(perdidos or fila or relatorio.em_risco),
    }
