# Backlog — Versão 2 (pós-lançamento)

Itens mapeados durante o desenvolvimento da v1 que **não entram no lançamento** e ficam
planejados para uma futura v2. Cada item descreve o **caso**, o **estado atual do sistema**
(com referências de arquivo), **o que precisa mudar por camada**, a **dificuldade** e as
**abordagens** possíveis. Serve de ponto de partida para quem for implementar — não é
especificação fechada; decisões em aberto estão marcadas.

> Convenção: `BL-NN` = id do item. Dificuldade: 🟢 Baixa · 🟠 Média · 🔴 Alta.
> Referências de código no formato `arquivo:linha` apontam para o estado da v1 no momento
> em que o item foi mapeado — reconfira antes de implementar.

---

## BL-01 — Exceções de carga por aluno em áreas compostas (condição especial)

**Dificuldade global: 🔴 Alta** (dominada pela camada de motor).
**Status:** mapeado, não iniciado. **Prioridade sugerida:** média (casos raros, mas reais).

### Caso real

Áreas compostas (`Hospitalar`, `Audiologia II`) hoje são cursadas dividindo a carga entre
sub-áreas. Alguns alunos têm **condição especial** (ex.: transtorno do espectro autista) e
**não podem cursar uma das sub-áreas** — por exemplo, não fazer as 50h de **Neonatologia**.
Em vez de dividir Hospitalar em Pediatria + Adulto + Neo, esse aluno precisa cumprir as
**160h inteiras de Hospitalar concentradas em Adulto**.

Como um grupo/onda de Adulto entrega ~60h, o aluno teria que **atravessar grupos consecutivos**
do mesmo local até somar o alvo: G1 60h → G2 60h → G3 40h = **160h**. A última onda é **parcial**.

O padrão continua igual para todos os outros alunos; a exceção é **opt-in, por aluno**.

### Estado atual do sistema (o que impede hoje)

- **Áreas são uma árvore de 2 níveis** (`app/models/catalogo.py:19-48`): a **composta**
  (`composta=true`, sem locais, não matriculável) e as **sub-áreas leaf** (`area_mae_id`
  aponta para a mãe, cada uma com seu `carga_exigida` e seus locais). Ex. no seed
  (`docs/seed_v2.sql:16-30`): `Hospitalar (160)` = `Pediatria (50)` + `Adulto (60)` +
  `Neonatologia (50)`; `Audiologia II (110)` = `SADT (40)` + `ORL (10)` + `Santa Marta (60)`.
- **Matrícula e conclusão são por sub-área leaf** (`app/models/aluno.py:56-78`, único
  `(aluno_id, area_id)`). Matricular na composta é **explicitamente rejeitado**
  (`app/services/matricula.py:73-74`). Logo, um aluno de Hospitalar tem **3 matrículas
  independentes**, cada uma concluída por conta própria.
- **`Area.carga_exigida` NÃO é lido pelo motor.** Quem dita o tamanho é o
  **`Local.numero_encontros`** = `teto(carga_horaria ÷ horas_sessao)`
  (`app/models/local.py:54-58`). A carga da mãe (160) é só uma **soma convencional**,
  não calculada nem validada em runtime.
- **"Uma caixa = uma conclusão de área"** (spec `docs/REGRAS_MOTOR_ESCALA.md` §2, §4:117,
  §11 decisão 3 em `:532`). O molde fatia o local em blocos de `N=numero_encontros`
  (`app/services/motor/molde.py:57-84`); terminar **uma** caixa fecha a área.
- **O preenchimento descarta a área após 1 caixa** (`app/services/motor/preenchimento.py:66-86`):
  ao sentar o aluno numa caixa, remove a área de `pendentes` — **nunca** senta uma 2ª caixa
  da mesma área para acumular horas.
- **Conclusão** (`app/services/motor/encontros.py:32-90`): `feitos >= total`, com
  `total = numero_encontros` de **uma** caixa. Já existe soma de `cumprida` **entre alocações**
  da mesma matrícula (`contar_encontros`), mas é usada só para **carry-forward** quando um
  local morre — não para somar caixas cheias rumo a um alvo maior.
- **Não existe override de carga por aluno, isenção nem customização por sub-área.** A única
  "condição especial" hoje é a **blocklist de local** (`RestricaoAlunoLocal`,
  `app/models/aluno.py:81-99`), que apenas impede o aluno de frequentar certos locais.

**Conclusão:** o alvo (160h de Hospitalar só em Adulto, acumulando entre grupos) **não cabe
em nenhum conceito atual**. Precisa de (a) um **alvo de carga por aluno** que sobreponha a
divisão padrão das sub-áreas, e (b) **acumulação multi-caixa** rumo a esse alvo.

### O que precisa mudar (por camada)

| Camada | Dificuldade | Mudança |
|---|---|---|
| **Modelo de dados** | 🟢 Baixa | Aditivo: por matrícula, um **alvo de carga/encontros** (nullable, override) e a marcação de **sub-áreas isentas/redistribuídas** (coluna na matrícula ou tabela nova de exceção por aluno). Migration simples e opt-in. |
| **Matrícula / cadastro** | 🟠 Média | Permitir a exceção: em vez das 3 sub-áreas padrão, matricular só a sub-área destino (Adulto) com **alvo aumentado**, e registrar as isentas. Ajustar `matricula.sincronizar` e o `_areas_check` (`cadastros.py:303-320`). |
| **Motor — preenchimento/molde** | 🔴 Alta | Quebrar "uma caixa = uma conclusão": para matrículas com alvo, **encadear ondas consecutivas do mesmo local até somar o alvo**, com a **última onda parcial**. Rever objetivo cobertura/lotação, contagem de **capacidade** (o aluno ocupa 1 assento por onda) e o determinismo grade-primeiro. |
| **Conclusão** | 🟠 Média | Trocar `total = max(numero_encontros)` por um **alvo** e concluir por **soma de horas cumpridas ≥ alvo** (pode ser no meio de uma caixa). A soma entre alocações **já existe** (`encontros.contar_encontros`). |
| **Ajuste / montagem / consolidação / estado** | 🟠 Média-Alta | Todos assumem **1 caixa por (aluno, área)**. Mover/remover/consolidar/travar e o `sentar/levantar` (`estado.py`) precisam entender o vínculo multi-caixa. Cuidado com unique constraints em `alocacoes`. |
| **UI/UX** | 🟠 Média | Ver abaixo. |
| **Testes** | 🟠 Média-Alta | Re-testar cobertura, capacidade, conclusão por alvo e onda parcial. |

### Impacto em UI/UX

- **Cadastro do aluno:** bloco "condição especial" — para uma área composta, escolher
  sub-áreas isentas e **redistribuir a carga** (ex.: "concentrar tudo em Adulto"), mostrando
  o **alvo calculado** (160h). Hoje o form pré-marca todas as sub-áreas da fase
  (`form_aluno.html` + `_areas_check`).
- **Grupos / calendário de estágios:** o aluno passa a aparecer em **vários grupos consecutivos**
  do mesmo local, com **progresso de carga** ("120/160h") e destaque da **onda parcial** final.
- **Risco de fechamento de carga** (spec §9) e **exports** (Excel/PDF de grupos) passam a ser
  **por aluno**, não por carga fixa da área.

### Abordagens

**A) Completo — automático (🔴 Alta, esforço grande).**
O motor entende o alvo, encadeia ondas sozinho, conclui por soma de horas e a UI mostra tudo.
Melhor experiência; exige vários PRs e re-teste amplo do motor.

**B) MVP — exceção manual (🟠 Média, recomendado como 1ª entrega).**
Como os casos são raros e por aluno, a comissão trata **à mão**:
1. Modelo: alvo de carga na matrícula + isenção de sub-áreas (barato).
2. Motor: **não forçar** a conclusão em 1 caixa para matrículas marcadas — deixar a comissão
   colocar o aluno em N ondas consecutivas do local (via Montagem/Ajuste).
3. Conclusão/relatório: **somar horas cumpridas** dessas alocações e concluir ao atingir o alvo
   (mostrar "120/160h"). Reaproveita a soma entre alocações que já existe.

Entrega o resultado clínico sem reescrever a otimização automática; evolui para (A) depois.

### Decisões em aberto

- O alvo é expresso em **horas** ou em **nº de encontros**? (o motor pensa em encontros; a
  comissão pensa em horas — precisa de conversão consistente com `horas_sessao`).
- A exceção vive em **`Matricula`** (alvo por sub-área) ou numa **tabela nova** de exceção por
  aluno × área composta (mais expressiva para isenção + redistribuição)?
- Na acumulação, o aluno ocupa **1 assento por onda** — como isso pesa na cobertura/lotação e
  no alerta de escassez de vagas?
- Interação com **passagem de grupo** e com o **remanejo pontual** (§7.3) quando uma das ondas
  encadeadas é afetada por feriado/afastamento.
- Carry-forward entre ciclos (§10) de uma matrícula com alvo parcialmente cumprido.

### Critérios de aceite (cenários)

1. Aluno com isenção de Neonatologia e alvo de **160h em Adulto** → alocado/concluído em ondas
   consecutivas do local de Adulto (60+60+40), **sem** matrícula em Pediatria/Neo.
2. A **última onda é parcial** (40h) e a conclusão dispara ao atingir 160h, não ao fim da caixa.
3. Aluno **sem** exceção continua com o comportamento atual (1 caixa = 1 conclusão), inalterado.
4. Progresso de carga e risco aparecem corretos na UI ("X/160h") e nos exports.
5. As restrições duras (sem sobreposição, 1h30, 30h/semana, blocklist) seguem válidas em cada onda.
