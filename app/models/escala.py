"""Saída do motor: alocacoes (ONDE) e sessoes (QUANDO).

O motor gera exatamente locais.numero_encontros sessões por alocação.
Contador de feitos = cumpridas + alocacoes.ajuste_encontros, limitado a [0, total].
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Time,
    UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    StatusAlocacao, StatusGrupo, StatusSessao,
    status_alocacao_enum, status_grupo_enum, status_sessao_enum,
)

if TYPE_CHECKING:
    from app.models.aluno import Aluno, Matricula
    from app.models.local import Local


class Alocacao(Base):
    __tablename__ = "alocacoes"
    __table_args__ = (
        UniqueConstraint("aluno_id", "local_id", name="uq_alocacao_aluno_local"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey("alunos.id"), nullable=False)
    local_id: Mapped[int] = mapped_column(ForeignKey("locais.id"), nullable=False)
    matricula_id: Mapped[int] = mapped_column(ForeignKey("matriculas.id"), nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim_prevista: Mapped[date] = mapped_column(Date, nullable=False)
    travada: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    ajuste_encontros: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[StatusAlocacao] = mapped_column(
        status_alocacao_enum, nullable=False, server_default=StatusAlocacao.ativa.value
    )

    aluno: Mapped["Aluno"] = relationship(back_populates="alocacoes")
    local: Mapped["Local"] = relationship(back_populates="alocacoes")
    matricula: Mapped["Matricula"] = relationship(back_populates="alocacoes")
    sessoes: Mapped[list["Sessao"]] = relationship(
        back_populates="alocacao", cascade="all, delete-orphan"
    )


class Sessao(Base):
    """A menor unidade da escala = o ENCONTRO."""
    __tablename__ = "sessoes"
    __table_args__ = (
        Index("idx_sessao_alocacao_data", "alocacao_id", "data"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alocacao_id: Mapped[int] = mapped_column(ForeignKey("alocacoes.id"), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fim: Mapped[time | None] = mapped_column(Time)
    horas: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    status: Mapped[StatusSessao] = mapped_column(
        status_sessao_enum, nullable=False, server_default=StatusSessao.prevista.value
    )

    alocacao: Mapped["Alocacao"] = relationship(back_populates="sessoes")


class Grupo(Base):
    """Onda de alunos que ocupa um local numa janela (capacidade = tamanho) — a "caixa".

    MODELO GRADE-PRIMEIRO (docs/REGRAS_MOTOR_ESCALA.md): o molde de TODOS os grupos
    do ciclo é MATERIALIZADO no bootstrap (datas = infraestrutura — feriados +
    afastamentos sem cobertura + nº de encontros —, não a demanda) e é a FONTE DE
    VERDADE. A caixa em andamento tem datas comprometidas; as previstas (futuras)
    permanecem re-deriváveis. onda 1 = grupo atual; 2,3… = previstos (cascata:
    cada onda começa quando a anterior conclui). Ver regras §10.2 e §7.
    """
    __tablename__ = "grupos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(
        ForeignKey("ciclos.id", ondelete="CASCADE"), nullable=False
    )
    local_id: Mapped[int] = mapped_column(
        ForeignKey("locais.id", ondelete="CASCADE"), nullable=False
    )
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), nullable=False)
    onda: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StatusGrupo] = mapped_column(status_grupo_enum, nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)

    membros: Mapped[list["GrupoAluno"]] = relationship(
        back_populates="grupo", cascade="all, delete-orphan"
    )


class GrupoAluno(Base):
    """Membro de um grupo. `aviso` = dependência/conflito na projeção
    (ex.: 'entra ao concluir Voz (previsto 15/09)'); nulo se entra sem conflito.
    `fixado` = remanejo manual da coordenação: quando true, o motor NÃO remove nem
    realoca este membro numa regeração (grade-primeiro — o ajuste manual sobrevive
    ao reprocesso; ver §9.1)."""
    __tablename__ = "grupo_alunos"
    __table_args__ = (
        UniqueConstraint("grupo_id", "aluno_id", name="uq_grupo_aluno"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grupo_id: Mapped[int] = mapped_column(
        ForeignKey("grupos.id", ondelete="CASCADE"), nullable=False
    )
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False
    )
    aviso: Mapped[str | None] = mapped_column(String)
    fixado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    grupo: Mapped["Grupo"] = relationship(back_populates="membros")
