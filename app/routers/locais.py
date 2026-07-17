"""Rotas REST de Locais/slot (escopados no ciclo ativo)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.local import (
    IndisponibilidadeCreate, IndisponibilidadeOut,
    LocalConfigCampo, LocalCreate, LocalOut, LocalUpdate,
)
from app.services import indisponibilidade as indisp_service
from app.services import local as service

router = APIRouter(prefix="/locais", tags=["locais"])


@router.get("", response_model=list[LocalOut])
def listar(incluir_inativos: bool = True, db: Session = Depends(get_db)):
    return service.listar(db, incluir_inativos=incluir_inativos)


@router.get("/{local_id}", response_model=LocalOut)
def obter(local_id: int, db: Session = Depends(get_db)):
    return service.obter(db, local_id)


@router.post("", response_model=LocalOut, status_code=status.HTTP_201_CREATED)
def criar(dados: LocalCreate, db: Session = Depends(get_db)):
    return service.criar(db, dados)


@router.patch("/{local_id}", response_model=LocalOut)
def atualizar(local_id: int, dados: LocalUpdate, db: Session = Depends(get_db)):
    return service.atualizar(db, local_id, dados)


@router.patch("/{local_id}/campo", response_model=LocalOut)
def configurar_campo(local_id: int, dados: LocalConfigCampo, db: Session = Depends(get_db)):
    """Configurações de campo: atribui docente + preceptor (polimórfico) ao slot."""
    return service.configurar_campo(db, local_id, dados)


@router.delete("/{local_id}", response_model=LocalOut)
def desativar(local_id: int, db: Session = Depends(get_db)):
    return service.desativar(db, local_id)


# --- Indisponibilidades do local (só na operação) ---
@router.get("/{local_id}/indisponibilidades", response_model=list[IndisponibilidadeOut])
def listar_indisponibilidades(local_id: int, db: Session = Depends(get_db)):
    return indisp_service.listar(db, local_id)


@router.post(
    "/{local_id}/indisponibilidades",
    response_model=IndisponibilidadeOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_indisponibilidade(local_id: int, dados: IndisponibilidadeCreate, db: Session = Depends(get_db)):
    return indisp_service.criar(db, local_id, dados)


@router.delete("/indisponibilidades/{indisponibilidade_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_indisponibilidade(indisponibilidade_id: int, db: Session = Depends(get_db)):
    indisp_service.remover(db, indisponibilidade_id)
