"""Schemas de Afastamentos (ausência de UMA pessoa: docente XOR preceptor)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.enums import TipoAfastamento
from app.schemas.common import ORMModel


class AfastamentoBase(BaseModel):
    docente_id: int | None = None
    preceptor_id: int | None = None
    tipo: TipoAfastamento = TipoAfastamento.ferias
    motivo: str | None = None
    data_inicio: date
    data_retorno: date

    @model_validator(mode="after")
    def _valida(self) -> "AfastamentoBase":
        if (self.docente_id is None) == (self.preceptor_id is None):
            raise ValueError("Informe exatamente uma pessoa: docente OU preceptor.")
        if self.data_retorno < self.data_inicio:
            raise ValueError("data_retorno deve ser >= data_inicio.")
        return self


class AfastamentoCreate(AfastamentoBase):
    pass


class AfastamentoOut(ORMModel):
    id: int
    ciclo_id: int | None
    docente_id: int | None
    preceptor_id: int | None
    tipo: TipoAfastamento
    motivo: str | None
    data_inicio: date
    data_retorno: date
    criado_em: datetime | None
