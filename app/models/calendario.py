"""Calendário institucional: afastamentos de docentes e eventos do ciclo."""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey, Integer, String, TIMESTAMP,
    UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    OrigemEvento, TipoAfastamento, TipoEvento,
    origem_evento_enum, tipo_afastamento_enum, tipo_evento_enum,
)

if TYPE_CHECKING:
    from app.models.ciclo import Ciclo
    from app.models.catalogo import Docente, Preceptor


class Afastamento(Base):
    """Ausência (férias/licença/outro) de UMA pessoa: docente OU preceptor.

    Exatamente uma das FKs (docente_id / preceptor_id) é preenchida (CHECK XOR).
    Quando o preceptor de um local é um docente, a ausência dele é registrada
    como afastamento de docente.
    """
    __tablename__ = "afastamentos"
    __table_args__ = (
        CheckConstraint("data_retorno >= data_inicio", name="ck_afast_datas"),
        # Exatamente uma pessoa: docente XOR preceptor.
        CheckConstraint(
            "(docente_id IS NOT NULL) <> (preceptor_id IS NOT NULL)",
            name="ck_afast_pessoa",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int | None] = mapped_column(ForeignKey("ciclos.id"))
    docente_id: Mapped[int | None] = mapped_column(ForeignKey("docentes.id"))
    preceptor_id: Mapped[int | None] = mapped_column(ForeignKey("preceptores.id"))
    tipo: Mapped[TipoAfastamento] = mapped_column(
        tipo_afastamento_enum, nullable=False, server_default=TipoAfastamento.ferias.value
    )
    motivo: Mapped[str | None] = mapped_column(String)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_retorno: Mapped[date] = mapped_column(Date, nullable=False)
    criado_em: Mapped[datetime | None] = mapped_column(TIMESTAMP)

    ciclo: Mapped["Ciclo | None"] = relationship(back_populates="afastamentos")
    docente: Mapped["Docente | None"] = relationship(back_populates="afastamentos")
    preceptor: Mapped["Preceptor | None"] = relationship(back_populates="afastamentos")


class Evento(Base):
    __tablename__ = "eventos"
    __table_args__ = (
        CheckConstraint("data_fim >= data_inicio", name="ck_evento_datas"),
        UniqueConstraint("ciclo_id", "nome", "data_inicio", name="uq_evento_ciclo_nome_data"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclos.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[TipoEvento] = mapped_column(tipo_evento_enum, nullable=False)
    origem: Mapped[OrigemEvento] = mapped_column(
        origem_evento_enum, nullable=False, server_default=OrigemEvento.manual.value
    )
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)
    # Regra "evento de Linguagem não bloqueia" vira atributo, sem hardcode.
    bloqueia_estagio: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    google_event_id: Mapped[str | None] = mapped_column(String)

    ciclo: Mapped["Ciclo"] = relationship(back_populates="eventos")
