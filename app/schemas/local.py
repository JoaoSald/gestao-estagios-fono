"""Schemas de Locais/slot (1 local = campo+dia+turno) e config de campo."""
from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DiaSemana, Turno
from app.schemas.common import ORMModel


class LocalBase(BaseModel):
    area_id: int
    docente_id: int | None = None
    unidade: str | None = None
    campo: str = Field(min_length=1)
    dia_semana: DiaSemana
    turno: Turno
    hora_inicio: time
    hora_fim: time
    capacidade: int = Field(gt=0)
    carga_horaria: int = Field(gt=0, description="CH total da área neste local (h).")
    horas_sessao: float = Field(gt=0, description="Horas reais de cada encontro.")
    numero_encontros: int | None = Field(
        default=None, gt=0,
        description="Nº de encontros da turma (conforme o espelho). Em branco = sugerido "
                    "por ceil(carga/horas_sessao).",
    )
    passagem_grupo: bool = False

    @model_validator(mode="after")
    def _horas(self) -> "LocalBase":
        if self.hora_fim <= self.hora_inicio:
            raise ValueError("hora_fim deve ser maior que hora_inicio.")
        return self


class LocalCreate(LocalBase):
    """Form do slot. Aceita docente E preceptor já na criação.

    O passo 'Config. de campo' continua existindo (atribuição em lote), mas deixou de ser
    pré-requisito: a cobertura do slot (docente + preceptor) precisa estar completa no
    próprio passo de cadastro para o validador de locais dizer a verdade sobre as datas
    viáveis — sem preceptor ele subestima a cobertura (§4/§8.3).
    """
    preceptor_tipo: Literal["externo", "docente"] | None = None
    preceptor_id: int | None = None

    @model_validator(mode="after")
    def _preceptor_coeso(self) -> "LocalCreate":
        if (self.preceptor_tipo is None) != (self.preceptor_id is None):
            raise ValueError(
                "preceptor_tipo e preceptor_id devem ser ambos informados ou ambos nulos."
            )
        return self


class LocalUpdate(BaseModel):
    area_id: int | None = None
    docente_id: int | None = None
    unidade: str | None = None
    campo: str | None = Field(default=None, min_length=1)
    dia_semana: DiaSemana | None = None
    turno: Turno | None = None
    hora_inicio: time | None = None
    hora_fim: time | None = None
    capacidade: int | None = Field(default=None, gt=0)
    carga_horaria: int | None = Field(default=None, gt=0)
    horas_sessao: float | None = Field(default=None, gt=0)
    numero_encontros: int | None = Field(default=None, gt=0)
    passagem_grupo: bool | None = None
    preceptor_tipo: Literal["externo", "docente"] | None = None
    preceptor_id: int | None = None


class LocalConfigCampo(BaseModel):
    """Passo 'Configurações de campo': atribui docente e preceptor ao slot.

    Preceptor é polimórfico: `preceptor_tipo` diz em qual catálogo `preceptor_id`
    aponta. Ambos nulos = sem preceptor separado (só o docente responde).
    """
    docente_id: int | None = None
    preceptor_tipo: Literal["externo", "docente"] | None = None
    preceptor_id: int | None = None

    @model_validator(mode="after")
    def _preceptor_coeso(self) -> "LocalConfigCampo":
        if (self.preceptor_tipo is None) != (self.preceptor_id is None):
            raise ValueError(
                "preceptor_tipo e preceptor_id devem ser ambos informados ou ambos nulos."
            )
        return self


class IndisponibilidadeCreate(BaseModel):
    motivo: str | None = None
    data_inicio: date
    data_fim: date

    @model_validator(mode="after")
    def _datas(self) -> "IndisponibilidadeCreate":
        if self.data_fim < self.data_inicio:
            raise ValueError("data_fim deve ser >= data_inicio.")
        return self


class IndisponibilidadeOut(ORMModel):
    id: int
    local_id: int
    motivo: str | None
    data_inicio: date
    data_fim: date


class LocalOut(ORMModel):
    id: int
    ciclo_id: int
    area_id: int
    unidade: str | None
    campo: str
    docente_id: int | None
    preceptor_tipo: str | None
    preceptor_id: int | None
    dia_semana: DiaSemana
    turno: Turno
    hora_inicio: time
    hora_fim: time
    capacidade: int
    carga_horaria: int
    horas_sessao: float | None
    numero_encontros: int
    passagem_grupo: bool
    ativo: bool
