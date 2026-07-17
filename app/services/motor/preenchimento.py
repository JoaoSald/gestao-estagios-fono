"""Fase 3 — Preenchimento automático do molde (§6).

Objetivo lexicográfico: (1) COBERTURA — máximo de alunos concluindo suas áreas; depois
(2) LOTAÇÃO — empacotar caixas. Dois botões: ordem dos alunos = `ordenamento`; escolha da
caixa = empacotamento (mais cheia com vaga). As áreas de cada aluno são resolvidas da MAIS
escassa para a menos (most-constrained-first), evitando fila por conflito evitável (§6.4).

`compromissos` (dict aluno_id → list[Caixa]) é o estado partilhado: começa com os pins
já aplicados (§5) e vai crescendo a cada colocação. As 4 restrições duras
(`restricoes.py`) já consideram esse estado.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.aluno import Aluno
from app.services.motor.molde import Caixa
from app.services.motor.restricoes import caixas_viaveis, viola_restricoes


@dataclass
class Aguardando:
    """Par (aluno, área) que não coube — fila do próximo ciclo, com o motivo (§6.5)."""
    aluno_id: int
    area_id: int
    motivo: str


def indexar_por_area(caixas: list[Caixa]) -> dict[int, list[Caixa]]:
    idx: dict[int, list[Caixa]] = {}
    for c in caixas:
        idx.setdefault(c.area_id, []).append(c)
    return idx


def _escolher_caixa(viaveis: list[Caixa]) -> Caixa:
    """Mais cheia com vaga (empacota); desempate: início mais cedo (§6.4)."""
    return max(viaveis, key=lambda c: (len(c.ocupantes), -c.data_inicio.toordinal()))


def _motivo_aguardando(caixas_area: list[Caixa], comp: list[Caixa], bloqueados: set[int]) -> str:
    if not caixas_area:
        return "sem caixa para esta área no ciclo (refaz no próximo)"
    com_vaga = [c for c in caixas_area if c.tem_vaga()]
    if not com_vaga:
        return "todas as caixas da área estão cheias"
    for c in com_vaga:
        m = viola_restricoes(comp, c, bloqueados)
        if m:
            return m
    return "sem vaga viável"


def preencher(
    caixas: list[Caixa],
    alunos_ordenados: list[Aluno],
    areas_por_aluno: dict[int, list[int]],
    bloqueados_por_aluno: dict[int, set[int]],
    compromissos: dict[int, list[Caixa]],
    aguardando: list[Aguardando],
) -> None:
    """Preenche as caixas in-place. `areas_por_aluno` = áreas `em_andamento` a alocar."""
    por_area = indexar_por_area(caixas)
    for aluno in alunos_ordenados:
        comp = compromissos.setdefault(aluno.id, [])
        bloq = bloqueados_por_aluno.get(aluno.id, set())
        feitas = {c.area_id for c in comp}
        pendentes = {a for a in areas_por_aluno.get(aluno.id, []) if a not in feitas}

        while pendentes:
            # Escassez: resolve antes a área com MENOS caixas viáveis para este aluno.
            def n_viaveis(a: int) -> int:
                return len(caixas_viaveis(por_area.get(a, []), comp, bloq))

            area_id = min(pendentes, key=n_viaveis)
            pendentes.discard(area_id)
            viaveis = caixas_viaveis(por_area.get(area_id, []), comp, bloq)
            if not viaveis:
                aguardando.append(Aguardando(
                    aluno.id, area_id,
                    _motivo_aguardando(por_area.get(area_id, []), comp, bloq),
                ))
                continue
            escolhida = _escolher_caixa(viaveis)
            escolhida.ocupantes.append(aluno.id)
            comp.append(escolhida)


def aplicar_pins(
    caixas: list[Caixa],
    pins: list[tuple[int, int, int]],
    bloqueados_por_aluno: dict[int, set[int]],
    compromissos: dict[int, list[Caixa]],
) -> None:
    """Coloca antes os assentos preservados/pinados (§5) como compromissos FIXOS.

    `pins` = lista de (aluno_id, local_id, onda). Casa com a caixa (local, onda); se a onda
    mudou (datas re-derivadas), cai para a caixa viável mais cedo daquele local. O motor
    honra o pin como intocável (não é removido pela consolidação nem pelo auto-preenchimento).
    """
    por_local: dict[int, list[Caixa]] = {}
    for c in caixas:
        por_local.setdefault(c.local.id, []).append(c)

    for aluno_id, local_id, onda in pins:
        comp = compromissos.setdefault(aluno_id, [])
        candidatos = por_local.get(local_id, [])
        if not candidatos:
            continue
        alvo = next((c for c in candidatos if c.onda == onda and c.tem_vaga()), None)
        if alvo is None:
            comvaga = [c for c in candidatos if c.tem_vaga()]
            comvaga.sort(key=lambda c: c.data_inicio)
            alvo = comvaga[0] if comvaga else None
        if alvo is None or aluno_id in alvo.ocupantes:
            continue
        alvo.ocupantes.append(aluno_id)
        alvo.fixos.add(aluno_id)
        comp.append(alvo)
