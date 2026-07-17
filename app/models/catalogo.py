"""Catálogos permanentes (atravessam ciclos): áreas e docentes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import FaseArea, fase_area_enum

if TYPE_CHECKING:
    from app.models.aluno import Matricula
    from app.models.local import Local
    from app.models.calendario import Afastamento
    from app.models.escala import Grupo


class Area(Base):
    __tablename__ = "areas"
    __table_args__ = (
        CheckConstraint("carga_exigida > 0", name="ck_area_carga"),
        # No máximo UMA área pré-requisito (Audiologia I): índice único parcial.
        Index("uq_area_prereq", "pre_requisito", unique=True,
              postgresql_where=text("pre_requisito")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    cor: Mapped[str | None] = mapped_column(String(7))
    carga_exigida: Mapped[int] = mapped_column(Integer, nullable=False)
    fase: Mapped[FaseArea] = mapped_column(
        fase_area_enum, nullable=False, server_default=FaseArea._9_10.value
    )
    pre_requisito: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Área COMPOSTA (container, ex.: Audiologia II, Hospitalar): não é matriculável
    # nem alocável (não tem locais). O aluno cursa as SUB-ÁREAS (leaf).
    composta: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # Sub-área de uma composta: aponta para a área-mãe (container). Área simples/mãe = NULL.
    # A CH da mãe = soma das CHs das sub-áreas; matrícula/conclusão são por sub-área.
    area_mae_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"))

    mae: Mapped["Area | None"] = relationship("Area", remote_side="Area.id", back_populates="sub_areas")
    sub_areas: Mapped[list["Area"]] = relationship("Area", back_populates="mae")
    matriculas: Mapped[list["Matricula"]] = relationship(back_populates="area")
    locais: Mapped[list["Local"]] = relationship(back_populates="area")


class Docente(Base):
    __tablename__ = "docentes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # Login institucional UFCSPA + destino das notificações do sistema.
    email: Mapped[str | None] = mapped_column(String)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    locais: Mapped[list["Local"]] = relationship(back_populates="docente")
    afastamentos: Mapped[list["Afastamento"]] = relationship(back_populates="docente")


class Preceptor(Base):
    """Responsável de campo, EXTERNO à UFCSPA (sem login institucional).

    A conta é gerada a partir do e-mail (por isso obrigatório). Catálogo
    permanente; 1 preceptor pode responder por N locais. O preceptor de um
    local é uma referência POLIMÓRFICA (locais.preceptor_tipo/preceptor_id):
    pode apontar para cá (externo) ou para um docente.
    """
    __tablename__ = "preceptores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    afastamentos: Mapped[list["Afastamento"]] = relationship(back_populates="preceptor")
