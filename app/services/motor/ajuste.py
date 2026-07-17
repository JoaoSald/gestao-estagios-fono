"""Ajuste manual da escala (§5) — a saída do motor é uma SUGESTÃO editável.

Toda operação recalcula as 4 restrições duras ANTES de aplicar. Se violaria, o sistema
NÃO executa: devolve o motivo exato e sugere a caixa viável mais cedo (§5.3) — sem
override. As colocações manuais nascem FIXAS (`fixado`/`travada`), então sobrevivem à
regeração (§5; decisão §4).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflito, DomainError, NaoEncontrado
from app.models.aluno import Aluno, Matricula, RestricaoAlunoLocal
from app.models.enums import StatusAlocacao
from app.models.escala import Alocacao, GrupoAluno
from app.models.local import Local
from app.services import common
from app.services.motor import calendario, estado
from app.services.motor.molde import Caixa
from app.services.motor.restricoes import viola_restricoes


@dataclass
class ResultadoAjuste:
    ok: bool
    motivos: list[str] = field(default_factory=list)
    sugestao: dict | None = None


def _bloqueados(db: Session, aluno_id: int) -> set[int]:
    return {
        r.local_id for r in db.scalars(
            select(RestricaoAlunoLocal).where(RestricaoAlunoLocal.aluno_id == aluno_id)
        ).all()
    }


def _sugerir(mv: estado.MoldeVivo, area_id: int, comp: list[Caixa], bloq: set[int]) -> dict | None:
    candidatos = sorted(mv.por_area(area_id), key=lambda t: t[1].data_inicio)
    for gid, cx in candidatos:
        if cx.tem_vaga() and viola_restricoes(comp, cx, bloq) is None:
            return {"grupo_id": gid, "onda": cx.onda, "data_inicio": cx.data_inicio.isoformat()}
    return None


def _carregar(db: Session, aluno_id: int) -> tuple[Aluno, estado.MoldeVivo]:
    aluno = common.obter_ou_404(db, Aluno, aluno_id, "Aluno")
    ctx = calendario.carregar_contexto(db, aluno.ciclo)
    return aluno, estado.carregar_molde_vivo(db, aluno.ciclo, ctx)


def _caixa(mv: estado.MoldeVivo, grupo_id: int, rotulo: str) -> Caixa:
    cx = mv.caixas.get(grupo_id)
    if cx is None:
        raise NaoEncontrado(f"{rotulo} não encontrado(a).")
    return cx


def mover(db: Session, aluno_id: int, grupo_origem: int, grupo_destino: int) -> ResultadoAjuste:
    aluno, mv = _carregar(db, aluno_id)
    origem = _caixa(mv, grupo_origem, "Grupo de origem")
    destino = _caixa(mv, grupo_destino, "Grupo de destino")
    if origem.area_id != destino.area_id:
        raise DomainError("Só é possível mover o aluno para uma caixa da MESMA área.")
    if aluno_id not in origem.ocupantes:
        raise DomainError("O aluno não está no grupo de origem.")

    comp = mv.compromissos(aluno_id, excluir_grupo=grupo_origem)
    bloq = _bloqueados(db, aluno_id)
    motivos: list[str] = []
    if not destino.tem_vaga():
        motivos.append(f"grupo cheio ({len(destino.ocupantes)}/{destino.capacidade})")
    m = viola_restricoes(comp, destino, bloq)
    if m:
        motivos.append(m)
    if motivos:
        return ResultadoAjuste(False, motivos, _sugerir(mv, destino.area_id, comp, bloq))

    mat = estado.matricula_de(db, aluno_id, destino.area_id)
    estado.levantar(db, aluno_id, origem.local.id, grupo_origem)
    estado.sentar(db, aluno_id, destino, grupo_destino, mat.id, fixado=True)
    common.registrar_atividade(db, aluno.ciclo, f"{aluno.nome} movido de grupo ({destino.local.campo}).")
    common.commit(db, "Não foi possível mover o aluno.")
    return ResultadoAjuste(True)


def adicionar_da_fila(db: Session, aluno_id: int, grupo_id: int) -> ResultadoAjuste:
    aluno, mv = _carregar(db, aluno_id)
    destino = _caixa(mv, grupo_id, "Grupo")
    if any(destino.area_id == cx.area_id for cx in mv.compromissos(aluno_id)):
        raise Conflito("O aluno já está alocado nesta área — use Mover.")
    mat = estado.matricula_de(db, aluno_id, destino.area_id)
    if mat is None:
        raise DomainError("O aluno não cursa esta área.")

    comp = mv.compromissos(aluno_id)
    bloq = _bloqueados(db, aluno_id)
    motivos: list[str] = []
    if not destino.tem_vaga():
        motivos.append(f"grupo cheio ({len(destino.ocupantes)}/{destino.capacidade})")
    m = viola_restricoes(comp, destino, bloq)
    if m:
        motivos.append(m)
    if motivos:
        return ResultadoAjuste(False, motivos, _sugerir(mv, destino.area_id, comp, bloq))

    estado.sentar(db, aluno_id, destino, grupo_id, mat.id, fixado=True)
    common.registrar_atividade(db, aluno.ciclo, f"{aluno.nome} adicionado da fila ({destino.local.campo}).")
    common.commit(db, "Não foi possível adicionar o aluno.")
    return ResultadoAjuste(True)


def remover(db: Session, aluno_id: int, grupo_id: int) -> ResultadoAjuste:
    aluno, mv = _carregar(db, aluno_id)
    caixa = _caixa(mv, grupo_id, "Grupo")
    if aluno_id not in caixa.ocupantes:
        raise DomainError("O aluno não está neste grupo.")
    estado.levantar(db, aluno_id, caixa.local.id, grupo_id)
    common.registrar_atividade(db, aluno.ciclo, f"{aluno.nome} removido do grupo ({caixa.local.campo}) — vaga liberada.")
    common.commit(db, "Não foi possível remover o aluno.")
    return ResultadoAjuste(True)


def substituir(
    db: Session, aluno_a: int, grupo_a: int, aluno_b: int, grupo_b: int,
) -> ResultadoAjuste:
    _, mv = _carregar(db, aluno_a)
    ca = _caixa(mv, grupo_a, "Grupo A")
    cb = _caixa(mv, grupo_b, "Grupo B")
    if aluno_a not in ca.ocupantes or aluno_b not in cb.ocupantes:
        raise DomainError("Cada aluno precisa estar no seu grupo de origem.")
    if grupo_a == grupo_b:
        raise DomainError("Os grupos precisam ser diferentes.")

    bloq_a, bloq_b = _bloqueados(db, aluno_a), _bloqueados(db, aluno_b)
    comp_a = mv.compromissos(aluno_a, excluir_grupo=grupo_a)
    comp_b = mv.compromissos(aluno_b, excluir_grupo=grupo_b)
    motivos: list[str] = []
    ma = viola_restricoes(comp_a, cb, bloq_a)  # A vai para a caixa de B
    mb = viola_restricoes(comp_b, ca, bloq_b)  # B vai para a caixa de A
    if ma:
        motivos.append(f"A: {ma}")
    if mb:
        motivos.append(f"B: {mb}")
    if motivos:
        return ResultadoAjuste(False, motivos)

    mat_a = estado.matricula_de(db, aluno_a, cb.area_id)
    mat_b = estado.matricula_de(db, aluno_b, ca.area_id)
    estado.levantar(db, aluno_a, ca.local.id, grupo_a)
    estado.levantar(db, aluno_b, cb.local.id, grupo_b)
    estado.sentar(db, aluno_a, cb, grupo_b, mat_a.id, fixado=True)
    estado.sentar(db, aluno_b, ca, grupo_a, mat_b.id, fixado=True)
    aluno = common.obter_ou_404(db, Aluno, aluno_a, "Aluno")
    common.registrar_atividade(db, aluno.ciclo, "Alunos trocados de grupo (substituição 1-a-1).")
    common.commit(db, "Não foi possível substituir os alunos.")
    return ResultadoAjuste(True)


def concluir_grupo(db: Session, local_id: int) -> int:
    """Conclui os alunos ATIVOS de um local (§8.5 'concluir grupo') e libera as vagas.

    Marca a matrícula como concluída (data de hoje) e a alocação como concluída. Devolve
    quantos foram concluídos. Espelha `concluirGrupoLocal` do protótipo.
    """
    from datetime import date
    from app.models.aluno import Aluno
    from app.models.enums import StatusMatricula
    local = db.get(Local, local_id)
    alocs = db.scalars(select(Alocacao).where(
        Alocacao.local_id == local_id, Alocacao.status == StatusAlocacao.ativa)).all()
    n = 0
    hoje = date.today()
    for a in alocs:
        m = db.get(Matricula, a.matricula_id)
        if m is not None and m.status != StatusMatricula.concluida:
            m.status = StatusMatricula.concluida
            m.data_conclusao = m.data_conclusao_prevista or hoje
        a.status = StatusAlocacao.concluida
        n += 1
    ciclo = db.get(Aluno, alocs[0].aluno_id).ciclo if alocs else None
    if ciclo is not None:
        common.registrar_atividade(db, ciclo, f"Grupo concluído em {local.campo if local else local_id} — {n} aluno(s), vagas liberadas.")
    common.commit(db, "Não foi possível concluir o grupo.")
    return n


def travar(db: Session, grupo_id: int, aluno_id: int, valor: bool) -> None:
    """Alterna o pin de um membro (§5; decisão §4): protege o ajuste manual da re-simulação."""
    ga = db.scalars(select(GrupoAluno).where(
        GrupoAluno.grupo_id == grupo_id, GrupoAluno.aluno_id == aluno_id
    )).first()
    if ga is None:
        raise NaoEncontrado("Membro do grupo não encontrado.")
    ga.fixado = valor
    for a in db.scalars(select(Alocacao).where(Alocacao.aluno_id == aluno_id)).all():
        grupo = ga.grupo
        if a.local_id == grupo.local_id:
            a.travada = valor
    common.commit(db, "Não foi possível travar/destravar.")
