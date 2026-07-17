"""Schemas de Alunos, Matrículas, Restrições e read-model de estados (§6.3)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import StatusMatricula
from app.schemas.common import ORMModel


# --- Matrícula (item do conjunto sincronizado) ---
class MatriculaItem(BaseModel):
    area_id: int
    # Carry-forward: uma área já feita entra como 'concluida'.
    status: StatusMatricula = StatusMatricula.em_andamento


class MatriculaOut(ORMModel):
    id: int
    aluno_id: int
    area_id: int
    data_matricula: date | None
    status: StatusMatricula
    data_conclusao_prevista: date | None
    data_conclusao: date | None
    motivo_interrupcao: str | None
    data_interrupcao: date | None


# --- Aluno ---
class AlunoCreate(BaseModel):
    nome: str = Field(min_length=1)
    matricula: str = Field(min_length=1)
    email: str | None = None
    semestre: int | None = None
    prioridade: bool = False
    matriculas: list[MatriculaItem] = Field(default_factory=list)
    locais_bloqueados: list[int] = Field(default_factory=list)


class AlunoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    matricula: str | None = Field(default=None, min_length=1)
    email: str | None = None
    semestre: int | None = None
    prioridade: bool | None = None


class AlunoOut(ORMModel):
    id: int
    ciclo_id: int
    nome: str
    matricula: str
    email: str | None
    semestre: int | None
    ordenamento: int
    prioridade: bool


# --- Sincronização de matrículas / restrições ---
class MatriculasSync(BaseModel):
    """Conjunto desejado de áreas do aluno (as 'marcadas' da fase dele)."""
    itens: list[MatriculaItem]


class RestricoesSync(BaseModel):
    """Blocklist: local_ids que o aluno NÃO pode frequentar (ausência = disponível)."""
    locais_bloqueados: list[int]


# --- Read-model de estados derivados (§6.3) ---
class MatriculaEstado(BaseModel):
    area_id: int
    area_nome: str
    status: StatusMatricula
    estado: str   # a_iniciar | aguardando | em_andamento | em_risco | concluida | interrompida | incompleta
    data_conclusao_prevista: date | None = None


class AlunoDetalhe(BaseModel):
    aluno: AlunoOut
    fase: str
    pre_requisito_ok: bool
    avisos: list[str]
    matriculas: list[MatriculaEstado]
    locais_bloqueados: list[int]
    resumo: dict[str, int]
