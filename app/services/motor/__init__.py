"""Motor de alocação (FASE 4) — modelo grade-primeiro.

Fonte autoritativa do algoritmo: `docs/REGRAS_MOTOR_ESCALA.md`. O JS do `versao_2` é
apenas um rascunho visual e NÃO é portado.

Fluxo (§4–§6): materializa o molde (caixas com datas reais = infraestrutura) →
preenche (cobertura > lotação, escassez, empacotamento, 4 restrições duras, honrando
pins) → consolida. Eventos de meio de ciclo (§7/§8) e ajuste manual (§5) reajustam só o
conteúdo (o molde é fixo; datas só mudam por afastamento/feriado tardio ou local novo).
"""
from app.services.motor.escala import gerar_escala

__all__ = ["gerar_escala"]
