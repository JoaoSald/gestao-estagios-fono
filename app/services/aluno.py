"""Regras de Alunos — cadastro, matrículas, restrições (blocklist) e estados (§6.3)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Conflito, DomainError, NaoEncontrado
from app.models.aluno import Aluno, Matricula, RestricaoAlunoLocal
from app.models.catalogo import Area
from app.models.ciclo import Ciclo
from app.models.enums import StatusAlocacao, StatusMatricula
from app.models.escala import Alocacao
from app.models.local import Local
from app.schemas.aluno import (
    AlunoCreate, AlunoUpdate, AlunoDetalhe, AlunoOut, MatriculaEstado,
)
from app.services import common, matricula as matricula_service
from app.services.ordenamento import reindex_por_prioridade, reindexar_ordenamento


def _email_default(matricula: str) -> str:
    return f"{matricula}@aluno.ufcspa.edu.br"


def obter_model(db: Session, aluno_id: int) -> Aluno:
    return common.obter_ou_404(db, Aluno, aluno_id, "Aluno")


def _validar_matricula_unica(db: Session, ciclo_id: int, matricula: str, ignora_id: int | None = None) -> None:
    q = select(Aluno).where(Aluno.ciclo_id == ciclo_id, Aluno.matricula == matricula)
    if ignora_id is not None:
        q = q.where(Aluno.id != ignora_id)
    outro = db.scalars(q).first()
    if outro is not None:
        raise Conflito(f"Matrícula '{matricula}' já usada por {outro.nome}.")


def validar_cobertura_local(db: Session, aluno: Aluno) -> None:
    """BLOQUEIA se alguma área matriculada `em_andamento` ficar sem ≥1 local liberado (AR-2)."""
    bloqueados = {
        r.local_id for r in db.scalars(
            select(RestricaoAlunoLocal).where(RestricaoAlunoLocal.aluno_id == aluno.id)
        ).all()
    }
    for m in aluno.matriculas:
        if m.status != StatusMatricula.em_andamento:
            continue
        locais_area = db.scalars(select(Local).where(
            Local.ciclo_id == aluno.ciclo_id,
            Local.area_id == m.area_id,
            Local.ativo.is_(True),
        )).all()
        liberados = [l for l in locais_area if l.id not in bloqueados]
        if locais_area and not liberados:
            area = db.get(Area, m.area_id)
            raise DomainError(
                f"Sem local liberado em: {area.nome}. Libere ao menos um local ou "
                "remova a matrícula."
            )


def definir_restricoes(db: Session, aluno: Aluno, locais_bloqueados: list[int]) -> None:
    """Substitui a blocklist do aluno (grava só os desmarcados). Valida cobertura."""
    ciclo_id = aluno.ciclo_id
    for local_id in locais_bloqueados:
        local = db.get(Local, local_id)
        if local is None or local.ciclo_id != ciclo_id:
            raise NaoEncontrado(f"Local {local_id} não encontrado neste ciclo.")

    # Zera e regrava (idempotente).
    for r in list(aluno.restricoes_local):
        db.delete(r)
    db.flush()
    for local_id in set(locais_bloqueados):
        db.add(RestricaoAlunoLocal(aluno_id=aluno.id, local_id=local_id))
    db.flush()
    validar_cobertura_local(db, aluno)


def criar(db: Session, dados: AlunoCreate) -> Aluno:
    ciclo = common.exigir_ciclo_ativo(db)
    _validar_matricula_unica(db, ciclo.id, dados.matricula)

    aluno = Aluno(
        ciclo_id=ciclo.id,
        nome=dados.nome,
        matricula=dados.matricula,
        email=dados.email or _email_default(dados.matricula),
        semestre=dados.semestre,
        prioridade=dados.prioridade,
        ordenamento=10_000,  # temporário; reindex_por_prioridade define o valor real
    )
    db.add(aluno)
    db.flush()

    matricula_service.sincronizar(db, aluno, dados.matriculas)
    definir_restricoes(db, aluno, dados.locais_bloqueados)
    reindex_por_prioridade(db, ciclo.id)
    # Aluno novo em operação → §8.1 (entra em caixa futura via Remanejar).
    common.registrar_pendencia_infra(db, ciclo, f"Aluno {aluno.nome} cadastrado — alocação pendente.")
    common.commit(db, "Não foi possível cadastrar o aluno.")
    db.refresh(aluno)
    return aluno


def atualizar(db: Session, aluno_id: int, dados: AlunoUpdate) -> Aluno:
    aluno = obter_model(db, aluno_id)
    campos = dados.model_dump(exclude_unset=True)
    if "matricula" in campos:
        _validar_matricula_unica(db, aluno.ciclo_id, campos["matricula"], ignora_id=aluno_id)
        # Mantém o e-mail derivado coerente se ele seguia o padrão e não foi trocado à mão.
        if not campos.get("email") and aluno.email == _email_default(aluno.matricula):
            aluno.email = _email_default(campos["matricula"])

    muda_ordem = ("prioridade" in campos and campos["prioridade"] != aluno.prioridade) or \
                 ("semestre" in campos and campos["semestre"] != aluno.semestre)
    for campo, valor in campos.items():
        setattr(aluno, campo, valor)
    if muda_ordem:
        db.flush()
        reindex_por_prioridade(db, aluno.ciclo_id)
    common.registrar_atividade(db, aluno.ciclo, f"Aluno {aluno.nome} alterado.")
    common.commit(db, "Não foi possível atualizar o aluno.")
    db.refresh(aluno)
    return aluno


def sincronizar_matriculas(db: Session, aluno_id: int, itens: list) -> list[str]:
    aluno = obter_model(db, aluno_id)
    avisos = matricula_service.sincronizar(db, aluno, itens)
    validar_cobertura_local(db, aluno)  # nova área pode não ter local liberado
    # Troca/nova área em operação → §8.1/§8.6 (entra em caixa futura via Remanejar).
    common.registrar_pendencia_infra(db, aluno.ciclo, f"Matrículas de {aluno.nome} alteradas.")
    common.commit(db, "Não foi possível salvar as matrículas.")
    return avisos


def salvar_restricoes(db: Session, aluno_id: int, locais_bloqueados: list[int]) -> None:
    aluno = obter_model(db, aluno_id)
    definir_restricoes(db, aluno, locais_bloqueados)
    common.registrar_atividade(db, aluno.ciclo, f"Restrições de local de {aluno.nome} alteradas.")
    common.commit(db, "Não foi possível salvar as restrições.")


def remover(db: Session, aluno_id: int) -> None:
    aluno = obter_model(db, aluno_id)
    ciclo = aluno.ciclo
    nome = aluno.nome
    # Cascata: matrículas e restrições do aluno.
    for m in list(aluno.matriculas):
        db.delete(m)
    db.delete(aluno)  # restricoes_local via cascade="all, delete-orphan"
    db.flush()
    reindexar_ordenamento(db, ciclo.id)
    # Vaga aberta não é gatilho (§7.2) — só registra no log.
    common.registrar_atividade(db, ciclo, f"Aluno {nome} removido — vaga liberada.")
    common.commit(db, "Não foi possível remover o aluno.")


# --- Read-model de estados derivados (§6.3) ---
def _tem_alocacao_ativa(db: Session, matricula_id: int) -> bool:
    return db.scalars(select(Alocacao).where(
        Alocacao.matricula_id == matricula_id,
        Alocacao.status == StatusAlocacao.ativa,
    )).first() is not None


def _estado(m: Matricula, ciclo: Ciclo, tem_aloc: bool) -> str:
    if m.status == StatusMatricula.concluida:
        return "concluida"
    if m.status == StatusMatricula.interrompida:
        return "interrompida"
    if m.status == StatusMatricula.incompleta:
        return "incompleta"
    # em_andamento
    if not tem_aloc:
        return "aguardando"
    if m.data_conclusao_prevista and m.data_conclusao_prevista > ciclo.data_fim:
        return "em_risco"
    return "em_andamento"


def detalhe(db: Session, aluno_id: int) -> AlunoDetalhe:
    aluno = obter_model(db, aluno_id)
    ciclo = aluno.ciclo
    fase = common.fase_do_aluno(aluno.semestre)

    estados: list[MatriculaEstado] = []
    resumo = {k: 0 for k in
              ("a_iniciar", "aguardando", "em_andamento", "em_risco",
               "concluida", "interrompida", "incompleta")}
    matriculadas_areas: set[int] = set()
    for m in sorted(aluno.matriculas, key=lambda x: x.area_id):
        area = db.get(Area, m.area_id)
        matriculadas_areas.add(m.area_id)
        est = _estado(m, ciclo, _tem_alocacao_ativa(db, m.id))
        resumo[est] += 1
        estados.append(MatriculaEstado(
            area_id=m.area_id, area_nome=area.nome if area else "?",
            status=m.status, estado=est,
            data_conclusao_prevista=m.data_conclusao_prevista,
        ))

    # a_iniciar: áreas ofertadas da fase ainda sem matrícula.
    ofertadas = matricula_service.areas_ofertadas(db, fase)
    resumo["a_iniciar"] = sum(1 for a in ofertadas if a.id not in matriculadas_areas)

    avisos = matricula_service.avisos_pre_requisito(db, aluno)
    bloqueados = [r.local_id for r in aluno.restricoes_local]

    return AlunoDetalhe(
        aluno=AlunoOut.model_validate(aluno),
        fase=fase.value,
        pre_requisito_ok=matricula_service.pre_requisito_concluido(db, aluno.id),
        avisos=avisos,
        matriculas=estados,
        locais_bloqueados=bloqueados,
        resumo=resumo,
    )


def listar(db: Session) -> list[Aluno]:
    ciclo = common.exigir_ciclo_ativo(db)
    return list(db.scalars(
        select(Aluno).where(Aluno.ciclo_id == ciclo.id).order_by(Aluno.ordenamento)
    ).all())
