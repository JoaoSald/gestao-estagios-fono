"""Schemas de Ciclos (máquina de estados; 1 ativo por vez)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.enums import StatusCiclo
from app.schemas.common import ORMModel


class CicloCreate(BaseModel):
    data_inicio: date
    data_fim: date

    @model_validator(mode="after")
    def _datas(self) -> "CicloCreate":
        if self.data_fim <= self.data_inicio:
            raise ValueError("data_fim deve ser maior que data_inicio.")
        return self


class CicloEncerrar(BaseModel):
    # Confirmação forte: digitar o ano do ciclo (evita encerramento acidental).
    ano: int


class CicloOut(ORMModel):
    id: int
    data_inicio: date
    data_fim: date
    status: StatusCiclo
    passo_bootstrap: int | None
    escala_desatualizada: bool
    criado_em: datetime | None
    encerrado_em: datetime | None


class EstadoInicial(BaseModel):
    """Estado da aplicação — decide a tela inicial (welcome/bootstrap/painel)."""

    estado: str          # 'nenhum' | 'rascunho' | 'em_andamento'
    ciclo: CicloOut | None
