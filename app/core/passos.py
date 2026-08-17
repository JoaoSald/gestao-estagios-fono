"""Ordem canônica dos passos do bootstrap — fonte única de verdade.

A ordem NÃO é arbitrária: ela segue o grafo de dependências do wizard. O que decide é
`ContextoCalendario.datas_viaveis` (`motor/calendario.py`), que precisa de **datas do
ciclo + eventos bloqueantes + afastamentos + cobertura (docente/preceptor)** para dizer
quantos encontros um slot consegue fechar. Por isso Eventos e Afastamentos vêm ANTES de
Áreas e Locais: é o que permite validar a oferta (nº de encontros × datas viáveis) no
próprio passo em que o local é cadastrado, em vez de descobrir na geração.

As demais amarras:
  * Afastamentos > Docentes e Preceptores  (o afastamento aponta para uma pessoa);
  * Locais > Áreas                          (o slot pertence a uma área folha);
  * Alunos > Locais                         (a blocklist do aluno é montada sobre os
                                             locais ativos — `cadastros.py::_salvar`).

Leitura para a comissão: passos 1–5 são "o ano" (calendário e quem cobre), 6–7 são "a
oferta", 8–9 são "as pessoas", 10 é "rodar".

Cada passo tem uma CHAVE estável. Rotear/ramificar por chave (não pelo número) é o que
permite reordenar o wizard sem caçar `passo == 5` espalhado em router e template.
"""
from __future__ import annotations

# (chave, rótulo exibido no stepper)
PASSOS: list[tuple[str, str]] = [
    ("ciclo", "Ciclo"),
    ("docentes", "Docentes"),
    ("preceptores", "Preceptores"),
    ("eventos", "Eventos"),
    ("afastamentos", "Afastamentos"),
    ("oferta", "Áreas e Locais"),
    ("campo", "Config. de campo"),
    ("alunos", "Alunos"),
    ("montagem", "Montagem de prioridade"),
    ("revisao", "Revisão & Geração"),
]

TOTAL_PASSOS = len(PASSOS)

# número (1-based, como fica em `ciclo.passo_bootstrap`) → chave
CHAVE_POR_NUMERO: dict[int, str] = {i: k for i, (k, _) in enumerate(PASSOS, start=1)}
NUMERO_POR_CHAVE: dict[str, int] = {k: i for i, k in CHAVE_POR_NUMERO.items()}

ROTULOS: list[str] = [rot for _k, rot in PASSOS]


def chave(passo: int) -> str:
    """Chave do passo, com clamp — `passo_bootstrap` fora da faixa cai no 1º/último."""
    return CHAVE_POR_NUMERO[max(1, min(TOTAL_PASSOS, passo))]


def numero(chave_passo: str) -> int:
    return NUMERO_POR_CHAVE[chave_passo]
