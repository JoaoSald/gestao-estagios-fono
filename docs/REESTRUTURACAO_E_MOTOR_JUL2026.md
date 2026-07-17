# Reestruturação + regras de motor — rodada jul/2026

Fonte de verdade: protótipo `versao_2` (mock.js seed v12) validado headless.
Este documento é a **spec** das regras decididas nesta rodada. A **modelagem** já
foi aplicada ao data layer do repo real (migration `d4e8a1c6f3b2`); as regras de
**motor/tela** ficam aqui como spec para a FASE 4 (motor) e FASE 5 (front).

> **⚠️ Motor superado (rodada seguinte):** as regras de **geração da escala** deste
> documento (motor puxado pela demanda / linha do tempo) foram **substituídas** pelo
> modelo **grade-primeiro** em `REGRAS_MOTOR_ESCALA.md` — use aquele como fonte de
> verdade do motor. A **modelagem** abaixo (§1: sub-áreas, slot, fase) **permanece
> válida** e é a base do grade-primeiro.

## 1. Modelagem (JÁ no schema — migration d4e8a1c6f3b2)

- **Sub-áreas / áreas compostas**: `areas.composta` (container, ex.: Audiologia II,
  Hospitalar — não matriculável/alocável, sem locais) + `areas.area_mae_id` nas
  sub-áreas leaf. CH da mãe = soma das sub-áreas; **matrícula e conclusão são por
  sub-área**. Locais apontam só para leaf.
- **Fase**: enum `fase_area` renomeado `'7'` (Audiologia I) e `'9_10'` (demais).
  `alunos.semestre ∈ {7, 9, 10}`.
- **Modelo SLOT**: cada local = 1 (campo+dia+turno). Um campo com N dias vira N
  locais, que rodam **em paralelo** (grupos simultâneos). Novo `locais.horas_sessao`
  (horas reais/encontro); `numero_encontros = teto(carga_horaria / horas_sessao)`.
  Aposentada a tabela `locais_dias` (multi-dia).
- Seed: catálogo 2026 = 14 áreas (2 compostas + 6 sub-áreas) · 18 docentes · 12
  preceptores · 37 locais (slot).

## 2. Motor por LINHA DO TEMPO (FASE 4)

Simulação **cronológica global** (todas as áreas juntas), não área-por-área:
abre as ondas futuras em ordem de data entre todos os slots e, em cada abertura,
puxa da fila (por prioridade) quem PODE entrar. Garante:

- **Mínima espera**: cada aluno pega a leva mais cedo viável somando TODAS as áreas.
- **Empacotamento**: fecha a capacidade de uma onda antes de abrir a próxima.
- **Restrições respeitadas**: capacidade, conflito de dia/turno, **teto de 30h/semana**
  (`MAX_HORAS_SEMANAIS = 30`), restrição de local do aluno (blocklist).
- **Transparência**: quem é adiado carrega o motivo ("aguarda concluir X até dd/mm"
  ou "evita passar de 30h").

### 2.1 Corte de ciclo (um ano)
O ciclo dura um ano; o motor **não projeta ondas além de `ciclo.data_fim`**. Uma
onda só é criada se COUBER inteira no ciclo (`data_fim ≤ fim do ciclo`). Quem não
couber fica **"Aguardando vaga · próximo ciclo"** (visível, sem data falsa) — refaz
no próximo ciclo. Ex. validado: leva de 20 encontros começando em ago/2026 fecharia
só em 18/dez, e o ciclo acaba em 11/dez → não cabe → próximo ciclo.

## 3. Seleção de áreas por aluno (demanda real)

O 9/10 **não faz todas as áreas**: o professor escolhe o subconjunto obrigatório
por aluno no ciclo (checkboxes por área; novo aluno vem DESMARCADO; 7º só Aud I).
Área não selecionada = **"Não faz neste ciclo"** (neutra, **não é pendência**). O
progresso e o encerramento contam só o **plano** (áreas matriculadas): "ciclo
completo" = concluiu o plano dele. Esqueceu uma área → matricula depois e o motor
recalcula.

## 4. Ordenamento (prioridade)

**1 por aluno**, numerado **por fase** (7º e 9/10 cada um 1..k, independentes — as
fases nunca disputam o mesmo local). Definido no passo Alunos por **arrastar** OU
**digitar** a posição. Sem ordenamento → fim da fila. O motor consome por área.

## 5. Grupos / remanejo / ajuste manual

- **Mover aluno entre grupos**: "bloqueia e sugere" — o movimento só ocorre se a
  onda destino tem vaga, sem conflito de dia/turno e sem estourar 30h; senão mostra
  o motivo e sugere a leva mais cedo viável.
- **Toda alteração é GATILHO de remanejo**: matrícula, afastamento, interrupção,
  local etc. setam `escala_desatualizada` + enfileiram; a escala só recalcula quando
  o usuário APLICA o remanejo (revisão deliberada, incremental, preserva ajustes).
- **Overflow visível**: matriculados sem grupo (não coube no ciclo) aparecem na aba
  Grupos numa faixa "Aguardando vaga · próximo ciclo" por área — nunca somem.

## 6. Onde está implementado (referência)

Tudo acima está implementado e validado no protótipo `versao_2` (`js/state.js`,
`js/views/*`), que serve de guia de tradução para o motor Python (FASE 4) e os
templates Jinja (FASE 5). Ver `docs/prototipo_js/`.
