"""Rotas REST de Alunos (matrículas, restrições, estados derivados)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.aluno import (
    AlunoCreate, AlunoDetalhe, AlunoOut, AlunoUpdate, MatriculaOut,
    MatriculasSync, RestricoesSync,
)
from app.services import aluno as service
from app.services import desmatricula as desmatricula_service


class InterromperBody(BaseModel):
    motivo: str | None = None

router = APIRouter(prefix="/alunos", tags=["alunos"])


@router.get("", response_model=list[AlunoOut])
def listar(db: Session = Depends(get_db)):
    return service.listar(db)


@router.get("/{aluno_id}", response_model=AlunoDetalhe)
def obter(aluno_id: int, db: Session = Depends(get_db)):
    """Detalhe com estados derivados por área (§6.3) e avisos."""
    return service.detalhe(db, aluno_id)


@router.post("", response_model=AlunoDetalhe, status_code=status.HTTP_201_CREATED)
def criar(dados: AlunoCreate, db: Session = Depends(get_db)):
    aluno = service.criar(db, dados)
    return service.detalhe(db, aluno.id)


@router.patch("/{aluno_id}", response_model=AlunoOut)
def atualizar(aluno_id: int, dados: AlunoUpdate, db: Session = Depends(get_db)):
    return service.atualizar(db, aluno_id, dados)


@router.put("/{aluno_id}/matriculas", response_model=AlunoDetalhe)
def sincronizar_matriculas(aluno_id: int, dados: MatriculasSync, db: Session = Depends(get_db)):
    """Sincroniza o conjunto de áreas do aluno (marcadas da fase). Retorna avisos no detalhe."""
    service.sincronizar_matriculas(db, aluno_id, dados.itens)
    return service.detalhe(db, aluno_id)


@router.put("/{aluno_id}/restricoes", response_model=AlunoDetalhe)
def salvar_restricoes(aluno_id: int, dados: RestricoesSync, db: Session = Depends(get_db)):
    """Define a blocklist (local_ids bloqueados). Bloqueia se sobrar área sem local liberado."""
    service.salvar_restricoes(db, aluno_id, dados.locais_bloqueados)
    return service.detalhe(db, aluno_id)


@router.post("/{aluno_id}/interromper/{area_id}", response_model=MatriculaOut)
def interromper(aluno_id: int, area_id: int, body: InterromperBody, db: Session = Depends(get_db)):
    """Interrompe o estágio de uma área (§6.1): matrícula vira 'interrompida',
    cancela alocação + sessões futuras, libera a vaga. Sem promoção automática."""
    return desmatricula_service.desmatricular_area(db, aluno_id, area_id, body.motivo)


@router.delete("/{aluno_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(aluno_id: int, db: Session = Depends(get_db)):
    service.remover(db, aluno_id)
