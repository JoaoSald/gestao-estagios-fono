"""Schemas de saída/entrada do motor de escala (FASE 4)."""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# --- Geração ---
class AguardandoOut(ORMModel):
    aluno_id: int
    area_id: int
    motivo: str


class RelatorioGeracao(ORMModel):
    total_alunos: int
    alocados: int
    alunos_ok: int
    alunos_parcial: int
    caixas: int
    caixas_ocupadas: int
    caixas_fracas: int
    em_risco: int
    aguardando: list[AguardandoOut]
    avisos: list[str]


# --- Grupos (caixas) ---
class MembroOut(BaseModel):
    aluno_id: int
    nome: str
    fixado: bool
    aviso: str | None = None


class GrupoOut(BaseModel):
    id: int
    local_id: int
    local_campo: str
    area_id: int
    area_nome: str
    onda: int
    status: str
    data_inicio: date
    data_fim: date
    capacidade: int
    ocupacao: int
    membros: list[MembroOut]


# --- Escala do aluno ---
class SessaoOut(ORMModel):
    id: int
    data: date
    hora_inicio: time | None
    hora_fim: time | None
    horas: Decimal | None
    status: str


class AlocacaoOut(BaseModel):
    id: int
    local_id: int
    local_campo: str
    area_id: int
    area_nome: str
    data_inicio: date
    data_fim_prevista: date
    travada: bool
    status: str
    total: int
    feitos: int
    sessoes: list[SessaoOut]


class EscalaAlunoOut(BaseModel):
    aluno_id: int
    nome: str
    ordenamento: int
    alocacoes: list[AlocacaoOut]
    aguardando_areas: list[int]


class EncontrosOut(BaseModel):
    total: int
    feitos: int


# --- Ajuste manual / montagem ---
class AjusteResultado(BaseModel):
    ok: bool
    motivos: list[str] = Field(default_factory=list)
    sugestao: dict | None = None


class BancoItemOut(BaseModel):
    aluno_id: int
    nome: str
    semestre: int | None
    ch_semanal: float
    areas_pendentes: list[int]


class CHSemanalOut(BaseModel):
    aluno_id: int
    ch_semanal: float


# --- Corpos de requisição ---
class DeltaBody(BaseModel):
    delta: int


class PrioridadeBody(BaseModel):
    prioridade: bool


class MoverBody(BaseModel):
    aluno_id: int
    grupo_origem: int
    grupo_destino: int


class AdicionarBody(BaseModel):
    aluno_id: int
    grupo_id: int


class RemoverBody(BaseModel):
    aluno_id: int
    grupo_id: int


class SubstituirBody(BaseModel):
    aluno_a: int
    grupo_a: int
    aluno_b: int
    grupo_b: int


class EncaixarBody(BaseModel):
    """Nova matrícula no meio do ciclo (§10.1)."""
    area_id: int


class ReflowBody(BaseModel):
    local_id: int
    dia_afetado: date
