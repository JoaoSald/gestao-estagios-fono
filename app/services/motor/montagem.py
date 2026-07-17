"""Montagem dos grupos (§5) — suporte de motor para a pré-montagem manual.

A coordenação marca quem tem `prioridade` (checkbox) e ARRASTA esses alunos para as caixas
do molde vazio. Cada colocação é um PIN (`grupo_alunos.fixado=true`), validado em tempo
real pelas 4 restrições duras (+ "cursa a área"). A CH exibida é SEMANAL de pico (não a
carga total). O motor honra os pins ao gerar a escala e os preserva na regeração (§5; decisão §4).

(A tela arrastar-e-soltar é da FASE 5/8; aqui ficam os serviços/JSON.)
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models.aluno import Aluno, Matricula
from app.models.ciclo import Ciclo
from app.models.enums import StatusMatricula
from app.models.escala import Grupo, GrupoAluno
from app.services import common
from app.services.motor import calendario, estado, persistencia
from app.services.motor.ajuste import ResultadoAjuste, _bloqueados, _sugerir
from app.services.motor.restricoes import ch_pico, viola_restricoes


def materializar(db: Session, ciclo: Ciclo | None = None) -> list[Grupo]:
    """Persiste o molde vazio (todas as caixas, inclusive vazias) para a montagem."""
    ciclo = ciclo or common.exigir_ciclo_ativo(db)
    ctx = calendario.carregar_contexto(db, ciclo)
    grupos = persistencia.materializar_molde_vazio(db, ciclo, ctx)
    common.commit(db, "Não foi possível materializar o molde.")
    return grupos


def _matriculas_andamento(db: Session, aluno_id: int) -> list[Matricula]:
    return list(db.scalars(select(Matricula).where(
        Matricula.aluno_id == aluno_id, Matricula.status == StatusMatricula.em_andamento
    )).all())


def banco_prioridade(db: Session, ciclo: Ciclo | None = None) -> list[dict]:
    """Alunos de prioridade com ≥1 área ainda não pinada + sua CH semanal de pico."""
    ciclo = ciclo or common.exigir_ciclo_ativo(db)
    ctx = calendario.carregar_contexto(db, ciclo)
    mv = estado.carregar_molde_vivo(db, ciclo, ctx)
    alunos = db.scalars(select(Aluno).where(
        Aluno.ciclo_id == ciclo.id, Aluno.prioridade.is_(True)
    ).order_by(Aluno.ordenamento)).all()

    banco: list[dict] = []
    for aluno in alunos:
        pinadas = {cx.area_id for cx in mv.compromissos(aluno.id)}
        pendentes = [m.area_id for m in _matriculas_andamento(db, aluno.id) if m.area_id not in pinadas]
        if not pendentes:
            continue
        banco.append({
            "aluno_id": aluno.id, "nome": aluno.nome, "semestre": aluno.semestre,
            "ch_semanal": ch_pico(mv.compromissos(aluno.id)),
            "areas_pendentes": pendentes,
        })
    return banco


def colocar(db: Session, aluno_id: int, grupo_id: int) -> ResultadoAjuste:
    """Cria/troca o pin do aluno numa caixa (1 pin por área). Bloqueia + sugere se viola (§5.3)."""
    aluno = common.obter_ou_404(db, Aluno, aluno_id, "Aluno")
    ctx = calendario.carregar_contexto(db, aluno.ciclo)
    mv = estado.carregar_molde_vivo(db, aluno.ciclo, ctx)
    caixa = mv.caixas.get(grupo_id)
    if caixa is None:
        raise DomainError("Caixa não encontrada. Materialize o molde antes.")

    mat = estado.matricula_de(db, aluno_id, caixa.area_id)
    if mat is None or mat.status != StatusMatricula.em_andamento:
        return ResultadoAjuste(False, ["o aluno não cursa esta área"])

    # 1 pin por área: localiza o pin atual do aluno na mesma área (para trocar).
    gid_atual = next(
        (gid for gid, cx in mv.caixas.items() if cx.area_id == caixa.area_id and aluno_id in cx.ocupantes),
        None,
    )
    if gid_atual == grupo_id:
        return ResultadoAjuste(True)  # já está aqui

    comp = [cx for gid, cx in mv.caixas.items()
            if aluno_id in cx.ocupantes and cx.area_id != caixa.area_id]
    bloq = _bloqueados(db, aluno_id)
    motivos: list[str] = []
    if not caixa.tem_vaga():
        motivos.append(f"caixa cheia ({len(caixa.ocupantes)}/{caixa.capacidade})")
    m = viola_restricoes(comp, caixa, bloq)
    if m:
        motivos.append(m)
    if motivos:
        return ResultadoAjuste(False, motivos, _sugerir(mv, caixa.area_id, comp, bloq))

    if gid_atual is not None:
        antigo = db.scalars(select(GrupoAluno).where(
            GrupoAluno.grupo_id == gid_atual, GrupoAluno.aluno_id == aluno_id
        )).first()
        if antigo is not None:
            db.delete(antigo)
            db.flush()
    db.add(GrupoAluno(grupo_id=grupo_id, aluno_id=aluno_id, fixado=True))
    common.registrar_atividade(db, aluno.ciclo, f"{aluno.nome} pré-montado em {caixa.local.campo}.")
    common.commit(db, "Não foi possível colocar o aluno na caixa.")
    return ResultadoAjuste(True)


def descolocar(db: Session, aluno_id: int, grupo_id: int) -> None:
    """Remove o pin do aluno na caixa (libera a CH da semana)."""
    ga = db.scalars(select(GrupoAluno).where(
        GrupoAluno.grupo_id == grupo_id, GrupoAluno.aluno_id == aluno_id
    )).first()
    if ga is not None:
        db.delete(ga)
    common.commit(db, "Não foi possível remover o pin.")


def ch_semanal(db: Session, aluno_id: int) -> float:
    """CH de pico do aluno na montagem corrente (janelas sobrepostas)."""
    aluno = common.obter_ou_404(db, Aluno, aluno_id, "Aluno")
    ctx = calendario.carregar_contexto(db, aluno.ciclo)
    mv = estado.carregar_molde_vivo(db, aluno.ciclo, ctx)
    return ch_pico(mv.compromissos(aluno_id))
