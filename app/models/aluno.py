"""Alunos (por ciclo) e suas matrículas por área.

matriculas = O QUE o aluno cursa. Carry-forward: pode nascer 'concluida'.
Pré-requisito: o motor não aloca área de 6/7 sem a área pre_requisito concluída.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, Date, ForeignKey, Index, Integer, String, TIMESTAMP, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import StatusMatricula, status_matricula_enum

if TYPE_CHECKING:
    from app.models.ciclo import Ciclo
    from app.models.catalogo import Area
    from app.models.escala import Alocacao
    from app.models.local import Local


class Aluno(Base):
    __tablename__ = "alunos"
    __table_args__ = (
        UniqueConstraint("ciclo_id", "matricula", name="uq_aluno_ciclo_matricula"),
        Index("idx_alunos_ordenamento", "ordenamento"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclos.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    matricula: Mapped[str] = mapped_column(String, nullable=False)
    # Destino das notificações do sistema (padrão matricula@aluno.ufcspa.edu.br).
    email: Mapped[str | None] = mapped_column(String)
    semestre: Mapped[int | None] = mapped_column(Integer)
    # Ordem de alocação (menor = maior prioridade). DERIVADA (AR-8): por fase,
    # alunos com prioridade=true primeiro, depois por matrícula — não é ordenação manual.
    ordenamento: Mapped[int] = mapped_column(Integer, nullable=False)
    # AR-8: marcado no bootstrap p/ POSICIONAR o aluno à mão na Montagem dos grupos.
    # O motor honra a colocação (pin) e preenche o resto (prioritários não-colocados → matrícula).
    prioridade: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    criado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP)

    ciclo: Mapped["Ciclo"] = relationship(back_populates="alunos")
    matriculas: Mapped[list["Matricula"]] = relationship(back_populates="aluno")
    alocacoes: Mapped[list["Alocacao"]] = relationship(back_populates="aluno")
    restricoes_local: Mapped[list["RestricaoAlunoLocal"]] = relationship(
        back_populates="aluno", cascade="all, delete-orphan"
    )


class Matricula(Base):
    __tablename__ = "matriculas"
    __table_args__ = (
        UniqueConstraint("aluno_id", "area_id", name="uq_matricula_aluno_area"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aluno_id: Mapped[int] = mapped_column(ForeignKey("alunos.id"), nullable=False)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), nullable=False)
    data_matricula: Mapped[date | None] = mapped_column(Date)
    status: Mapped[StatusMatricula] = mapped_column(
        status_matricula_enum, nullable=False,
        server_default=StatusMatricula.em_andamento.value,
    )
    data_conclusao_prevista: Mapped[date | None] = mapped_column(Date)
    data_conclusao: Mapped[date | None] = mapped_column(Date)
    # Interrupção do estágio (desmatrícula por motivo extraordinário) — ver regra §6.1.
    motivo_interrupcao: Mapped[str | None] = mapped_column(String)
    data_interrupcao: Mapped[date | None] = mapped_column(Date)

    aluno: Mapped["Aluno"] = relationship(back_populates="matriculas")
    area: Mapped["Area"] = relationship(back_populates="matriculas")
    alocacoes: Mapped[list["Alocacao"]] = relationship(back_populates="matricula")


class RestricaoAlunoLocal(Base):
    """Restrição de local do aluno (BLOCKLIST). Ausência de linha = disponível
    (padrão). Cada linha é uma exceção: local que o aluno NÃO pode frequentar
    (condição especial). O motor pula esses locais ao alocar o aluno."""
    __tablename__ = "restricoes_aluno_local"
    __table_args__ = (
        UniqueConstraint("aluno_id", "local_id", name="uq_restricao_aluno_local"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aluno_id: Mapped[int] = mapped_column(
        ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False
    )
    local_id: Mapped[int] = mapped_column(
        ForeignKey("locais.id", ondelete="CASCADE"), nullable=False
    )

    aluno: Mapped["Aluno"] = relationship(back_populates="restricoes_local")
    local: Mapped["Local"] = relationship()
