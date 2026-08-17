"""As restrições duras de carga (§3) + escassez (§6.4).

Barram a entrada de um aluno numa caixa. Invioláveis — inclusive no ajuste manual (§5.3):
não há override. Operam sobre os "compromissos" do aluno = as caixas que ele já pegou.
A CH relevante é a da semana de PICO (janelas sobrepostas), não a soma plana.

Um aluno PODE cursar áreas diferentes no mesmo dia (inclusive no mesmo turno). As ÚNICAS
restrições de carga são, portanto:
  1. sem sobreposição de horário entre as sessões do mesmo dia;
  2. intervalo mínimo de 1h30 entre o fim de uma sessão e o início da próxima no mesmo dia;
  3. teto de 30h de estágio por semana (semana de pico);
mais a blocklist de local. NÃO há limite de "1 estágio por dia" nem bloqueio por dobrar
o mesmo turno — o que importa é o relógio (sobreposição + intervalo), não o rótulo do turno.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, timedelta

from app.core.rotulos import rotulo
from app.services.motor.molde import Caixa

MAX_HORAS_SEMANAIS = 30.0
INTERVALO_MIN_HORAS = 1.5   # 1h30 entre áreas no mesmo dia (§3.2 · decisão §11.11)


@dataclass
class Conflito:
    """Uma restrição dura violada, com os CULPADOS nomeados (§5.3).

    É a forma detalhada do que `viola_restricoes` resume numa string. Existe para a
    revisão manual poder dizer "Audiologia II está barrada AQUI por causa de Voz na
    quarta" — e daí oferecer mover Voz. `caixas` = os compromissos culpados (vazio na
    blocklist, onde o culpado é o próprio local). `semana` só no teto.

    Homônimo proposital do `errors.Conflito` (exceção HTTP 409) — este é dado de
    diagnóstico, não exceção; onde os dois convivem, importe o de errors com alias.
    """
    tipo: str                                       # 'blocklist'|'sobreposicao'|'intervalo'|'teto'
    motivo: str                                     # pt-BR, padrão §5.3
    caixas: list[Caixa] = field(default_factory=list)
    semana: date | None = None                      # segunda-feira, só em 'teto'


def janelas_sobrepoem(ini_a, fim_a, ini_b, fim_b) -> bool:
    return not (fim_a < ini_b or ini_a > fim_b)


def _min(t: time) -> int:
    return t.hour * 60 + t.minute


def gap_horas(ai: time, af: time, bi: time, bf: time) -> float:
    """Horas de folga entre dois horários no mesmo dia. Negativo = sobreposição.

    Público: `analise_grade` reusa isto para dizer quais slots do mesmo dia são
    mutuamente exclusivos para um aluno — a regra tem que ser a MESMA do motor (§3).
    """
    if _min(af) <= _min(bi):
        return (_min(bi) - _min(af)) / 60.0
    if _min(bf) <= _min(ai):
        return (_min(ai) - _min(bf)) / 60.0
    return -1.0  # os horários se sobrepõem no relógio


def segunda_da_semana(d: date) -> date:
    """Segunda-feira da semana ISO de `d` — a chave canônica de "semana" no sistema."""
    return d - timedelta(days=d.weekday())


def ch_por_semana(caixas: list[Caixa]) -> dict[date, float]:
    """CH do aluno em CADA semana do ciclo. Chave = segunda-feira (§3.1/§5.2).

    Uma caixa contribui `c.horas` em toda semana que o seu período alcança (da semana do
    `data_inicio` à do `data_fim`). Caixas que não coexistem não competem — é por isso
    que a soma é por semana real e não "todas as que encostam nesta".

    **Escolha deliberada:** contenção-de-período, e NÃO "semanas com encontro real". A
    segunda seria mais precisa (uma semana cujo encontro caiu em feriado tem 0h), mas
    divergiria da restrição dura — a coluna da tela diria 26h enquanto o motor barra por
    30h. Uma verdade só, ainda que conservadora.
    """
    por: dict[date, float] = {}
    for c in caixas:
        semana = segunda_da_semana(c.data_inicio)
        ultima = segunda_da_semana(c.data_fim)
        while semana <= ultima:
            # round: soma de floats repetida produziria 30.000000000000004 e barraria
            # uma alocação que fecha exatamente no teto.
            por[semana] = round(por.get(semana, 0.0) + c.horas, 6)
            semana += timedelta(days=7)
    return por


def ch_pico(caixas: list[Caixa]) -> float:
    """Maior carga horária numa MESMA semana (§3.1/§5.2) — o que o teto de 30h limita.

    Derivado de `ch_por_semana`: a tela e a restrição dura leem a MESMA série semanal,
    então a coluna de CH nunca contradiz o motivo do bloqueio.
    """
    return max(ch_por_semana(caixas).values(), default=0.0)


def conflitos(
    compromissos: list[Caixa],
    caixa: Caixa,
    bloqueados: set[int],
) -> list[Conflito]:
    """TODAS as restrições duras violadas ao colocar o aluno em `caixa`, com os culpados.

    Irmã de `viola_restricoes` (que é `conflitos(...)[0].motivo`): mesma ordem de
    checagem, mesmas mensagens, mas nomeia as caixas responsáveis em vez de parar na
    primeira string. É o que permite à revisão manual propor "mova X para liberar Y".

    `compromissos` = caixas que o aluno já ocupa (não inclui `caixa`).
    `bloqueados` = local_ids na blocklist do aluno (§3, restrição 4).
    """
    local = caixa.local
    # 4. Blocklist de local — culpado é o próprio local, não há caixa a mover.
    if local.id in bloqueados:
        return [Conflito("blocklist", "local bloqueado para este aluno")]

    # Agrupa por tipo preservando a ordem em que o 1º culpado de cada tipo aparece —
    # assim `conflitos(...)[0].motivo` é exatamente o motivo que `viola_restricoes`
    # devolvia antes desta refatoração.
    culpados: dict[str, list[Caixa]] = {}
    for c in compromissos:
        if not janelas_sobrepoem(c.data_inicio, c.data_fim, caixa.data_inicio, caixa.data_fim):
            continue
        # Só há conflito de carga entre sessões que caem no MESMO dia da semana e cujos
        # períodos coexistem no calendário. Áreas diferentes podem dividir o dia (inclusive
        # o mesmo turno) — o que manda é o relógio: sem sobreposição + ≥1h30 de intervalo.
        if c.local.dia_semana != local.dia_semana:
            continue
        gap = gap_horas(c.local.hora_inicio, c.local.hora_fim, local.hora_inicio, local.hora_fim)
        # 1. Sem sobreposição de horário no mesmo dia.
        if gap < 0:
            culpados.setdefault("sobreposicao", []).append(c)
        # 2. Intervalo mínimo de 1h30 entre áreas no mesmo dia.
        elif gap < INTERVALO_MIN_HORAS:
            culpados.setdefault("intervalo", []).append(c)

    # A frase (e o `rotulo`) só é montada quando há de fato conflito: esta função está no
    # caminho MAIS quente do motor — o preenchimento a chama centenas de milhares de vezes
    # e, na esmagadora maioria, não há nada a relatar. Montar f-strings à toa custava mais
    # que a checagem em si.
    achados: list[Conflito] = []
    if culpados:
        dia = rotulo(local.dia_semana)
        frases = {
            "sobreposicao": f"sobreposição de horário com outra área no mesmo dia ({dia})",
            "intervalo": f"faltam 1h30 entre áreas no mesmo dia ({dia})",
        }
        achados = [Conflito(tipo, frases[tipo], caixas) for tipo, caixas in culpados.items()]

    # 3. Teto de 30h/semana — a PRIMEIRA semana que estoura, com as caixas dessa semana.
    #    Só as semanas ALCANÇADAS pela caixa nova podem passar a estourar (as outras têm a
    #    mesma soma de antes), então basta somar a série dos compromissos nessas semanas.
    ini_nova = segunda_da_semana(caixa.data_inicio)
    fim_nova = segunda_da_semana(caixa.data_fim)
    serie = ch_por_semana(compromissos)
    semana = ini_nova
    estourada: date | None = None
    while semana <= fim_nova:
        if serie.get(semana, 0.0) + caixa.horas > MAX_HORAS_SEMANAIS:
            estourada = semana
            break
        semana += timedelta(days=7)
    if estourada is not None:
        na_semana = [
            c for c in compromissos
            if segunda_da_semana(c.data_inicio) <= estourada <= segunda_da_semana(c.data_fim)
        ]
        achados.append(Conflito(
            "teto",
            f"passaria de {MAX_HORAS_SEMANAIS:g}h na semana de {estourada.strftime('%d/%m')}",
            na_semana, estourada,
        ))
    return achados


def viola_restricoes(
    compromissos: list[Caixa],
    caixa: Caixa,
    bloqueados: set[int],
) -> str | None:
    """Motivo (pt-BR) da 1ª restrição violada ao colocar o aluno em `caixa`, ou None."""
    achados = conflitos(compromissos, caixa, bloqueados)
    return achados[0].motivo if achados else None


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
