"""As 4 restrições duras (§3) + CH de pico. Testes PUROS (sem banco)."""
from __future__ import annotations

from datetime import date, time

from app.models.enums import DiaSemana, Turno
from app.models.local import Local
from app.services.motor.molde import Caixa
from app.services.motor.restricoes import (
    MAX_HORAS_SEMANAIS, ch_pico, ch_por_semana, conflitos, segunda_da_semana,
    viola_restricoes,
)

JAN = date(2026, 3, 3)
FEV = date(2026, 5, 3)


def mk_caixa(lid, dia, turno, hi, hf, horas, ini, fim, cap=4, ocup=0) -> Caixa:
    local = Local(
        id=lid, ciclo_id=1, area_id=lid, campo=f"C{lid}", docente_id=1,
        dia_semana=dia, turno=turno, hora_inicio=hi, hora_fim=hf,
        capacidade=cap, carga_horaria=int(horas), horas_sessao=horas, numero_encontros=1,
    )
    c = Caixa(local=local, area_id=lid, onda=1, datas=[], data_inicio=ini, data_fim=fim,
              capacidade=cap, horas=horas)
    c.ocupantes = list(range(100, 100 + ocup))
    return c


def test_ch_pico_soma_janelas_sobrepostas():
    a = mk_caixa(1, DiaSemana.terca, Turno.manha, time(8, 0), time(12, 0), 4.0, JAN, FEV)
    b = mk_caixa(2, DiaSemana.quinta, Turno.manha, time(8, 0), time(12, 0), 4.0, JAN, FEV)
    assert ch_pico([a, b]) == 8.0  # sobrepõem → somam
    c = mk_caixa(3, DiaSemana.terca, Turno.manha, time(8, 0), time(12, 0), 4.0,
                 date(2026, 6, 1), date(2026, 7, 1))
    assert ch_pico([a, c]) == 4.0  # não sobrepõem → pico é 1 sozinho


def test_ch_pico_nao_soma_curtas_que_nao_coexistem_via_anual():
    # Regressão: uma caixa ANUAL (ano todo) coexiste com duas curtas que NÃO se
    # sobrepõem entre si (mar–mai e jul–dez). O pico é anual + UMA curta, nunca as duas.
    anual = mk_caixa(1, DiaSemana.quarta, Turno.manha, time(8, 0), time(12, 0), 4.0,
                     date(2026, 3, 4), date(2026, 12, 2))
    curta_a = mk_caixa(2, DiaSemana.segunda, Turno.manha, time(8, 0), time(12, 0), 4.0,
                       date(2026, 3, 9), date(2026, 5, 11))
    curta_b = mk_caixa(3, DiaSemana.sexta, Turno.tarde, time(13, 0), time(16, 0), 3.0,
                       date(2026, 7, 23), date(2026, 12, 3))
    # errado (bug antigo): 4+4+3 = 11; correto: max(4+4, 4+3) = 8
    assert ch_pico([anual, curta_a, curta_b]) == 8.0


def test_teto_30h_pico():
    # 7 caixas de 4h sobrepostas = 28h; a 8ª (4h) passaria de 30.
    comp = [mk_caixa(i, DiaSemana.segunda, Turno.integral, time(8, 0), time(12, 0), 4.0, JAN, FEV)
            for i in range(1, 8)]
    nova = mk_caixa(99, DiaSemana.sexta, Turno.manha, time(8, 0), time(12, 0), 4.0, JAN, FEV)
    m = viola_restricoes(comp, nova, set())
    assert m and "30" in m


def test_sobreposicao_horario_bloqueia():
    # Cenário 3: dois horários no mesmo dia que se sobrepõem → só cabe um.
    comp = [mk_caixa(1, DiaSemana.terca, Turno.manha, time(8, 0), time(12, 0), 4.0, JAN, FEV)]
    sobreposta = mk_caixa(2, DiaSemana.terca, Turno.manha, time(10, 0), time(14, 0), 4.0, JAN, FEV)
    m = viola_restricoes(comp, sobreposta, set())
    # o dia sai ROTULADO (pt-BR acentuado), nunca o valor cru do enum
    assert m and "sobreposição" in m and "Terça" in m


def test_intervalo_1h30_mesmo_dia():
    # Cenário 2: menos de 1h30 entre o fim de uma e o início da outra → só cabe uma.
    comp = [mk_caixa(1, DiaSemana.terca, Turno.manha, time(8, 0), time(12, 0), 4.0, JAN, FEV)]
    # tarde começando 13h → só 1h de folga (12→13) < 1h30 → viola
    perto = mk_caixa(2, DiaSemana.terca, Turno.tarde, time(13, 0), time(17, 0), 4.0, JAN, FEV)
    assert viola_restricoes(comp, perto, set())
    # tarde começando 13h30 → exatamente 1h30 de folga → ok (§3.2)
    ok = mk_caixa(3, DiaSemana.terca, Turno.tarde, time(13, 30), time(16, 0), 2.5, JAN, FEV)
    assert viola_restricoes(comp, ok, set()) is None


def test_mesmo_dia_ambas_areas_com_intervalo_ok():
    # Cenário 1: duas áreas no mesmo dia com ≥1h30 entre elas → ambas cabem,
    # mesmo compartilhando o turno (não há mais bloqueio por dobrar o turno).
    comp = [mk_caixa(1, DiaSemana.terca, Turno.manha, time(8, 0), time(9, 30), 1.5, JAN, FEV)]
    # começa 11h → 1h30 exatos após o fim (9h30) → ok, e ainda dentro do turno da manhã
    segunda_area = mk_caixa(2, DiaSemana.terca, Turno.manha, time(11, 0), time(12, 30), 1.5, JAN, FEV)
    assert viola_restricoes(comp, segunda_area, set()) is None


def test_teto_30h_nao_ultrapassa():
    # Cenário 4: aluno perto das 30h não pode passar do teto.
    # 6 caixas de 4h sobrepostas = 24h; a 7ª de 4h chegaria a 28h (ok);
    # uma 8ª de 4h passaria de 30 (28+4=32) → bloqueia.
    comp = [mk_caixa(i, DiaSemana.segunda, Turno.integral, time(8, 0), time(12, 0), 4.0, JAN, FEV)
            for i in range(1, 8)]  # 7 caixas = 28h
    cabe = mk_caixa(90, DiaSemana.sexta, Turno.manha, time(8, 0), time(10, 0), 2.0, JAN, FEV)
    assert viola_restricoes(comp, cabe, set()) is None  # 28+2 = 30, no limite
    estoura = mk_caixa(91, DiaSemana.sexta, Turno.tarde, time(14, 0), time(16, 30), 2.5, JAN, FEV)
    m = viola_restricoes(comp, estoura, set())  # 28+2.5 = 30.5 > 30
    assert m and "30" in m


def test_blocklist():
    nova = mk_caixa(7, DiaSemana.terca, Turno.manha, time(8, 0), time(12, 0), 4.0, JAN, FEV)
    m = viola_restricoes([], nova, {7})
    assert m and "bloqueado" in m


def test_ch_pico_e_o_maximo_da_serie_semanal():
    """Invariante de "uma verdade só": o teto duro lê a MESMA série que a tela mostra."""
    grades = [
        [],
        [mk_caixa(1, DiaSemana.terca, Turno.manha, time(8, 0), time(12, 0), 4.0,
                  date(2026, 3, 3), date(2026, 6, 2))],
        [mk_caixa(1, DiaSemana.terca, Turno.manha, time(8, 0), time(12, 0), 4.0,
                  date(2026, 3, 3), date(2026, 6, 2)),
         mk_caixa(2, DiaSemana.quinta, Turno.tarde, time(13, 30), time(17, 30), 4.0,
                  date(2026, 5, 7), date(2026, 9, 3)),
         mk_caixa(3, DiaSemana.sexta, Turno.manha, time(8, 0), time(11, 0), 3.0,
                  date(2026, 8, 7), date(2026, 12, 4))],
    ]
    for g in grades:
        assert ch_pico(g) == max(ch_por_semana(g).values(), default=0.0)


def test_ch_por_semana_chaveia_na_segunda_e_cobre_o_periodo():
    cx = mk_caixa(1, DiaSemana.quarta, Turno.manha, time(8, 0), time(12, 0), 4.0,
                  date(2026, 3, 4), date(2026, 3, 25))     # 4 quartas consecutivas
    serie = ch_por_semana([cx])
    assert sorted(serie) == [date(2026, 3, 2), date(2026, 3, 9),
                             date(2026, 3, 16), date(2026, 3, 23)]
    assert all(d.weekday() == 0 for d in serie)            # sempre segunda-feira
    assert set(serie.values()) == {4.0}


def test_conflitos_nomeia_o_culpado_nos_tres_tipos_de_carga():
    base = mk_caixa(1, DiaSemana.terca, Turno.manha, time(8, 0), time(12, 0), 4.0,
                    date(2026, 3, 3), date(2026, 6, 2))
    # sobreposição de relógio no mesmo dia
    sobreposta = mk_caixa(2, DiaSemana.terca, Turno.manha, time(10, 0), time(14, 0), 4.0,
                          date(2026, 3, 3), date(2026, 6, 2))
    cs = conflitos([base], sobreposta, set())
    assert [c.tipo for c in cs] == ["sobreposicao"]
    assert cs[0].caixas == [base]                          # o culpado, não uma string

    # intervalo < 1h30
    perto = mk_caixa(3, DiaSemana.terca, Turno.tarde, time(13, 0), time(17, 0), 4.0,
                     date(2026, 3, 3), date(2026, 6, 2))
    cs = conflitos([base], perto, set())
    assert [c.tipo for c in cs] == ["intervalo"] and cs[0].caixas == [base]

    # blocklist: o culpado é o local, não há caixa a mover
    cs = conflitos([], base, {1})
    assert [c.tipo for c in cs] == ["blocklist"] and cs[0].caixas == []


def test_conflito_de_teto_traz_a_semana_que_estoura():
    # 7 caixas de 4h coexistindo = 28h; a 8ª de 4h estoura.
    comp = [mk_caixa(i, DiaSemana.segunda, Turno.integral, time(8, 0), time(12, 0), 4.0,
                     date(2026, 3, 2), date(2026, 6, 1)) for i in range(1, 8)]
    nova = mk_caixa(99, DiaSemana.sexta, Turno.manha, time(8, 0), time(12, 0), 4.0,
                    date(2026, 4, 3), date(2026, 6, 5))
    cs = conflitos(comp, nova, set())
    teto = [c for c in cs if c.tipo == "teto"]
    assert len(teto) == 1
    c = teto[0]
    assert c.semana == segunda_da_semana(date(2026, 4, 3))          # 1ª semana que estoura
    assert c.semana.strftime("%d/%m") in c.motivo                   # §5.3: a data, não "pico"
    assert len(c.caixas) == 7                                       # as caixas dessa semana
    assert viola_restricoes(comp, nova, set()) == cs[0].motivo       # a frase curta não mudou
    assert ch_pico(comp + [nova]) > MAX_HORAS_SEMANAIS
