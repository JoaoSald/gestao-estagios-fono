"""Fase 1 — materialização do molde (§4). Testes PUROS (sem banco)."""
from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

from app.models.enums import DiaSemana, Turno
from app.models.local import Local
from app.services.motor import molde
from app.services.motor.calendario import ContextoCalendario, ocorrencias_dia

CICLO = SimpleNamespace(id=1, data_inicio=date(2026, 3, 2), data_fim=date(2026, 7, 31))


def mk_local(**kw) -> Local:
    base = dict(
        id=1, ciclo_id=1, area_id=1, campo="Campo X", docente_id=1,
        dia_semana=DiaSemana.terca, turno=Turno.manha,
        hora_inicio=time(8, 0), hora_fim=time(12, 0),
        capacidade=4, carga_horaria=16, horas_sessao=4.0, numero_encontros=4,
        ativo=True,
    )
    base.update(kw)
    return Local(**base)


def test_fatia_em_blocos_de_n_descarta_incompleto():
    local = mk_local(numero_encontros=4)
    ctx = ContextoCalendario()
    datas = ocorrencias_dia(local.dia_semana, CICLO.data_inicio, CICLO.data_fim)
    caixas = molde.caixas_do_local(local, CICLO, ctx)

    assert len(caixas) == len(datas) // 4
    for c in caixas:
        assert len(c.datas) == 4
        assert c.data_inicio == c.datas[0] and c.data_fim == c.datas[-1]
    # ondas numeradas 1..k na ordem temporal
    assert [c.onda for c in caixas] == list(range(1, len(caixas) + 1))
    # bloco final incompleto não vira caixa
    assert len(caixas) * 4 <= len(datas)


def test_caixas_encadeadas_sem_sobreposicao():
    caixas = molde.caixas_do_local(mk_local(numero_encontros=4, passagem_grupo=False),
                                    CICLO, ContextoCalendario())
    for a, b in zip(caixas, caixas[1:]):
        assert a.data_fim < b.data_inicio  # a próxima começa depois que a anterior termina


def test_passagem_de_grupo_sobrepoe_um_dia():
    # Com passagem de grupo, o último encontro de uma onda é o 1º da seguinte.
    ctx = ContextoCalendario()
    local = mk_local(numero_encontros=4, passagem_grupo=True)
    caixas = molde.caixas_do_local(local, CICLO, ctx)
    assert len(caixas) >= 2  # datas suficientes p/ mais de uma onda
    for a, b in zip(caixas, caixas[1:]):
        assert a.data_fim == b.data_inicio          # dia de passagem compartilhado
        assert a.datas[-1] == b.datas[0]
        assert len(a.datas) == 4 and len(b.datas) == 4  # cada grupo ainda tem N encontros
    # a sobreposição rende mais ondas que o fatiamento disjunto
    disjuntas = molde.caixas_do_local(mk_local(numero_encontros=4, passagem_grupo=False), CICLO, ctx)
    assert len(caixas) >= len(disjuntas)


def test_feriado_empurra_sem_regra_de_empurrar():
    local = mk_local(numero_encontros=4)
    todas = ocorrencias_dia(local.dia_semana, CICLO.data_inicio, CICLO.data_fim)
    feriado = todas[5]  # uma terça válida no meio
    ctx = ContextoCalendario(eventos_bloqueantes=[(feriado, feriado)])

    caixas = molde.caixas_do_local(local, CICLO, ctx)
    todas_datas = [d for c in caixas for d in c.datas]
    assert feriado not in todas_datas  # a sessão pulou o feriado
    # conta sessões VIÁVEIS (não semanas): total viável = todas − 1
    assert len(molde.materializar_molde(None, CICLO, ctx, locais=[local])) >= 1


def test_local_sem_datas_suficientes_nao_gera_e_avisa():
    # N maior que as ocorrências viáveis do dia no ciclo → nenhuma caixa, mas AVISA
    # (antes sumia em silêncio — caso Linguagem Infantil com feriados/recesso).
    local = mk_local(numero_encontros=100)  # muito além das terças do ciclo
    avisos: list[str] = []
    caixas = molde.materializar_molde(None, CICLO, ContextoCalendario(), locais=[local], avisos=avisos)
    assert caixas == []
    assert len(avisos) == 1
    assert "100" in avisos[0] and "viável" in avisos[0] and "NENHUM grupo" in avisos[0]


def test_local_sem_docente_e_pulado_com_aviso():
    sem_doc = mk_local(docente_id=None)
    avisos: list[str] = []
    caixas = molde.materializar_molde(None, CICLO, ContextoCalendario(), locais=[sem_doc], avisos=avisos)
    assert caixas == []
    assert len(avisos) == 1 and "sem docente" in avisos[0]


def test_perdidos_traz_diagnostico_estruturado():
    # A prosa do aviso e o dado estruturado saem da MESMA apuração (uma fonte só).
    local = mk_local(numero_encontros=100)
    todas = ocorrencias_dia(local.dia_semana, CICLO.data_inicio, CICLO.data_fim)
    feriado = todas[3]
    ctx = ContextoCalendario(eventos_bloqueantes=[(feriado, feriado)])

    avisos: list[str] = []
    perdidos: list[molde.LocalSemGrupo] = []
    caixas = molde.materializar_molde(None, CICLO, ctx, locais=[local],
                                      avisos=avisos, perdidos=perdidos)
    assert caixas == []
    assert len(perdidos) == 1 and len(avisos) == 1
    p = perdidos[0]
    assert p.causa == "datas_insuficientes"
    assert p.local_id == local.id and p.area_id == local.area_id
    assert p.encontros == 100
    assert p.ocorrencias == len(todas)
    assert p.viaveis == len(todas) - 1        # o feriado derrubou uma data
    assert p.bloqueadas == 1
    assert p.faltam == 100 - p.viaveis
    assert p.sugerido == p.viaveis            # maior N que ainda fecha 1 grupo
    assert str(p.viaveis) in avisos[0]        # a prosa reflete o mesmo número


def test_perdidos_sem_docente_nao_varre_datas():
    perdidos: list[molde.LocalSemGrupo] = []
    molde.materializar_molde(None, CICLO, ContextoCalendario(),
                             locais=[mk_local(docente_id=None)], perdidos=perdidos)
    assert len(perdidos) == 1
    p = perdidos[0]
    assert p.causa == "sem_docente" and p.viaveis == 0 and p.ocorrencias > 0
