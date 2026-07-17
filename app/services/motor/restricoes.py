"""As 4 restrições duras (§3) + escassez (§6.4).

Barram a entrada de um aluno numa caixa. Invioláveis — inclusive no ajuste manual (§5.3):
não há override. Operam sobre os "compromissos" do aluno = as caixas que ele já pegou.
A CH relevante é a da semana de PICO (janelas sobrepostas), não a soma plana.
"""
from __future__ import annotations

from datetime import time

from app.services.motor.molde import Caixa

MAX_HORAS_SEMANAIS = 30.0
INTERVALO_MIN_HORAS = 1.5   # 1h30 entre áreas no mesmo dia (§3.2 · decisão §11.11)


def janelas_sobrepoem(ini_a, fim_a, ini_b, fim_b) -> bool:
    return not (fim_a < ini_b or ini_a > fim_b)


def _min(t: time) -> int:
    return t.hour * 60 + t.minute


def _gap_horas(ai: time, af: time, bi: time, bf: time) -> float:
    """Horas de folga entre dois horários no mesmo dia. Negativo = sobreposição."""
    if _min(af) <= _min(bi):
        return (_min(bi) - _min(af)) / 60.0
    if _min(bf) <= _min(ai):
        return (_min(ai) - _min(bf)) / 60.0
    return -1.0  # os horários se sobrepõem no relógio


def ch_pico(caixas: list[Caixa]) -> float:
    """Maior soma de horas/semana entre caixas cujas janelas se sobrepõem no tempo."""
    pico = 0.0
    for base in caixas:
        soma = sum(
            c.horas for c in caixas
            if janelas_sobrepoem(c.data_inicio, c.data_fim, base.data_inicio, base.data_fim)
        )
        pico = max(pico, soma)
    return pico


def viola_restricoes(
    compromissos: list[Caixa],
    caixa: Caixa,
    bloqueados: set[int],
) -> str | None:
    """Motivo (pt-BR) da 1ª restrição violada ao colocar o aluno em `caixa`, ou None.

    `compromissos` = caixas que o aluno já ocupa (não inclui `caixa`).
    `bloqueados` = local_ids na blocklist do aluno (§3, restrição 4).
    """
    local = caixa.local
    # 4. Blocklist de local.
    if local.id in bloqueados:
        return "local bloqueado para este aluno"

    for c in compromissos:
        if not janelas_sobrepoem(c.data_inicio, c.data_fim, caixa.data_inicio, caixa.data_fim):
            continue
        mesmo_dia = c.local.dia_semana == local.dia_semana
        if not mesmo_dia:
            continue
        # 3. Conflito de dia/turno — não dobrar o mesmo turno.
        if c.local.turno == local.turno:
            return f"conflito de {local.dia_semana.value}/{local.turno.value} com outra área"
        # 2. Intervalo mínimo de 1h30 entre áreas no mesmo dia.
        gap = _gap_horas(c.local.hora_inicio, c.local.hora_fim, local.hora_inicio, local.hora_fim)
        if gap < INTERVALO_MIN_HORAS:
            return f"faltam 1h30 entre áreas no mesmo dia ({local.dia_semana.value})"

    # 1. Teto de 30h/semana (pico das janelas sobrepostas).
    if ch_pico(compromissos + [caixa]) > MAX_HORAS_SEMANAIS:
        return f"passaria de {MAX_HORAS_SEMANAIS:g}h na semana de pico"

    return None


def caixas_viaveis(
    caixas_da_area: list[Caixa],
    compromissos: list[Caixa],
    bloqueados: set[int],
) -> list[Caixa]:
    """Caixas da área COM vaga que passam nas 4 restrições dados os compromissos atuais."""
    return [
        c for c in caixas_da_area
        if c.tem_vaga() and viola_restricoes(compromissos, c, bloqueados) is None
    ]
