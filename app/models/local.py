"""Locais de estágio, dias adicionais (multi-dia) e indisponibilidades."""
from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, Date, Float, ForeignKey, Integer, String, Time, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DiaSemana, Turno, dia_semana_enum, turno_enum

if TYPE_CHECKING:
    from app.models.ciclo import Ciclo
    from app.models.catalogo import Area, Docente
    from app.models.escala import Alocacao


class Local(Base):
    __tablename__ = "locais"
    __table_args__ = (
        CheckConstraint("capacidade > 0", name="ck_local_capacidade"),
        CheckConstraint("hora_fim > hora_inicio", name="ck_local_horas"),
        # Preceptor de campo = FK POLIMÓRFICA (resolvida na aplicação):
        # preceptor_tipo diz em qual tabela preceptor_id aponta. Ambos nulos = sem
        # preceptor separado (só o docente responde).
        CheckConstraint(
            "(preceptor_tipo IS NULL AND preceptor_id IS NULL) "
            "OR (preceptor_tipo IN ('externo', 'docente') AND preceptor_id IS NOT NULL)",
            name="ck_local_preceptor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ciclo_id: Mapped[int] = mapped_column(ForeignKey("ciclos.id"), nullable=False)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), nullable=False)
    unidade: Mapped[str | None] = mapped_column(String)
    campo: Mapped[str] = mapped_column(String, nullable=False)
    # AR-7: NULLABLE — o slot (campo+dia+turno) pode nascer sem docente e recebê-lo depois,
    # no passo "Configurações de campo". A obrigatoriedade "todo local ativo tem docente" vira
    # validação antes de gerar a escala, não constraint de banco.
    docente_id: Mapped[int | None] = mapped_column(ForeignKey("docentes.id"))
    # Preceptor de campo (opcional). FK polimórfica resolvida por preceptor_tipo:
    # 'externo' -> preceptores.id | 'docente' -> docentes.id | ambos nulos = nenhum.
    preceptor_tipo: Mapped[str | None] = mapped_column(String)
    preceptor_id: Mapped[int | None] = mapped_column(Integer)
    dia_semana: Mapped[DiaSemana] = mapped_column(dia_semana_enum, nullable=False)
    turno: Mapped[Turno] = mapped_column(turno_enum, nullable=False)
    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fim: Mapped[time] = mapped_column(Time, nullable=False)
    capacidade: Mapped[int] = mapped_column(Integer, nullable=False)
    carga_horaria: Mapped[int] = mapped_column(Integer, nullable=False)
    # Horas REAIS de cada encontro (desconta almoço no integral). numero_encontros do
    # slot = teto(carga_horaria ÷ horas_sessao). Modelo SLOT: 1 local = 1 (campo+dia+turno).
    horas_sessao: Mapped[float | None] = mapped_column(Float)
    numero_encontros: Mapped[int] = mapped_column(Integer, nullable=False)
    # Passagem de grupo: último encontro de um grupo = primeiro do próximo (ver §7.2/§10.2).
    passagem_grupo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    ciclo: Mapped["Ciclo"] = relationship(back_populates="locais")
    area: Mapped["Area"] = relationship(back_populates="locais")
    docente: Mapped["Docente | None"] = relationship(back_populates="locais")
    indisponibilidades: Mapped[list["IndisponibilidadeLocal"]] = relationship(
        back_populates="local"
    )
    alocacoes: Mapped[list["Alocacao"]] = relationship(back_populates="local")


class IndisponibilidadeLocal(Base):
    __tablename__ = "indisponibilidades_local"
    __table_args__ = (
        CheckConstraint("data_fim >= data_inicio", name="ck_indisp_datas"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    local_id: Mapped[int] = mapped_column(ForeignKey("locais.id"), nullable=False)
    motivo: Mapped[str | None] = mapped_column(String)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(Date, nullable=False)

    local: Mapped["Local"] = relationship(back_populates="indisponibilidades")
