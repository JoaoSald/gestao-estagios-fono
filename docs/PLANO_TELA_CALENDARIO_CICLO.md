# Tela "Calendário do ciclo" (passo 11) — TENTADA E REMOVIDA

**Status: REMOVIDA em 29/07/2026.** Construída em 28/07, testada pela comissão, redesenhada
na mesma noite e removida no dia seguinte. Este documento deixou de ser um plano de
implementação e passou a ser o **registro do porquê não fazer isso de novo**.

> O plano original (contratos, assinaturas, 4 fases de entrega, 12 testes) foi apagado
> junto com o código. Se alguém quiser reconstruí-lo, leia primeiro a seção "Por que
> falhou" — o problema não era a implementação.

---

## O que se tentou

Uma tela de **correção manual por aluno**: listar quem a alocação automática deixou sem
grupo e deixar a comissão remanejar à mão, com o molde do ciclo à vista. Escopo restritivo
por desenho: só alunos pendentes, só as áreas do próprio aluno se movem, nunca desloca
outro aluno, grupo lotado é intransponível.

Passou por três formas em dois dias:

1. **Calendário do ano como superfície de decisão** (28/07, manhã) — 10 meses, 1 chip por
   onda + ticks, coluna de CH semanal, clique no chip para alocar.
2. **Quadro de vagas com arrastar-e-soltar** (28/07, noite) — depois de "ficou muito
   poluído… fazer arrastando, não rodar um motor de novo". Calendário foi para trás de um
   botão.
3. **Removida** (29/07) — "ta ruim, muito poluído, não tem como entender logicamente…
   não funcionou esse propósito, muito difícil de ajustar".

## Por que falhou

**Resolvia um problema que os dados dizem não existir.** Medido no molde real do seed
(37 locais, 68–80 grupos, 10 alunos com pendência, 24 pendências):

* **0 de 24 pendências** tinham qualquer caminho por remanejo de 2 passos;
* Hospitalar-Adulto tinha **22 vagas livres** e **0 delas cabiam** nos alunos que faltavam;
* 2 dos 10 alunos pendentes tinham **zero** movimento possível — e eram justamente os que
  a tela abria primeiro (ordenava por "mais pendências").

Os alunos carregam ~8 áreas e chegam a 21h/30h de pico. O gargalo **não é a alocação**: é
a **oferta** (dia/horário/capacidade). Uma tela de ajuste fino de alocação não tem o que
ajustar — e passa à comissão a impressão oposta, de que há trabalho manual a fazer.

**O que confundiu o diagnóstico no caminho:** o primeiro teste da comissão parecia um
problema de desenho e era **CSS velho em cache** (grade empilhada em coluna, chips sem
estilo, zero erro no log). Isso queimou um ciclo inteiro de conversa. Ver
`core/templates.py::estatico()`.

## O que ficou (e deve ficar)

Melhorias no motor, usadas pela geração e **independentes da tela**:

| Onde | O que | Por quê fica |
|---|---|---|
| `motor/restricoes.py` | `ch_por_semana()` — CH em cada semana do ciclo, chaveada na segunda | `ch_pico` deriva dela; corrige subestimativa na fronteira de período (onda que fecha na terça 16/06 + outra que abre na quarta 17/06 caem na MESMA semana). Verificado no seed: escala gerada **idêntica** (90 alocações, 24 na fila) |
| `motor/restricoes.py` | `conflitos()` — todas as restrições violadas, com as caixas CULPADAS | `viola_restricoes` passou a ser `conflitos(...)[0].motivo`; uma implementação só. Habilita dizer "Voz na quarta é quem barra", não só "não cabe" |
| `motor/restricoes.py` | teto agora diz a semana: `"passaria de 30h na semana de 07/04"` | é o que o §5.3 pedia |
| `motor/preenchimento.py` | `motivo_sem_vaga()` público (era `_motivo_aguardando`) | recalcular o motivo fora da geração |
| `core/templates.py` + `base.html` | `estatico()` → `?v=<mtime>` em CSS/JS | **vale para todo o projeto**; sem isso nenhuma mudança de CSS chega a um navegador com a página aberta |
| `tests/test_motor_restricoes.py` | 4 testes migrados (série semanal, culpados, semana do teto) | são testes de motor, não de tela |

Removidos: `motor/encaixe.py`, `routers/ui/calendario_ciclo*.py`, `templates/partials/cc_*.html`
e `passo11.html`, o passo `encaixe` de `core/passos.py`, os blocos `.cc-*` do CSS e os
handlers do passo 11 no `app.js`, `tests/test_calendario_ciclo*.py`.

## Se o assunto voltar

A pergunta certa **não** é "como a comissão remaneja aluno à mão", é **"como a comissão
descobre que dia/horário abrir"**. Duas coisas concretas que a medição sustenta:

1. **`analise_grade.capacidade_vs_demanda` mente por otimismo.** Ela compara vagas totais ×
   demanda e diria saldo **+12** para Hospitalar-Adulto — quando 0 daquelas vagas cabem nos
   alunos que faltam. Falta cruzar a vaga com o **relógio** dos alunos que a disputam
   (`restricoes.viola_restricoes` já faz isso; é só agregar por área).
2. **Qual dia abrir.** Com `conflitos()` já é possível dizer, por área com fila: em que
   dia/turno os alunos que sobraram estão livres. Isso é uma linha de tabela no painel de
   oferta que os professores já usam — não uma tela nova.
