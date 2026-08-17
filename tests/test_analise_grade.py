"""Diagnóstico da oferta (`services/analise_grade`): validador de locais, régua de
horários e vagas × demanda.

`linha_do_tempo` é pura — recebe `SlotValidado` e não toca o banco, então é testada com
objetos transientes. O validador e a tabela de demanda usam o banco (ciclo do seed) e por
isso filtram pelo local/área que o teste criou: o seed já traz dezenas de slots e as
asserções não podem depender deles.
"""
from __future__ import annotations

from datetime import time

from app.models.enums import DiaSemana, Turno
from app.models.local import Local
from app.services import analise_grade
from app.services.motor import calendario
from tests import factories as f

_ids = {"n": 100}


def _slot(dia: DiaSemana, ini: time, fim: time, *, cap: int = 4, ondas: int = 1,
          area: str = "Área A", cor: str = "#0ea5e9", turno: Turno = Turno.manha,
          campo: str = "Campo") -> analise_grade.SlotValidado:
    """SlotValidado transiente. `horas_sessao=None` → horas = (fim − início)."""
    _ids["n"] += 1
    local = Local(
        id=_ids["n"], ciclo_id=1, area_id=1, campo=campo, docente_id=1,
        dia_semana=dia, turno=turno, hora_inicio=ini, hora_fim=fim,
        capacidade=cap, carga_horaria=40, horas_sessao=None, numero_encontros=10,
        ativo=True, passagem_grupo=False,
    )
    return analise_grade.SlotValidado(
        local=local, area_nome=area, area_cor=cor, area_carga_exigida=40,
        ocorrencias=20, viaveis=20, ondas=ondas, capacidade_efetiva=ondas * cap,
        ch_derivada=40.0, ch_sugerida=40.0, status="ok",
    )


# ============================ Validador de locais ============================
def test_local_que_nao_fecha_grupo_e_falha_e_sugere_o_maximo(db_session):
    """Caso do print: N do espelho acima das datas viáveis → nenhum grupo, com sugestão."""
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=40)
    local = f.local(db_session, ciclo, area, numero_encontros=999)

    slots = {s.local.id: s for s in analise_grade.validar_locais(db_session, ciclo)["slots"]}
    sv = slots[local.id]

    assert sv.status == "falha" and sv.causa == "datas_insuficientes"
    assert sv.ondas == 0 and sv.capacidade_efetiva == 0
    assert sv.viaveis < 999 and sv.sugerido == sv.viaveis
    assert sv.pode_sugerir
    assert "nenhum grupo fecha" in " ".join(sv.motivos)
    assert sv in analise_grade.validar_locais(db_session, ciclo)["problemas"]


def test_slot_saudavel_nao_sugere_aumentar_encontros(db_session):
    """14 encontros com 40 datas viáveis fecha 2 grupos; sugerir 40 faria UM grupo
    ocupando o ciclo inteiro — menos vagas. O atalho é conserto, não otimização."""
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=56)                       # 14 × 4h
    local = f.local(db_session, ciclo, area, horas_sessao=4.0, numero_encontros=14)

    val = analise_grade.validar_locais(db_session, ciclo)
    sv = {s.local.id: s for s in val["slots"]}[local.id]
    assert sv.status == "ok" and sv.causa is None
    assert sv.ondas >= 2
    assert sv.viaveis > sv.encontros        # há folga de datas…
    assert not sv.pode_sugerir              # …e mesmo assim não sugere nada
    assert sv not in val["problemas"]       # nem aparece na lista da tela


def test_problemas_traz_so_o_que_precisa_de_decisao(db_session):
    """A tela lista só falha/ressalva — 34 linhas verdes esconderiam as 3 que importam."""
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=16)
    ok = f.local(db_session, ciclo, area, numero_encontros=4)
    quebrado = f.local(db_session, ciclo, area, numero_encontros=999)

    val = analise_grade.validar_locais(db_session, ciclo)
    ids = {s.local.id for s in val["problemas"]}
    assert quebrado.id in ids and ok.id not in ids
    assert all(s.status != "ok" for s in val["problemas"])
    # falha antes de ressalva: o que não gera grupo nenhum vem primeiro
    status = [s.status for s in val["problemas"]]
    assert status == sorted(status, key=lambda st: st != "falha")


def test_numero_sugerido_realmente_fecha_um_grupo(db_session):
    """O `sugerido` não é chute: aplicado ao slot, ele fecha ao menos 1 grupo."""
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=40)
    quebrado = f.local(db_session, ciclo, area, numero_encontros=999)

    sv = {s.local.id: s for s in
          analise_grade.validar_locais(db_session, ciclo)["slots"]}[quebrado.id]
    assert sv.sugerido > 0

    quebrado.numero_encontros = sv.sugerido
    db_session.flush()
    depois = {s.local.id: s for s in
              analise_grade.validar_locais(db_session, ciclo)["slots"]}[quebrado.id]
    assert depois.ondas >= 1
    assert depois.capacidade_efetiva == depois.ondas * quebrado.capacidade


def test_evento_bloqueante_derruba_datas_viaveis(db_session):
    """Feriado no dia do slot reduz as datas viáveis — e o validador mostra o quanto."""
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=40)
    local = f.local(db_session, ciclo, area, dia=DiaSemana.terca, numero_encontros=4)

    antes = {s.local.id: s for s in
             analise_grade.validar_locais(db_session, ciclo)["slots"]}[local.id]

    tercas = calendario.ocorrencias_dia(DiaSemana.terca, ciclo.data_inicio, ciclo.data_fim)
    f.evento(db_session, ciclo, tercas[2], tercas[2])

    depois = {s.local.id: s for s in
              analise_grade.validar_locais(db_session, ciclo)["slots"]}[local.id]
    assert depois.viaveis == antes.viaveis - 1
    assert depois.bloqueadas == antes.bloqueadas + 1
    assert depois.ocorrencias == antes.ocorrencias  # ocorrências do dia não mudam


def test_ch_abaixo_da_exigida_marca_atencao(db_session):
    """Fecha grupo, mas com CH menor que a área exige — o alerta que o corte de encontros
    provoca (reduzir 40→37 encontros reduz a carga cumprida)."""
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=40)
    local = f.local(db_session, ciclo, area, horas_sessao=4.0, numero_encontros=5)  # 20h

    sv = {s.local.id: s for s in
          analise_grade.validar_locais(db_session, ciclo)["slots"]}[local.id]
    assert sv.ondas >= 1
    assert sv.status == "atencao" and sv.causa == "ch_abaixo"
    assert sv.ch_derivada == 20.0 and sv.ch_abaixo == 20.0
    assert "abaixo da exigida" in " ".join(sv.motivos)
    assert not sv.pode_sugerir   # fecha grupo; encher de encontros não é o conserto


def test_slot_sem_docente_e_falha(db_session):
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=40)
    local = f.local(db_session, ciclo, area, numero_encontros=4)
    local.docente_id = None
    db_session.flush()

    sv = {s.local.id: s for s in
          analise_grade.validar_locais(db_session, ciclo)["slots"]}[local.id]
    assert sv.status == "falha" and sv.causa == "sem_docente" and sv.ondas == 0
    assert "Sem docente" in " ".join(sv.motivos)
    assert not sv.pode_sugerir   # o conserto é atribuir docente, não mexer em encontros


# ============================ Régua de horários ============================
def test_linha_do_tempo_empilha_sobrepostos_em_pistas():
    """Blocos que se cruzam no relógio vão para pistas diferentes (senão se cobrem)."""
    tl = analise_grade.linha_do_tempo([
        _slot(DiaSemana.quarta, time(8, 0), time(12, 0), campo="A"),
        _slot(DiaSemana.quarta, time(10, 0), time(14, 0), campo="B"),   # sobrepõe A
        _slot(DiaSemana.quarta, time(14, 0), time(18, 0), campo="C"),   # cabe após A
    ])
    assert tl["ini"] == 8 and tl["fim"] == 18
    dia = tl["dias"][0]
    pista = {b["slot"].local.campo: b["pista"] for b in dia["blocos"]}
    assert pista["A"] != pista["B"]        # sobrepostos, pistas distintas
    assert pista["C"] == pista["A"]        # C começa quando A já acabou → reaproveita

    a = next(b for b in dia["blocos"] if b["slot"].local.campo == "A")
    assert a["esquerda"] == 0.0            # começa na borda esquerda (08h = início da régua)
    assert round(a["largura"]) == 40       # 4h de 10h de régua


# ============================ Vagas × demanda ============================
def test_capacidade_vs_demanda_antecipa_a_fila(db_session):
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=16)
    local = f.local(db_session, ciclo, area, capacidade=2, numero_encontros=4)
    for _ in range(5):
        f.matricular(db_session, f.aluno(db_session, ciclo), area)

    val = analise_grade.validar_locais(db_session, ciclo)
    linha = next(r for r in analise_grade.capacidade_vs_demanda(
        db_session, ciclo, val["slots"]) if r["area_id"] == area.id)

    sv = {s.local.id: s for s in val["slots"]}[local.id]
    assert linha["demanda"] == 5
    assert linha["slots"] == 1 and linha["ondas"] == sv.ondas
    assert linha["vagas"] == sv.ondas * 2
    assert linha["saldo"] == linha["vagas"] - 5


def test_area_com_demanda_e_sem_slot_aparece_com_saldo_negativo(db_session):
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=16)   # nenhuma oferta cadastrada
    f.matricular(db_session, f.aluno(db_session, ciclo), area)

    val = analise_grade.validar_locais(db_session, ciclo)
    linha = next(r for r in analise_grade.capacidade_vs_demanda(
        db_session, ciclo, val["slots"]) if r["area_id"] == area.id)
    assert linha["slots"] == 0 and linha["vagas"] == 0
    assert linha["demanda"] == 1 and linha["saldo"] == -1


def test_slot_que_nao_fecha_grupo_nao_conta_vaga(db_session):
    """Capacidade perdida: o slot existe, aparece como `sem_grupo`, mas não gera vaga."""
    ciclo = f.ciclo(db_session)
    area = f.area(db_session, carga=40)
    f.local(db_session, ciclo, area, numero_encontros=999)
    f.matricular(db_session, f.aluno(db_session, ciclo), area)

    val = analise_grade.validar_locais(db_session, ciclo)
    linha = next(r for r in analise_grade.capacidade_vs_demanda(
        db_session, ciclo, val["slots"]) if r["area_id"] == area.id)
    assert linha["slots"] == 1 and linha["sem_grupo"] == 1
    assert linha["vagas"] == 0 and linha["saldo"] == -1
