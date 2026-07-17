"""Schemas de Eventos do calendário do ciclo."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.enums import OrigemEvento, TipoEvento
from app.schemas.common import ORMModel


class EventoBase(BaseModel):
    nome: str = Field(min_length=1)
    tipo: TipoEvento = TipoEvento.academico
    origem: OrigemEvento = OrigemEvento.manual
    data_inicio: date
    data_fim: date | None = None
    # 'Linguagem não bloqueia' vira atributo (sem hardcode): eventos com false não empurram sessões.
    bloqueia_estagio: bool = True

    @model_validator(mode="after")
    def _datas(self) -> "EventoBase":
        if self.data_fim is None:
            self.data_fim = self.data_inicio
        if self.data_fim < self.data_inicio:
            raise ValueError("data_fim deve ser >= data_inicio.")
        return self


class EventoCreate(EventoBase):
    pass


class EventoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    tipo: TipoEvento | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    bloqueia_estagio: bool | None = None


class EventoOut(ORMModel):
    id: int
    ciclo_id: int
    nome: str
    tipo: TipoEvento
    origem: OrigemEvento
    data_inicio: date
    data_fim: date
    bloqueia_estagio: bool
    google_event_id: str | None
