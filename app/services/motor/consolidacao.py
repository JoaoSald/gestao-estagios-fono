"""Fase 3 — Consolidação ("sempre tentar fechar", §6.6).

Da caixa mais fraca para a menos fraca, tenta mover ocupantes para caixas quase-cheias da
MESMA área (respeitando as 4 restrições). Troca duas caixas pela metade por uma cheia.

Guarda de cobertura (§6.2): uma jogada só é aceita se NÃO mandar ninguém para a fila —
como só movemos para um destino viável da mesma área, o aluno continua coberto; a
consolidação nunca reduz cobertura (objetivo primário). Ocupantes fixados (pins) não se
movem.
"""
from __future__ import annotations

from app.services.motor.molde import Caixa
from app.services.motor.preenchimento import indexar_por_area
from app.services.motor.restricoes import viola_restricoes


def consolidar(
    caixas: list[Caixa],
    bloqueados_por_aluno: dict[int, set[int]],
    compromissos: dict[int, list[Caixa]],
) -> int:
    """Move ocupantes de caixas fracas para caixas mais cheias. Devolve nº de movimentos."""
    por_area = indexar_por_area(caixas)
    movimentos = 0
    guarda = 0
    houve = True
    while houve and guarda < 200:
        houve = False
        guarda += 1
        fracas = sorted((c for c in caixas if c.ocupantes), key=lambda c: len(c.ocupantes))
        for fraca in fracas:
            for aluno_id in list(fraca.ocupantes):
                if aluno_id in fraca.fixos:
                    continue
                comp_sem = [c for c in compromissos.get(aluno_id, []) if c is not fraca]
                bloq = bloqueados_por_aluno.get(aluno_id, set())
                destinos = [
                    c for c in por_area.get(fraca.area_id, [])
                    if c is not fraca and c.tem_vaga()
                    and len(c.ocupantes) >= len(fraca.ocupantes)
                    and viola_restricoes(comp_sem, c, bloq) is None
                ]
                if not destinos:
                    continue
                destino = max(destinos, key=lambda c: len(c.ocupantes))
                fraca.ocupantes.remove(aluno_id)
                destino.ocupantes.append(aluno_id)
                compromissos[aluno_id] = comp_sem + [destino]
                movimentos += 1
                houve = True
    return movimentos
