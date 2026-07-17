"""Ciclo — espinha dorsal da orquestração (máquina de estados).

Invariante de aplicação: no máximo UM ciclo em rascunho/em_andamento por vez
(enforce no service layer, não no banco).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Integer, Boolean, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import StatusCiclo, status_ciclo_enum

if TYPE_CHECKING:
    from app.models.aluno import Aluno
    from app.models.local import Local
    from app.models.calendario import Afastamento, Evento


class Ciclo(Base):
    __tablename__ = "ciclos"
    __table_args__ = (
        CheckConstraint("data_fim > data_inicio", name="ck_ciclo_datas"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[StatusCiclo] = mapped_column(
        status_ciclo_enum, nullable=False, server_default=StatusCiclo.rascunho.value
    )
    passo_bootstrap: Mapped[int | None] = mapped_column(Integer)
    escala_desatualizada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    criado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    encerrado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP)

    alunos: Mapped[list["Aluno"]] = relationship(back_populates="ciclo")
    locais: Mapped[list["Local"]] = relationship(back_populates="ciclo")
    eventos: Mapped[list["Evento"]] = relationship(back_populates="ciclo")
    afastamentos: Mapped[list["Afastamento"]] = relationship(back_populates="ciclo")
