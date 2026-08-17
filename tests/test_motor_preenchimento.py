"""Fase 2 — preenchimento (§5). Testes PUROS (sem banco)."""
from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

from app.models.enums import DiaSemana, Turno
from app.models.local import Local
from app.services.motor.molde import Caixa
from app.services.motor.preenchimento import preencher

JAN = date(2026, 3, 3)
FIM = date(2026, 7, 1)


def mk_caixa(lid, area, dia, turno, cap=4, ocup=0) -> Caixa:
    local = Local(id=lid, ciclo_id=1, area_id=area, campo=f"C{lid}", docente_id=1,
                  dia_semana=dia, turno=turno, hora_inicio=time(8, 0), hora_fim=time(12, 0),
                  capacidade=cap, carga_horaria=16, horas_sessao=4.0, numero_encontros=4)
    c = Caixa(local=local, area_id=area, onda=1, datas=[], data_inicio=JAN, data_fim=FIM,
              capacidade=cap, horas=4.0)
    c.ocupantes = list(range(500, 500 + ocup))
    return c


def mk_caixa_h(lid, area, dia, turno, hi, hf, horas, cap=4, ocup=0) -> Caixa:
    """Como mk_caixa, mas com horário/carga explícitos (para cenários de mesmo dia)."""
    local = Local(id=lid, ciclo_id=1, area_id=area, campo=f"C{lid}", docente_id=1,
                  dia_semana=dia, turno=turno, hora_inicio=hi, hora_fim=hf,
                  capacidade=cap, carga_horaria=int(horas), horas_sessao=horas, numero_encontros=4)
    c = Caixa(local=local, area_id=area, onda=1, datas=[], data_inicio=JAN, data_fim=FIM,
              capacidade=cap, horas=horas)
    c.ocupantes = list(range(500, 500 + ocup))
    return c


def al(i):
    return SimpleNamespace(id=i, ordenamento=i)


def _rodar(caixas, alunos, areas, bloqueados=None):
    comp: dict[int, list] = {}
    aguardando: list = []
    preencher(caixas, alunos, areas, bloqueados or {}, comp, aguardando)
    return comp, aguardando


def test_ordem_por_ordenamento_respeita_capacidade():
    caixa = mk_caixa(1, area=10, dia=DiaSemana.terca, turno=Turno.manha, cap=1)
    comp, aguardando = _rodar([caixa], [al(1), al(2)], {1: [10], 2: [10]})
    assert 1 in caixa.ocupantes and 2 not in caixa.ocupantes  # prioridade da fila
    assert any(a.aluno_id == 2 and a.area_id == 10 for a in aguardando)


def test_empacotamento_escolhe_caixa_mais_cheia():
    cheia = mk_caixa(1, area=10, dia=DiaSemana.terca, turno=Turno.manha, cap=4, ocup=2)
    vazia = mk_caixa(2, area=10, dia=DiaSemana.quinta, turno=Turno.manha, cap=4, ocup=0)
    _rodar([vazia, cheia], [al(1)], {1: [10]})
    assert 1 in cheia.ocupantes and 1 not in vazia.ocupantes


def test_escassez_evita_fila_evitavel():
    # Área M (flexível): terça OU quinta. Área A (escassa): só terça, conflita com M-terça.
    m1 = mk_caixa(1, area=10, dia=DiaSemana.terca, turno=Turno.manha)
    m2 = mk_caixa(2, area=10, dia=DiaSemana.quinta, turno=Turno.manha)
    a1 = mk_caixa(3, area=20, dia=DiaSemana.terca, turno=Turno.manha)
    comp, aguardando = _rodar([m1, m2, a1], [al(1)], {1: [10, 20]})
    # Resolve A antes (mais escassa): A pega terça; M sobra p/ quinta. Ninguém na fila.
    assert aguardando == []
    assert 1 in a1.ocupantes
    assert 1 in m2.ocupantes and 1 not in m1.ocupantes


def test_conflito_evitavel_preserva_area_sem_alternativa():
    # Caso real ORL-TAN (§6.4): área L (longa) tem caixa em terça E em quinta; área O
    # (curta) SÓ existe em terça e colide com a de L. most-constrained-first resolve L
    # primeiro (menos caixas). O motor deve escolher a caixa de L que NÃO mata O — a de
    # quinta —, deixando a terça livre para O. Antes do fix, L pegava a terça e O ia à fila.
    l_terca = mk_caixa(1, area=10, dia=DiaSemana.terca, turno=Turno.manha)
    l_quinta = mk_caixa(2, area=10, dia=DiaSemana.quinta, turno=Turno.manha)
    o_terca = mk_caixa(3, area=20, dia=DiaSemana.terca, turno=Turno.manha)
    o_terca2 = mk_caixa(4, area=20, dia=DiaSemana.terca, turno=Turno.manha)  # O tem +caixas, mas todas terça
    comp, aguardando = _rodar([l_terca, l_quinta, o_terca, o_terca2], [al(1)], {1: [10, 20]})
    assert aguardando == []                       # as duas áreas fecham
    assert 1 in l_quinta.ocupantes and 1 not in l_terca.ocupantes  # L cedeu a terça para O
    assert 1 in o_terca.ocupantes or 1 in o_terca2.ocupantes


def test_blocklist_manda_para_fila_com_motivo():
    caixa = mk_caixa(1, area=10, dia=DiaSemana.terca, turno=Turno.manha)
    comp, aguardando = _rodar([caixa], [al(1)], {1: [10]}, bloqueados={1: {1}})
    assert 1 not in caixa.ocupantes
    assert aguardando and "bloqueado" in aguardando[0].motivo


def test_duas_areas_mesmo_dia_alocadas_no_automatico():
    # Bug reportado: no preenchimento automático o aluno ficava limitado a 1 estágio/dia
    # e a 2ª área ia para a fila, deixando vaga ociosa. Sendo o mesmo dia a única opção
    # das duas áreas e havendo ≥1h30 entre as sessões, o motor agora aloca AS DUAS.
    a = mk_caixa_h(1, area=10, dia=DiaSemana.terca, turno=Turno.manha,
                   hi=time(8, 0), hf=time(10, 0), horas=2.0)
    b = mk_caixa_h(2, area=20, dia=DiaSemana.terca, turno=Turno.manha,
                   hi=time(11, 30), hf=time(13, 30), horas=2.0)  # 1h30 após o fim de A
    comp, aguardando = _rodar([a, b], [al(1)], {1: [10, 20]})
    assert aguardando == []                        # ninguém na fila, nenhuma vaga ociosa
    assert 1 in a.ocupantes and 1 in b.ocupantes   # as duas áreas, no mesmo dia


def test_duas_areas_mesmo_dia_sem_intervalo_so_uma_no_automatico():
    # Se o intervalo do mesmo dia for < 1h30, o automático aloca só uma; a outra vai à fila.
    a = mk_caixa_h(1, area=10, dia=DiaSemana.terca, turno=Turno.manha,
                   hi=time(8, 0), hf=time(10, 0), horas=2.0)
    b = mk_caixa_h(2, area=20, dia=DiaSemana.terca, turno=Turno.manha,
                   hi=time(10, 30), hf=time(12, 30), horas=2.0)  # só 30min de folga
    comp, aguardando = _rodar([a, b], [al(1)], {1: [10, 20]})
    alocadas = sum(1 for c in (a, b) if 1 in c.ocupantes)
    assert alocadas == 1 and len(aguardando) == 1


def test_carry_forward_area_concluida_nao_alocada():
    # área 10 em_andamento; área 30 (concluída) simplesmente não entra em areas_por_aluno.
    caixa10 = mk_caixa(1, area=10, dia=DiaSemana.terca, turno=Turno.manha)
    caixa30 = mk_caixa(2, area=30, dia=DiaSemana.quinta, turno=Turno.manha)
    _rodar([caixa10, caixa30], [al(1)], {1: [10]})
    assert 1 in caixa10.ocupantes and caixa30.ocupantes == []


# ============ Busca por aluno (substituiu a escolha puramente gulosa) ============

def mk_periodo(lid, area, dia, ini, fim, cap=4, ocup=0) -> Caixa:
    """Como `mk_caixa`, mas com PERÍODO próprio — é o que permite testar ondas."""
    c = mk_caixa(lid, area, dia, Turno.manha, cap=cap, ocup=ocup)
    c.data_inicio, c.data_fim = ini, fim
    return c


def test_busca_acha_cobertura_que_o_guloso_perde():
    """O caso que motivou a busca: sacrificar uma área fecha as outras duas.

    A escolha gulosa resolve uma área por vez e não desfaz. `_escolher_caixa` olha UM
    passo à frente ("a área pendente ainda tem ≥1 caixa viável?"), o que não é o mesmo
    que "ainda existe atribuição completa". Medido no molde real: fechava 8 de 11 áreas
    onde 10 eram possíveis.
    """
    from app.services.motor.preenchimento import (
        _atribuir_busca, _atribuir_guloso, _qualidade,
    )
    AGO = date(2026, 8, 4)          # depois de FIM: a 2ª onda NÃO coexiste com A/B
    DEZ = date(2026, 12, 1)
    # A e B colidem entre si (mesma terça de manhã, mesmo período) — só uma cabe.
    # C também é terça de manhã, mas tem uma 2ª onda mais tarde, que não coexiste.
    por_area = {
        1: [mk_periodo(1, 1, DiaSemana.terca, JAN, FIM)],
        2: [mk_periodo(2, 2, DiaSemana.terca, JAN, FIM)],
        3: [mk_periodo(3, 3, DiaSemana.terca, JAN, FIM),
            mk_periodo(4, 3, DiaSemana.terca, AGO, DEZ)],
    }
    g = _atribuir_guloso([1, 2, 3], por_area, [], set())
    b = _atribuir_busca([1, 2, 3], por_area, [], set())

    assert _qualidade(b) >= _qualidade(g)       # a busca nunca fica abaixo
    assert len(b) == 2                          # A e B são exclusivas: 2 é o máximo
    assert 3 in b                               # C entra pela 2ª onda


def test_busca_nunca_viola_as_restricoes_duras():
    """A busca é mais esperta, não mais permissiva: as 4 restrições continuam duras."""
    from app.services.motor.preenchimento import _atribuir_busca
    from app.services.motor.restricoes import viola_restricoes
    por_area = {
        1: [mk_periodo(1, 1, DiaSemana.terca, JAN, FIM)],
        2: [mk_periodo(2, 2, DiaSemana.terca, JAN, FIM)],   # colide com a 1
        3: [mk_periodo(3, 3, DiaSemana.quinta, JAN, FIM)],
    }
    escolha = _atribuir_busca([1, 2, 3], por_area, [], set())
    aplicadas = []
    for cx in escolha.values():
        assert viola_restricoes(aplicadas, cx, set()) is None
        aplicadas.append(cx)
    assert len(escolha) == 2                    # 1 e 2 não podem coexistir


def test_busca_respeita_blocklist_e_lotacao():
    from app.services.motor.preenchimento import _atribuir_busca
    cheia = mk_periodo(1, 1, DiaSemana.terca, JAN, FIM, cap=1, ocup=1)
    livre_bloqueada = mk_periodo(2, 1, DiaSemana.quinta, JAN, FIM)
    por_area = {1: [cheia, livre_bloqueada]}
    # única caixa com vaga é de local bloqueado para o aluno → não fecha nada
    assert _atribuir_busca([1], por_area, [], {2}) == {}
