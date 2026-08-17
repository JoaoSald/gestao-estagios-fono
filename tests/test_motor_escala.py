"""Geração ponta-a-ponta + persistência (§4–§6, §10.5). Usa banco (rollback por savepoint)."""
from __future__ import annotations

from sqlalchemy import select

from app.models.aluno import Aluno, Matricula
from app.models.enums import StatusAlocacao
from app.models.escala import Alocacao, Grupo
from app.services.motor import escala
import tests.factories as f


def _alocs_do_aluno(db, aluno_id):
    return db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == aluno_id, Alocacao.status == StatusAlocacao.ativa
    )).all()


def test_gera_e_persiste_sessoes_exatas(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)          # N = 16/4 = 4 encontros
    loc = f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    a2 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    f.matricular(db, a2, ar)

    rel = escala.gerar_escala(db, c)

    assert rel.alocados == 2
    for aluno in (a1, a2):
        alocs = _alocs_do_aluno(db, aluno.id)
        assert len(alocs) == 1
        aloc = alocs[0]
        # exatamente N sessões; a última sessão = data_fim_prevista da caixa.
        assert len(aloc.sessoes) == loc.numero_encontros
        datas = sorted(s.data for s in aloc.sessoes)
        assert aloc.data_fim_prevista == datas[-1]
        assert aloc.data_inicio == datas[0]
        # matrícula recebeu previsão de conclusão.
        m = db.get(Matricula, aloc.matricula_id)
        assert m.data_conclusao_prevista == aloc.data_fim_prevista


def test_grupos_materializados_para_todos_os_locais(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    loc = f.local(db, c, ar, capacidade=2)
    escala.gerar_escala(db, c)
    grupos_loc = db.scalars(select(Grupo).where(Grupo.local_id == loc.id)).all()
    assert grupos_loc, "o molde deve materializar caixas do local (mesmo sem ocupantes)"
    assert [g.onda for g in sorted(grupos_loc, key=lambda g: g.onda)][0] == 1


def test_blocklist_manda_para_fila(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    loc = f.local(db, c, ar, capacidade=4)     # única oferta da área
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    f.bloquear_local(db, a1, loc)              # bloqueia a única oferta

    rel = escala.gerar_escala(db, c)
    assert _alocs_do_aluno(db, a1.id) == []
    assert any(x.aluno_id == a1.id and "bloqueado" in x.motivo for x in rel.aguardando)


def test_regeracao_limpa_escala_desatualizada(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)
    f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)
    assert c.escala_desatualizada is False


def test_regerar_no_rascunho_nao_conclui_nem_perde_aluno(db_session):
    """Bug: no bootstrap, o 2º "Gerar de novo" esvaziava a escala.

    Com o ciclo em `rascunho` e a data de hoje já dentro do período (normal ao montar o
    ano com o calendário correndo), `atualizar_conclusoes` marcava as sessões passadas
    como cumpridas e fechava as matrículas. Fechadas, elas saíam do filtro `em_andamento`
    e a geração seguinte simplesmente não as alocava.
    """
    from app.models.enums import StatusCiclo, StatusMatricula
    db = db_session
    c = f.ciclo(db)
    c.status = StatusCiclo.rascunho
    db.flush()
    ar = f.area(db, carga=16)
    f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    m1 = f.matricular(db, a1, ar)

    escala.gerar_escala(db, c)
    primeiras = len(_alocs_do_aluno(db, a1.id))
    assert primeiras > 0

    # Pré-condição do bug: existem sessões com data anterior a hoje (o ciclo do seed já
    # começou). É exatamente o que fazia `atualizar_conclusoes` fechar a matrícula.
    from datetime import date
    from app.models.escala import Sessao
    passadas = db.scalars(select(Sessao).join(Alocacao, Sessao.alocacao_id == Alocacao.id)
                          .where(Alocacao.aluno_id == a1.id, Sessao.data < date.today())).all()
    assert passadas, "cenário inválido: o ciclo de teste precisa ter sessões já decorridas"
    assert m1.status == StatusMatricula.em_andamento   # rascunho não conclui ninguém

    escala.gerar_escala(db, c)                          # "Gerar de novo"
    assert len(_alocs_do_aluno(db, a1.id)) == primeiras
    assert m1.status == StatusMatricula.em_andamento


def test_regerar_no_rascunho_recupera_matricula_ja_concluida(db_session):
    """Reparo dos rascunhos que já ficaram com matrículas fechadas pelo bug."""
    from app.models.enums import StatusCiclo, StatusMatricula
    db = db_session
    c = f.ciclo(db)
    c.status = StatusCiclo.rascunho
    db.flush()
    ar = f.area(db, carga=16)
    f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    m1 = f.matricular(db, a1, ar, status=StatusMatricula.concluida)

    escala.gerar_escala(db, c)
    assert m1.status == StatusMatricula.em_andamento
    assert len(_alocs_do_aluno(db, a1.id)) > 0


def test_desmatriculado_nao_volta_na_regeracao(db_session):
    """O reparo acima não pode ressuscitar quem a comissão interrompeu de propósito."""
    from app.models.enums import StatusCiclo, StatusMatricula
    db = db_session
    c = f.ciclo(db)
    c.status = StatusCiclo.rascunho
    db.flush()
    ar = f.area(db, carga=16)
    f.local(db, c, ar, capacidade=4)
    a1 = f.aluno(db, c)
    m1 = f.matricular(db, a1, ar, status=StatusMatricula.interrompida)

    escala.gerar_escala(db, c)
    assert m1.status == StatusMatricula.interrompida
    assert _alocs_do_aluno(db, a1.id) == []
