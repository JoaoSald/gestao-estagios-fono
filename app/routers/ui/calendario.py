"""Helper do calendário mensal (espelha renderCal* do versao_2).

Constrói a grade de células de um mês (domingo-primeiro) com os chips de cada dia, e a
navegação prev/next limitada a um intervalo. Cada tela (eventos, por campo, encontros)
fornece os chips por dia; a renderização é o macro `calendario` em `_macros.html`.
"""
from __future__ import annotations

import calendar as _cal
from datetime import date

MESES_LONGO = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
               "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
DOWS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]


def titulo_mes(ano: int, mes: int) -> str:
    return f"{MESES_LONGO[mes - 1]} {ano}"


def _add_mes(ym: str, delta: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    idx = (y * 12 + (m - 1)) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def celulas(ano: int, mes: int, chips_por_dia: dict[date, list[dict]], hoje: date) -> list[dict]:
    """Grade do mês: brancos iniciais (domingo-primeiro) + dias com chips."""
    start_dow = (date(ano, mes, 1).weekday() + 1) % 7  # Monday=0 → Sunday=0
    dias_no_mes = _cal.monthrange(ano, mes)[1]
    grade: list[dict] = [{"out": True} for _ in range(start_dow)]
    for d in range(1, dias_no_mes + 1):
        dia = date(ano, mes, d)
        chips = chips_por_dia.get(dia, [])
        grade.append({
            "out": False, "dia": d, "hoje": dia == hoje,
            "chips": chips[:3], "mais": max(0, len(chips) - 3),
        })
    return grade


def montar(mes_ref: str, chips_por_dia: dict[date, list[dict]], *, host_id: str,
           nav_url: str, min_mes: str, max_mes: str, hoje: date, legenda=None) -> dict:
    """Monta o `cal` que o macro `calendario` renderiza. `nav_url` recebe `?mes=YYYY-MM`."""
    y, m = int(mes_ref[:4]), int(mes_ref[5:7])
    prev_m, next_m = _add_mes(mes_ref, -1), _add_mes(mes_ref, 1)
    sep = "&" if "?" in nav_url else "?"
    return {
        "host_id": host_id, "titulo": titulo_mes(y, m), "dows": DOWS,
        "celulas": celulas(y, m, chips_por_dia, hoje),
        "prev_url": f"{nav_url}{sep}mes={prev_m}", "next_url": f"{nav_url}{sep}mes={next_m}",
        "pode_prev": mes_ref > min_mes, "pode_next": mes_ref < max_mes,
        "legenda": legenda or [],
    }


def mes_inicial(min_mes: str, max_mes: str, hoje: date) -> str:
    """Mês de abertura: hoje, limitado ao intervalo [min, max]."""
    h = hoje.strftime("%Y-%m")
    if h < min_mes:
        return min_mes
    if h > max_mes:
        return min_mes
    return h
