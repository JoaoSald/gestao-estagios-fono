"""Operação e histórico: fila de remanejo, log de atividade e snapshot do passado."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import (
    SituacaoHistorico, TipoAtividade, situacao_historico_enum, tipo_atividade_enum,
)


class FilaRemanejo(Base):
    __tablename__ = "fila_remanejo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclos.id"), nullable=False)
    quando: Mapped[date] = mapped_column(Date, nullable=False)
    texto: Mapped[str] = mapped_column(String, nullable=False)


class Atividade(Base):
    __tablename__ = "atividade"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclos.id"), nullable=False)
    quando: Mapped[date] = mapped_column(Date, nullable=False)
    texto: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[TipoAtividade] = mapped_column(
        tipo_atividade_enum, nullable=False, server_default=TipoAtividade.edicao.value
    )


class Historico(Base):
    """Snapshot denormalizado — o passado não muda."""
    __tablename__ = "historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclos.id"), nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    aluno_nome: Mapped[str] = mapped_column(String, nullable=False)
    matricula: Mapped[str | None] = mapped_column(String)
    # Array por área da fase: {nome, carga_exigida, horas_cumpridas, data_conclusao}.
    areas: Mapped[dict | list | None] = mapped_column(JSONB)
    carga_horaria_total: Mapped[int | None] = mapped_column(Integer)
    situacao: Mapped[SituacaoHistorico] = mapped_column(situacao_historico_enum, nullable=False)
    encerramento: Mapped[date | None] = mapped_column(Date)
    criado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP)
