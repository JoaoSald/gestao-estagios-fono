"""Regras de Ciclo — máquina de estados (§1).

Estados: nenhum → rascunho → em_andamento → encerrado.
Invariante: no máximo UM ciclo em `rascunho` OU `em_andamento` por vez (enforce aqui,
não no banco). O encerramento é irreversível e exige confirmação forte (digitar o ano).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from sqlalchemy import select

from app.core.errors import Conflito, DomainError
from app.models.ciclo import Ciclo
from app.models.enums import StatusCiclo, TipoAtividade
from app.models.local import Local
from app.models.operacao import Atividade
from app.schemas.ciclo import CicloCreate
from app.services import common


def obter(db: Session, ciclo_id: int) -> Ciclo:
    return common.obter_ou_404(db, Ciclo, ciclo_id, "Ciclo")


def obter_ativo(db: Session) -> Ciclo | None:
    return common.get_ciclo_ativo(db)


def estado_inicial(db: Session) -> tuple[str, Ciclo | None]:
    """Deriva o estado da aplicação (decide a tela inicial)."""
    ciclo = common.get_ciclo_ativo(db)
    if ciclo is None:
        return "nenhum", None
    return ciclo.status.value, ciclo


def abrir(db: Session, dados: CicloCreate, clonar: bool = True) -> Ciclo:
    """Cria um ciclo em `rascunho` (início do bootstrap). Recusa se já há ciclo ativo.

    `clonar=True` copia os locais do ciclo encerrado anterior (se houver) como defaults.
    """
    ativo = common.get_ciclo_ativo(db)
    if ativo is not None:
        raise Conflito(
            "Já existe um ciclo ativo (rascunho ou em andamento). "
            "Encerre-o antes de abrir outro."
        )
    ciclo = Ciclo(
        data_inicio=dados.data_inicio,
        data_fim=dados.data_fim,
        status=StatusCiclo.rascunho,
        passo_bootstrap=1,
        escala_desatualizada=False,
        criado_em=datetime.now(),
    )
    db.add(ciclo)
    db.flush()
    if clonar:
        _clonar_locais(db, ciclo)
    # Feriados nacionais (BR) + estaduais (RS) do período entram automaticamente (§11).
    from app.services import feriados as feriados_service
    feriados_service.importar_feriados(db, ciclo)
    common.commit(db, "Não foi possível abrir o ciclo.")
    db.refresh(ciclo)
    return ciclo


def _ciclo_anterior(db: Session) -> Ciclo | None:
    """O ciclo encerrado mais recente (fonte do clone de locais, AR-7)."""
    return db.scalars(
        select(Ciclo).where(Ciclo.status == StatusCiclo.encerrado)
        .order_by(Ciclo.encerrado_em.desc().nulls_last(), Ciclo.id.desc())
    ).first()


def _clonar_locais(db: Session, novo: Ciclo) -> int:
    """Copia os locais do ciclo encerrado anterior (docente/preceptor como default editável).

    Sem ciclo anterior (sistema em desenvolvimento) → não faz nada (a UI avisa "Nenhum
    ciclo anterior"). Devolve quantos locais foram clonados.
    """
    anterior = _ciclo_anterior(db)
    if anterior is None:
        return 0
    n = 0
    for l in db.scalars(select(Local).where(Local.ciclo_id == anterior.id)).all():
        db.add(Local(
            ciclo_id=novo.id, area_id=l.area_id, unidade=l.unidade, campo=l.campo,
            docente_id=l.docente_id, preceptor_tipo=l.preceptor_tipo, preceptor_id=l.preceptor_id,
            dia_semana=l.dia_semana, turno=l.turno, hora_inicio=l.hora_inicio, hora_fim=l.hora_fim,
            capacidade=l.capacidade, carga_horaria=l.carga_horaria, horas_sessao=l.horas_sessao,
            numero_encontros=l.numero_encontros, passagem_grupo=l.passagem_grupo, ativo=l.ativo,
        ))
        n += 1
    db.flush()
    return n


def set_passo(db: Session, ciclo_id: int, passo: int) -> Ciclo:
    """Persiste o passo atual do bootstrap (navegação do wizard)."""
    ciclo = obter(db, ciclo_id)
    if ciclo.status != StatusCiclo.rascunho:
        raise DomainError("Navegação de passos só vale durante o bootstrap (rascunho).")
    ciclo.passo_bootstrap = max(1, min(10, passo))
    common.commit(db, "Não foi possível salvar o passo.")
    db.refresh(ciclo)
    return ciclo


def confirmar(db: Session, ciclo_id: int) -> Ciclo:
    """rascunho → em_andamento (conclui o bootstrap)."""
    ciclo = obter(db, ciclo_id)
    if ciclo.status != StatusCiclo.rascunho:
        raise DomainError(
            f"Só é possível confirmar um ciclo em rascunho (atual: {ciclo.status.value})."
        )
    ciclo.status = StatusCiclo.em_andamento
    ciclo.passo_bootstrap = None
    db.add(Atividade(
        ciclo_id=ciclo.id, quando=date.today(),
        texto="Ciclo confirmado — em andamento.", tipo=TipoAtividade.ciclo,
    ))
    common.commit(db, "Não foi possível confirmar o ciclo.")
    db.refresh(ciclo)
    return ciclo


def encerrar(db: Session, ciclo_id: int, ano: int) -> Ciclo:
    """em_andamento → encerrado. Exige `ano` correto (confirmação forte).

    O snapshot denormalizado em `historico` é responsabilidade da FASE 8 (encerramento);
    aqui só fazemos a transição de estado.
    """
    ciclo = obter(db, ciclo_id)
    if ciclo.status != StatusCiclo.em_andamento:
        raise DomainError(
            f"Só é possível encerrar um ciclo em andamento (atual: {ciclo.status.value})."
        )
    ano_ciclo = ciclo.data_inicio.year
    if ano != ano_ciclo:
        raise DomainError(
            f"Confirmação inválida: digite o ano do ciclo ({ano_ciclo}) para encerrar."
        )
    # Snapshot denormalizado do ciclo em `historico` ANTES da transição (o passado não muda).
    from app.services import historico
    historico.snapshot_ciclo(db, ciclo)
    ciclo.status = StatusCiclo.encerrado
    ciclo.encerrado_em = datetime.now()
    ciclo.escala_desatualizada = False
    db.add(Atividade(
        ciclo_id=ciclo.id, quando=date.today(),
        texto=f"Ciclo {ano_ciclo} encerrado.", tipo=TipoAtividade.ciclo,
    ))
    common.commit(db, "Não foi possível encerrar o ciclo.")
    db.refresh(ciclo)
    return ciclo
