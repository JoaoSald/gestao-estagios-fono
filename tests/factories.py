"""Fábricas de dados para os testes do motor.

Tudo é criado DENTRO da transação revertida do `db_session` (via `flush`, sem `commit`),
então o banco real `estagios_fono` nunca é tocado. O seed já traz catálogos e 1 ciclo,
mas ZERO alunos — estas fábricas montam cenários controlados.
"""
from __future__ import annotations

import math
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.aluno import Aluno, Matricula, RestricaoAlunoLocal
from app.models.calendario import Afastamento, Evento
from app.models.catalogo import Area, Docente
from app.models.ciclo import Ciclo
from app.core.seguranca import hash_senha
from app.models.enums import (
    DiaSemana, FaseArea, PerfilUsuario, StatusMatricula, TipoAfastamento, TipoEvento, Turno,
)
from app.models.local import Local
from app.models.usuario import Usuario

_seq = {"n": 0}


def _uid() -> int:
    _seq["n"] += 1
    return _seq["n"]


def ciclo(db: Session) -> Ciclo:
    c = db.scalars(select(Ciclo)).first()
    assert c is not None, "seed deveria ter 1 ciclo"
    return c


def docente(db: Session, nome: str | None = None) -> Docente:
    d = Docente(nome=nome or f"Docente Teste {_uid()}", email=f"doc{_uid()}@ufcspa.edu.br", ativo=True)
    db.add(d)
    db.flush()
    return d


def area(db: Session, nome: str | None = None, carga: int = 40,
         fase: FaseArea = FaseArea._9_10, pre_requisito: bool = False) -> Area:
    a = Area(nome=nome or f"Área Teste {_uid()}", carga_exigida=carga, fase=fase,
             pre_requisito=pre_requisito, composta=False)
    db.add(a)
    db.flush()
    return a


def local(
    db: Session, cic: Ciclo, ar: Area, *,
    dia: DiaSemana = DiaSemana.terca, turno: Turno = Turno.manha,
    hora_inicio: time = time(8, 0), hora_fim: time = time(12, 0),
    capacidade: int = 4, carga: int | None = None, horas_sessao: float = 4.0,
    numero_encontros: int | None = None, doc: Docente | None = None,
    campo: str | None = None,
) -> Local:
    carga = carga if carga is not None else ar.carga_exigida
    n = numero_encontros if numero_encontros is not None else max(1, math.ceil(carga / horas_sessao))
    l = Local(
        ciclo_id=cic.id, area_id=ar.id, campo=campo or f"Campo {_uid()}",
        docente_id=(doc or docente(db)).id, dia_semana=dia, turno=turno,
        hora_inicio=hora_inicio, hora_fim=hora_fim, capacidade=capacidade,
        carga_horaria=carga, horas_sessao=horas_sessao, numero_encontros=n,
        ativo=True, passagem_grupo=False,
    )
    db.add(l)
    db.flush()
    return l


def aluno(db: Session, cic: Ciclo, *, nome: str | None = None, semestre: int = 9,
          prioridade: bool = False, ordenamento: int = 1) -> Aluno:
    a = Aluno(
        ciclo_id=cic.id, nome=nome or f"Aluno {_uid()}", matricula=f"M{_uid():05d}",
        email=None, semestre=semestre, prioridade=prioridade, ordenamento=ordenamento,
    )
    db.add(a)
    db.flush()
    return a


def matricular(db: Session, al: Aluno, ar: Area,
               status: StatusMatricula = StatusMatricula.em_andamento) -> Matricula:
    m = Matricula(aluno_id=al.id, area_id=ar.id, status=status, data_matricula=date.today())
    db.add(m)
    db.flush()
    return m


def bloquear_local(db: Session, al: Aluno, l: Local) -> None:
    db.add(RestricaoAlunoLocal(aluno_id=al.id, local_id=l.id))
    db.flush()


def afastar_docente(db: Session, cic: Ciclo, doc: Docente, inicio: date, retorno: date) -> None:
    db.add(Afastamento(ciclo_id=cic.id, docente_id=doc.id, tipo=TipoAfastamento.ferias,
                       data_inicio=inicio, data_retorno=retorno))
    db.flush()


def evento(db: Session, cic: Ciclo, inicio: date, fim: date, *,
           nome: str | None = None, bloqueia: bool = True) -> Evento:
    e = Evento(ciclo_id=cic.id, nome=nome or f"Evento {_uid()}", tipo=TipoEvento.feriado,
               data_inicio=inicio, data_fim=fim, bloqueia_estagio=bloqueia)
    db.add(e)
    db.flush()
    return e


# Senha dos usuários de teste, hasheada UMA vez para a suíte toda: bcrypt custa ~170 ms
# por hash de propósito, e pagar isso em cada teste que usa a fixture `client` somaria
# dezenas de segundos — o bastante para desequilibrar os testes do motor, que têm
# orçamento de TEMPO (`ORCAMENTO_SUGESTOES` em analise_grade).
SENHA_TESTE = "senha1234"
_HASH_SENHA_TESTE = hash_senha(SENHA_TESTE)


def usuario(db: Session, perfil: PerfilUsuario, *, nome: str | None = None,
            senha: str | None = None, matricula: str | None = None) -> Usuario:
    """Conta de acesso para os testes de autorização (FASE 6).

    Hash real (bcrypt), não hash falso: é o caminho do login de verdade que interessa
    testar. `senha=None` reaproveita o hash de `SENHA_TESTE`; passar outra senha paga um
    hash novo (só quem testa senha específica precisa disso).
    """
    n = _uid()
    u = Usuario(
        nome=nome or f"{perfil.value.capitalize()} Teste {n}",
        email=f"{perfil.value}{n}@ufcspa.edu.br",
        senha_hash=_HASH_SENHA_TESTE if senha is None else hash_senha(senha),
        perfil=perfil,
        matricula=matricula,
        ativo=True,
    )
    db.add(u)
    db.flush()
    return u
