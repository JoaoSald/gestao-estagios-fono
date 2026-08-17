"""Camada 2 — reflow pontual, descarte com carry-forward e simular/aplicar (§7.3/§8.3).

Ciclo do seed: 2026-03-02 → 2026-12-11 (hoje ~meio do ciclo). Para ter uma caixa EM
ANDAMENTO hoje, usamos carga alta (N=30) → a onda 1 corre de março a setembro.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.aluno import Matricula
from app.models.catalogo import Docente, Preceptor
from app.models.enums import DiaSemana, StatusAlocacao, StatusMatricula, StatusSessao
from app.models.escala import Alocacao, Sessao
from app.models.operacao import FilaRemanejo
from app.services import desmatricula
from app.services.motor import encontros, escala, eventos_ciclo
import tests.factories as f

HOJE = date.today()


def _futura(db, aluno_id):
    """Primeira sessão prevista futura (com alocação ativa) do aluno."""
    return db.scalars(
        select(Sessao).join(Alocacao, Sessao.alocacao_id == Alocacao.id)
        .where(Alocacao.aluno_id == aluno_id, Alocacao.status == StatusAlocacao.ativa,
               Sessao.status == StatusSessao.prevista, Sessao.data > HOJE)
        .order_by(Sessao.data)
    ).first()


def _datas_previstas(db, aluno_id):
    return [s.data for s in db.scalars(
        select(Sessao).join(Alocacao, Sessao.alocacao_id == Alocacao.id)
        .where(Alocacao.aluno_id == aluno_id, Sessao.status == StatusSessao.prevista)).all()]


def _cenario_em_andamento(db):
    """Ciclo + área carga alta (N=30) + 1 local terça + 1 aluno alocado (caixa em andamento)."""
    c = f.ciclo(db)
    ar = f.area(db, carga=120)                 # N = 30 → onda 1 vai de março a setembro
    loc = f.local(db, c, ar, dia=DiaSemana.terca)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)
    return c, ar, loc, a1


def test_simular_nao_persiste(db_session):
    db = db_session
    c, ar, loc, a1 = _cenario_em_andamento(db)
    s = _futura(db, a1.id)
    assert s is not None
    data_bloq = s.data
    f.evento(db, c, data_bloq, data_bloq)      # feriado numa terça futura da caixa

    resumo = eventos_ciclo.simular_impacto(db, c)
    assert resumo.tem_mudanca()                 # o preview detectou o empurrão
    # ...mas NADA foi aplicado: a sessão continua na data bloqueada.
    assert data_bloq in _datas_previstas(db, a1.id)


def test_aplicar_empurra_feriado(db_session):
    db = db_session
    c, ar, loc, a1 = _cenario_em_andamento(db)
    data_bloq = _futura(db, a1.id).data
    f.evento(db, c, data_bloq, data_bloq)

    eventos_ciclo.aplicar_pendencias(db, c)
    # nenhuma sessão do aluno cai na data bloqueada (foi empurrada).
    assert data_bloq not in _datas_previstas(db, a1.id)


def test_afastamento_sem_preceptor_empurra(db_session):
    db = db_session
    c, ar, loc, a1 = _cenario_em_andamento(db)
    data_bloq = _futura(db, a1.id).data
    f.afastar_docente(db, c, db.get(Docente, loc.docente_id), data_bloq, data_bloq)

    eventos_ciclo.aplicar_pendencias(db, c)
    assert data_bloq not in _datas_previstas(db, a1.id)


def test_afastamento_com_preceptor_nao_empurra(db_session):
    db = db_session
    c, ar, loc, a1 = _cenario_em_andamento(db)
    # dá um preceptor externo ativo ao local (há cobertura mesmo com docente afastado).
    p = Preceptor(nome=f"Prec {id(loc)}", email=f"prec{id(loc)}@ufcspa.edu.br", ativo=True)
    db.add(p)
    db.flush()
    loc.preceptor_tipo = "externo"
    loc.preceptor_id = p.id
    db.flush()

    data = _futura(db, a1.id).data
    f.afastar_docente(db, c, db.get(Docente, loc.docente_id), data, data)

    eventos_ciclo.aplicar_pendencias(db, c)
    # com preceptor presente há cobertura → a sessão NÃO se move.
    assert data in _datas_previstas(db, a1.id)


def test_local_desativado_descarta_com_carry_forward(db_session):
    db = db_session
    c, ar, loc, a1 = _cenario_em_andamento(db)
    m = db.scalars(select(Matricula).where(Matricula.aluno_id == a1.id, Matricula.area_id == ar.id)).first()
    feitos_antes = encontros.contar_encontros(db, m)["feitos"]
    assert feitos_antes > 0                      # já tem encontros cumpridos (março→hoje)

    loc.ativo = False                            # local morto
    db.flush()
    eventos_ciclo.aplicar_pendencias(db, c)

    # sem alocação ativa; matrícula segue em_andamento (carry-forward) e volta à fila.
    ativa = db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == a1.id, Alocacao.status == StatusAlocacao.ativa)).first()
    assert ativa is None
    db.refresh(m)
    assert m.status == StatusMatricula.em_andamento
    # os encontros já feitos são preservados.
    assert encontros.contar_encontros(db, m)["feitos"] == feitos_antes


def test_aluno_novo_entra_caixa_futura(db_session):
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)                     # N=4 → há caixas futuras vazias
    f.local(db, c, ar, dia=DiaSemana.terca)
    a1 = f.aluno(db, c)
    f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)

    a2 = f.aluno(db, c)                           # aluno novo no meio do ciclo
    f.matricular(db, a2, ar)                      # matrícula em_andamento, sem alocação
    eventos_ciclo.aplicar_pendencias(db, c)

    aloc = db.scalars(select(Alocacao).where(
        Alocacao.aluno_id == a2.id, Alocacao.status == StatusAlocacao.ativa)).first()
    assert aloc is not None
    assert aloc.data_inicio > HOJE               # entrou numa caixa FUTURA (§8.1)


def test_sincronizar_tempo_conclui_por_data(db_session):
    """§8.5: o tempo passando conclui a área por data, sem banner/clique."""
    db = db_session
    c = f.ciclo(db)
    ar = f.area(db, carga=16)                     # N=4 → onda 1 em março (já passou)
    f.local(db, c, ar, dia=DiaSemana.terca)
    a1 = f.aluno(db, c)
    m = f.matricular(db, a1, ar)
    escala.gerar_escala(db, c)
    db.refresh(m)
    assert m.status == StatusMatricula.concluida  # onda 1 terminou → concluída sozinha

    # "desfaz" o estado e confirma que sincronizar_tempo recupera por data.
    m.status = StatusMatricula.em_andamento
    m.data_conclusao = None
    db.flush()
    encontros.sincronizar_tempo(db, c)
    db.refresh(m)
    assert m.status == StatusMatricula.concluida


def test_desmatricula_nao_enfileira(db_session):
    db = db_session
    c, ar, loc, a1 = _cenario_em_andamento(db)
    antes = db.query(FilaRemanejo).filter_by(ciclo_id=c.id).count()
    desat_antes = c.escala_desatualizada

    desmatricula.desmatricular_area(db, a1.id, ar.id, motivo="teste")

    # vaga aberta / desistência não gera pendência de remanejo (§8.2/§7.2).
    assert db.query(FilaRemanejo).filter_by(ciclo_id=c.id).count() == antes
    db.refresh(c)
    assert c.escala_desatualizada == desat_antes


def test_fila_sem_vaga_nao_e_pendencia_de_remanejo(db_session):
    """Aluno na fila sem caixa viável é ALERTA (§9), não gatilho de remanejo (§7.1).

    `aguardando` é o aluno que o reflow tentou sentar e não conseguiu — aplicar o remanejo
    não muda nada. Se isso contasse como mudança, a pendência ficaria acesa para sempre.
    """
    db = db_session
    c, ar, loc, a1 = _cenario_em_andamento(db)
    orfa = f.area(db, carga=40)          # área SEM local: matrícula que nunca acha caixa
    a2 = f.aluno(db, c, ordenamento=2)
    f.matricular(db, a2, orfa)
    db.flush()

    resumo = eventos_ciclo.simular_impacto(db, c)
    assert any(x["aluno"] == a2.nome for x in resumo.aguardando)   # o alerta existe...
    assert not resumo.tem_mudanca()                                # ...e não há o que aplicar
    assert not c.escala_desatualizada


def test_novo_local_para_a_fila_ai_sim_e_pendencia(db_session):
    """O contraponto (§8.4): oferta nova COM fila é o que de fato acende a pendência."""
    db = db_session
    c, ar, loc, a1 = _cenario_em_andamento(db)
    orfa = f.area(db, carga=40)
    a2 = f.aluno(db, c, ordenamento=2)
    f.matricular(db, a2, orfa)
    db.flush()
    assert not eventos_ciclo.simular_impacto(db, c).tem_mudanca()

    f.local(db, c, orfa, dia=DiaSemana.quinta)   # abre o dia que faltava
    db.flush()

    resumo = eventos_ciclo.simular_impacto(db, c)
    assert resumo.tem_mudanca()
    assert any(p["aluno"] == a2.nome for p in resumo.colocados)
