"""Reúne todos os models para que o Alembic enxergue o metadata completo.

Importe `Base` daqui (ou de app.core.database) e todas as 16 tabelas estarão
registradas em `Base.metadata`.
"""
from app.core.database import Base

from app.models.ciclo import Ciclo
from app.models.catalogo import Area, Docente, Preceptor
from app.models.aluno import Aluno, Matricula, RestricaoAlunoLocal
from app.models.local import Local, IndisponibilidadeLocal
from app.models.escala import Alocacao, Sessao, Grupo, GrupoAluno
from app.models.calendario import Afastamento, Evento
from app.models.operacao import FilaRemanejo, Atividade, Historico
from app.models.usuario import Usuario

__all__ = [
    "Base",
    "Ciclo",
    "Area", "Docente", "Preceptor",
    "Aluno", "Matricula", "RestricaoAlunoLocal",
    "Local", "IndisponibilidadeLocal",
    "Alocacao", "Sessao", "Grupo", "GrupoAluno",
    "Afastamento", "Evento",
    "FilaRemanejo", "Atividade", "Historico",
    "Usuario",
]
