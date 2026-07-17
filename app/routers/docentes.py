"""Rotas REST de Docentes (catálogo permanente; DELETE = soft-delete)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.docente import DocenteCreate, DocenteOut, DocenteUpdate
from app.services import docente as service

router = APIRouter(prefix="/docentes", tags=["docentes"])


@router.get("", response_model=list[DocenteOut])
def listar(incluir_inativos: bool = True, db: Session = Depends(get_db)):
    return service.listar(db, incluir_inativos=incluir_inativos)


@router.get("/{docente_id}", response_model=DocenteOut)
def obter(docente_id: int, db: Session = Depends(get_db)):
    return service.obter(db, docente_id)


@router.post("", response_model=DocenteOut, status_code=status.HTTP_201_CREATED)
def criar(dados: DocenteCreate, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.patch("/{docente_id}", response_model=DocenteOut)
def atualizar(docente_id: int, dados: DocenteUpdate, db: Session = Depends(get_db)):
    return service.atualizar(db, docente_id, dados)


@router.delete("/{docente_id}", response_model=DocenteOut)
def desativar(docente_id: int, db: Session = Depends(get_db)):
    """Soft-delete (marca `ativo=false`); nunca apaga."""
    return service.desativar(db, docente_id)
