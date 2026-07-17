"""Helpers transversais dos services (regras que valem para vários recursos)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import Conflito, NaoEncontrado
from app.models.ciclo import Ciclo
from app.models.enums import FaseArea, StatusCiclo, TipoAtividade
from app.models.operacao import Atividade, FilaRemanejo


def get_ciclo_ativo(db: Session) -> Ciclo | None:
    """O único ciclo em `rascunho` OU `em_andamento` (invariante: no máx. 1).

    Retorna `None` quando não há ciclo ativo (estado inicial 'nenhum').
    """
    return db.scalars(
        select(Ciclo).where(
            Ciclo.status.in_([StatusCiclo.rascunho, StatusCiclo.em_andamento])
        )
    ).first()


def exigir_ciclo_ativo(db: Session) -> Ciclo:
    """Como `get_ciclo_ativo`, mas 409 quando não há ciclo aberto.

    Usado pelos recursos por-ciclo (locais, alunos, eventos…): não faz sentido
    cadastrá-los sem um ciclo aberto.
    """
    ciclo = get_ciclo_ativo(db)
    if ciclo is None:
        raise Conflito("Nenhum ciclo aberto. Abra um ciclo antes de cadastrar.")
    return ciclo


def fase_do_aluno(semestre: int | None) -> FaseArea:
    """Deriva a fase a partir do semestre (espelha `faseDoAluno` do protótipo).

    <= 7 → mini-ciclo ('7', só Audiologia I); caso contrário 9º/10º ('9_10').
    Sem semestre informado, assume 9_10 (fase padrão das áreas).
    """
    if semestre is not None and semestre <= 7:
        return FaseArea._7
    return FaseArea._9_10


def registrar_atividade(
    db: Session,
    ciclo: Ciclo,
    texto: str,
    tipo: TipoAtividade = TipoAtividade.edicao,
) -> None:
    """Registra a ação no feed de `atividade` — SEM marcar pendência de remanejo.

    Para edições de CONTEÚDO/escala (ajuste manual, montagem, encontros,
    desmatrícula) e cadastros comuns não-estruturais. Vaga aberta / desistência /
    conclusão não geram pendência (§7.2). No-op fora de `em_andamento`.
    """
    if ciclo.status != StatusCiclo.em_andamento:
        return
    db.add(Atividade(ciclo_id=ciclo.id, quando=date.today(), texto=texto, tipo=tipo))


def registrar_pendencia_infra(
    db: Session,
    ciclo: Ciclo,
    gatilho: str,
    tipo: TipoAtividade = TipoAtividade.edicao,
) -> None:
    """Evento de INFRAESTRUTURA (§7.1) em operação: marca uma pendência a revisar.

    Acende o banner "há mudanças a revisar" (`escala_desatualizada`), enfileira o
    gatilho em `fila_remanejo` e registra no feed. NÃO aplica nada: o reajuste é
    pontual e deliberado, feito depois pelo Remanejar (revisar impacto → aplicar
    só o afetado, §7.3). No-op fora de `em_andamento` (no bootstrap ainda não há
    escala a reajustar).
    """
    if ciclo.status != StatusCiclo.em_andamento:
        return
    ciclo.escala_desatualizada = True
    hoje = date.today()
    db.add(FilaRemanejo(ciclo_id=ciclo.id, quando=hoje, texto=gatilho))
    db.add(Atividade(ciclo_id=ciclo.id, quando=hoje, texto=gatilho, tipo=tipo))


def obter_ou_404(db: Session, model, id_: int, rotulo: str):
    """Busca por PK e levanta 404 pt-BR se não achar."""
    obj = db.get(model, id_)
    if obj is None:
        raise NaoEncontrado(f"{rotulo} não encontrado(a).")
    return obj


def commit(db: Session, mensagem_conflito: str = "Operação viola uma restrição do banco.") -> None:
    """Commit com rede de segurança: `IntegrityError` (unique/CHECK/FK) vira 409 pt-BR.

    Os services fazem as validações de negócio ANTES (com mensagens específicas);
    este é o guarda final para corridas ou restrições não pré-checadas.
    """
    try:
        db.commit()
    except IntegrityError as exc:  # pragma: no cover - rede de segurança
        db.rollback()
        raise Conflito(mensagem_conflito) from exc
