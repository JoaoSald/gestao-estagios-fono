"""Orquestrador do motor (§4–§6) — `gerar_escala`.

Roda o pipeline grade-primeiro e persiste a sugestão de escala. Determinístico dado o
molde; a fila (`ordenamento`) e os pins decidem o conteúdo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import Conflito
from app.models.aluno import Aluno, Matricula, RestricaoAlunoLocal
from app.models.ciclo import Ciclo
from app.models.enums import StatusCiclo, StatusMatricula, TipoAtividade
from app.models.operacao import Atividade, FilaRemanejo
from app.services import common
from app.services.motor import calendario, consolidacao, encontros, molde, persistencia, preenchimento
from app.services.motor.preenchimento import Aguardando
from app.services.ordenamento import reindex_por_prioridade


@dataclass
class Relatorio:
    total_alunos: int = 0
    alocados: int = 0            # nº de (aluno, área) colocados numa caixa
    alunos_ok: int = 0           # todas as áreas em_andamento colocadas
    alunos_parcial: int = 0      # algumas colocadas
    caixas: int = 0              # caixas do molde
    caixas_ocupadas: int = 0
    caixas_fracas: int = 0       # 0 < ocupantes < capacidade
    em_risco: int = 0            # conclusões previstas após o fim do ciclo
    aguardando: list[Aguardando] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _mapear_matriculas(db: Session, ciclo: Ciclo):
    """Devolve (areas_por_aluno, matricula_id_por) para matrículas em_andamento."""
    areas_por_aluno: dict[int, list[int]] = {}
    matricula_id: dict[tuple[int, int], int] = {}
    matriculas = db.scalars(
        select(Matricula).join(Aluno, Matricula.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id, Matricula.status == StatusMatricula.em_andamento)
    ).all()
    for m in matriculas:
        areas_por_aluno.setdefault(m.aluno_id, []).append(m.area_id)
        matricula_id[(m.aluno_id, m.area_id)] = m.id
    return areas_por_aluno, matricula_id


def _bloqueados_por_aluno(db: Session, ciclo: Ciclo) -> dict[int, set[int]]:
    bloq: dict[int, set[int]] = {}
    rows = db.scalars(
        select(RestricaoAlunoLocal).join(Aluno, RestricaoAlunoLocal.aluno_id == Aluno.id)
        .where(Aluno.ciclo_id == ciclo.id)
    ).all()
    for r in rows:
        bloq.setdefault(r.aluno_id, set()).add(r.local_id)
    return bloq


def gerar_escala(db: Session, ciclo: Ciclo | None = None) -> Relatorio:
    """Gera (Fases 1–3) e persiste a escala do ciclo. Retorna o relatório da geração."""
    if ciclo is None:
        ciclo = common.exigir_ciclo_ativo(db)
    if ciclo.status == StatusCiclo.encerrado:
        raise Conflito("Ciclo encerrado — não é possível gerar a escala.")

    # 0. Pins a preservar (§5 — rascunho manual) — capturar ANTES de qualquer wipe.
    pins = persistencia.capturar_pins(db, ciclo)

    # 1. Ordem da fila (§6.3): derivada de prioridade + matrícula.
    reindex_por_prioridade(db, ciclo.id)
    db.flush()

    alunos = list(db.scalars(
        select(Aluno).where(Aluno.ciclo_id == ciclo.id).order_by(Aluno.ordenamento)
    ).all())
    areas_por_aluno, matricula_id = _mapear_matriculas(db, ciclo)
    bloqueados = _bloqueados_por_aluno(db, ciclo)
    ctx = calendario.carregar_contexto(db, ciclo)

    # 2. Molde (Fase 1, §4) → pins (Fase 2, §5) → preenchimento + consolidação (Fase 3, §6).
    avisos: list[str] = []
    caixas = molde.materializar_molde(db, ciclo, ctx, avisos=avisos)
    compromissos: dict[int, list] = {}
    preenchimento.aplicar_pins(caixas, pins, bloqueados, compromissos)
    aguardando: list[Aguardando] = []
    preenchimento.preencher(caixas, alunos, areas_por_aluno, bloqueados, compromissos, aguardando)
    consolidacao.consolidar(caixas, bloqueados, compromissos)

    # 3. Persistir + conclusões.
    persistencia.persistir(db, ciclo, caixas, lambda a, ar: matricula_id.get((a, ar)))
    encontros.atualizar_conclusoes(db, ciclo)

    # 4. Escala em dia: apaga o banner e a fila de remanejo; registra a atividade.
    ciclo.escala_desatualizada = False
    db.execute(delete(FilaRemanejo).where(FilaRemanejo.ciclo_id == ciclo.id))
    db.add(Atividade(
        ciclo_id=ciclo.id, quando=date.today(),
        texto="Escala gerada (motor grade-primeiro).", tipo=TipoAtividade.ciclo,
    ))
    common.commit(db, "Não foi possível gerar a escala.")

    return _montar_relatorio(ciclo, alunos, caixas, areas_por_aluno, aguardando, avisos)


def _montar_relatorio(
    ciclo: Ciclo, alunos, caixas, areas_por_aluno, aguardando, avisos,
) -> Relatorio:
    rel = Relatorio(total_alunos=len(alunos), caixas=len(caixas), avisos=avisos, aguardando=aguardando)
    rel.alocados = sum(len(c.ocupantes) for c in caixas)
    rel.caixas_ocupadas = sum(1 for c in caixas if c.ocupantes)
    rel.caixas_fracas = sum(1 for c in caixas if 0 < len(c.ocupantes) < c.capacidade)
    rel.em_risco = sum(1 for c in caixas if c.ocupantes and c.data_fim > ciclo.data_fim)

    aguardando_por_aluno: dict[int, int] = {}
    for a in aguardando:
        aguardando_por_aluno[a.aluno_id] = aguardando_por_aluno.get(a.aluno_id, 0) + 1
    for aluno in alunos:
        n_areas = len(areas_por_aluno.get(aluno.id, []))
        if n_areas == 0:
            continue
        faltando = aguardando_por_aluno.get(aluno.id, 0)
        if faltando == 0:
            rel.alunos_ok += 1
        elif faltando < n_areas:
            rel.alunos_parcial += 1
    return rel
