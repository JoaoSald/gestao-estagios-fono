# Regras de Negócio — Sistema de Gestão de Estágios

**Curso de Fonoaudiologia — UFCSPA · Versão 2**

Este documento consolida **todas as regras de negócio** do sistema. É a
especificação de referência para a implementação do backend (FastAPI +
SQLAlchemy + PostgreSQL). O protótipo front-end (`versao_2/`) implementa e
valida estas regras; a modelagem está em `modelagem_dados_v2.dbml.txt` /
`modelagem_dados_v2.sql`.

> **Natureza do sistema:** é um **planejador de escala de estágios**, não um
> controle de frequência nem um diário de classe. Ele projeta *quando* cada
> aluno cumpre a carga e *quando* as vagas liberam — assumindo que os encontros
> planejados acontecem.

---

## 1. Ciclo (máquina de estados)

O **ciclo** representa um ano letivo de estágios e é a espinha dorsal do sistema.

- Estados: `nenhum` → `rascunho` → `em_andamento` → `encerrado`.
- **No máximo um** ciclo `rascunho` **ou** `em_andamento` por vez.
- O estado define a tela inicial:
  - *nenhum* → Boas-vindas (abrir novo ciclo).
  - `rascunho` → Bootstrap (carrossel de cadastro), retomável no passo salvo.
  - `em_andamento` → Painel de Operação.
  - `encerrado` → arquivado no Histórico.
- Transições: confirmar o bootstrap leva `rascunho → em_andamento`; encerrar o
  ano leva `em_andamento → encerrado` (gera o histórico).

---

## 2. Fases do curso (7º semestre × 9º/10º)

Convivem no **mesmo ciclo** dois grupos de alunos, com regras distintas:

- **7º semestre — mini-ciclo:** cursa **somente o Estágio de Audiologia I**.
- **9º/10º semestre:** cursa as **demais áreas** (todas exceto Audiologia I).

A fase é derivada do `semestre` do aluno: `semestre ≤ 7` → fase 7 (Audiologia I);
`semestre ≥ 8` → fase 9/10. Enum `fase_area`: `'7' | '9_10'`. O nº de alunos por
fase **não é fixo** — a coordenação cadastra quantos quiser por ciclo (por demanda).

---

## 3. Catálogo de áreas, sub-áreas e carga horária *(revisto)*

As **áreas** têm uma **carga exigida** (horas para concluir). Uma área pode ser
**simples** (o aluno cumpre a CH em **qualquer** local dela — ex.: Voz, Motricidade)
ou **composta**: tem **sub-áreas obrigatórias**, cada uma com CH própria e ligada a
campo(s) específicos. A **área-mãe é um container real** (`composta: true`) com a **CH
total**; ela **não é matriculável/alocável** (não tem locais próprios). As sub-áreas são
**áreas leaf separadas** (matrícula, locais e conclusão por sub-área) que referenciam a mãe
por **`area_mae` = id da mãe**; suas CHs **somam o total** da mãe. A mãe só conclui quando
**todas** as sub-áreas concluem. No **cadastro (bootstrap, passo Áreas)** as sub-áreas são
criadas/removidas **dentro da edição da área-mãe** — genérico: qualquer área pode virar
composta.

| Área (mãe) | Sub-área | Fase | CH exigida |
|---|---|---|---|
| Audiologia I | — (simples) | 7º | 60h |
| Motricidade Orofacial | — | 9/10 | 120h |
| Linguagem Infantil | — | 9/10 | 160h |
| Saúde Coletiva | — | 9/10 | 160h |
| LAD — Linguagem do Adulto/Idoso | — | 9/10 | 80h |
| Voz | — | 9/10 | 80h |
| **Audiologia II** *(composta)* | SADT (SA) | 9/10 | 40h |
| **Audiologia II** | Ambulatório ORL — TAN | 9/10 | 10h |
| **Audiologia II** | AMB. Santa Marta (SM) | 9/10 | 60h |
| **Hospitalar** *(composta)* | Pediatria | 9/10 | 50h |
| **Hospitalar** | Adulto | 9/10 | 60h |
| **Hospitalar** | Neonatologia | 9/10 | 50h |

- **Audiologia II** e **Hospitalar** seguem o **mesmo critério**: o aluno cumpre a CH de
  **cada** sub-área obrigatoriamente (Aud II = 40+10+60; Hospitalar = 50+60+50 = 160h).
- O contador de progresso (`X/N`) conta as áreas **leaf** da fase (9/10 = 11 leaves).

> ⚠️ **Pendência:** CH das sub-áreas hospitalares ainda a confirmar com a coordenação.

---

## 4. Pré-requisito Audiologia I — responsabilidade compartilhada *(regra revista)*

**Audiologia I é pré-requisito curricular dos estágios de 6º/7º** — mas a verificação
é de **responsabilidade compartilhada** (coordenação + sistema), **não uma trava**.

- **Não bloqueia.** O sistema **não impede** a matrícula nem a alocação de um aluno de
  6/7 por falta de registro de Audiologia I. Quem cadastra **conhece o histórico real**
  do aluno (semestres/ciclos anteriores), que nem sempre está registrado aqui.
- **Alerta para conferir (não-bloqueante).** Ao **cadastrar/matricular** um aluno de
  6/7, se **não houver registro** de Audiologia I concluída, o sistema mostra um
  **aviso** — *"Sem registro de Audiologia I — conferir"* — só para o professor
  **confirmar**. Havendo o registro, aparece como **concluído**. Em nenhum dos casos o
  fluxo é interrompido.
- **Por que mudou (era bloqueante):** na prática **todo aluno de 6/7 já entra com
  Audiologia I concluída** (§5), e o registro pode faltar por ser de ciclo anterior —
  uma trava geraria **falso impedimento**. A decisão fica com quem tem o histórico; o
  sistema **apoia com um lembrete**, não substitui o julgamento humano.

> **Princípio de responsabilidade compartilhada:** onde o sistema não tem como garantir
> um dado que o humano conhece, ele **sinaliza para conferência** em vez de bloquear.

---

## 5. Carry-forward (áreas já concluídas ao entrar no ciclo)

Um aluno pode **iniciar o ciclo com áreas já concluídas**, cursadas em
semestres/ciclos anteriores — ele só cursa **o que falta**.

- **Todo aluno de 6º/7º começa com Audiologia I concluída.**
- Alguns podem começar também com outras áreas de 6/7 já concluídas.
- Tecnicamente: a matrícula nasce com status `concluida`. O motor **só aloca as
  matrículas `em_andamento`**, então as concluídas são puladas naturalmente e
  contam como carga cheia no progresso.

---

## 6. Matrículas por área

A matrícula diz **o que** o aluno cursa (par aluno × área):

- **Quem cria e como:** o professor/coordenação matricula o aluno nas áreas pela
  tela de Alunos. A matrícula é **flexível, a critério do usuário** — pode-se
  matricular o aluno em **todas as áreas da fase de uma vez** ou em **apenas
  algumas**, acrescentando as demais depois. As áreas matriculadas que não couberem
  de imediato numa vaga ficam na **fila de espera** (§10) e entram conforme as vagas
  liberam.
- Status: `em_andamento` | `concluida` | `interrompida` (ver §6.1).
- **"A iniciar"** é um estado **derivado**: área do catálogo (da fase do aluno)
  **sem matrícula** = ainda não começou. O conjunto completo de estados derivados
  (a iniciar / aguardando vaga / em andamento / em risco / concluída / interrompida)
  está em **§6.3**.
- **Conclusão é automática**, nunca um check manual (ver §8).

### 6.1. Desmatrícula / interrupção do estágio *(regra nova)*

Um aluno pode, por motivo **extraordinário** (ex.: saúde mental), sinalizar à
coordenação que **não vai mais cursar** um estágio no ciclo corrente. É uma
**operação do dia a dia**, disponível **após o bootstrap** (ciclo `em_andamento`),
na **página de detalhe do aluno**: veem-se as áreas em que ele está matriculado e,
na área desejada, o botão **"Interromper estágio"** (com motivo opcional).

Ao interromper, o sistema:

1. marca a matrícula daquela área como **`interrompida`** (guarda **motivo** e
   **data**) — a matrícula **não é apagada** (preserva o histórico);
2. **cancela a alocação** ativa e as **sessões futuras** (as já cumpridas ficam
   como registro);
3. **libera a vaga** (deixa de ocupar) → ao regerar a escala, o **próximo da fila**
   (por `ordenamento`) entra no lugar (§10);
4. marca a **escala como desatualizada** e registra na **fila de remanejo** + log de
   atividade.

**Encerramento e ano seguinte:** no encerramento, a área interrompida fica
**`pendente`** no histórico (§14). No **próximo ciclo** ela renasce `em_andamento`
para ser refeita — mesma mecânica do **carry-forward** (§5): áreas concluídas antes
voltam `concluida`, a interrompida volta a cursar.

> **Diferente de "excluir aluno":** excluir é para **corrigir cadastro errado**
> (apaga tudo). Interromper é um evento **real e registrado** da vida do aluno.

### 6.2. Restrições de local do aluno *(regra nova)*

Sem isso, o motor alocaria o aluno em **qualquer** local da área. Alguns alunos,
porém, têm **condições especiais** e **não podem** frequentar determinados locais.

- **Padrão:** todo aluno está **disponível em todos os locais**. A restrição é
  **exceção** — armazena-se apenas o que foi **desmarcado** (lista de locais
  bloqueados por aluno).
- **Granularidade: por local** (não por área). O aluno continua cursando a área,
  mas o motor **só o aloca nos locais liberados** daquela área. A tela agrupa os
  locais **por área** (dá para desmarcar um local ou a área inteira de uma vez).
- **Onde configurar:** no **cadastro do aluno** — tanto no **bootstrap** quanto na
  **operação do dia a dia** (mesma tela de editar aluno).
- **Efeito no motor:** ao procurar vaga numa área, o motor **pula os locais
  bloqueados** para aquele aluno.
- **Validação ao salvar (impede):** se as restrições deixarem uma área **matriculada
  em andamento sem nenhum local liberado**, o sistema **avisa e bloqueia** o
  salvamento — a comissão precisa liberar ao menos um local ou remover a matrícula.
  (Se ainda assim ocorrer em operação — ex.: um local liberado é desativado depois —,
  o aluno cai como **sem vaga** com o motivo "restrição de local", ver §10.)

### 6.3. Estado derivado da área e leitura por aluno *(regra nova)*

Cada par **aluno × área** tem um **estado derivado** — **não persistido**, calculado
a partir do status da matrícula **+** a existência de **alocação ativa**. São os
valores que a visão usa (lista de Alunos e detalhe do aluno):

| Estado | Como se deriva | Significado |
|---|---|---|
| **A iniciar** | área da fase **sem matrícula** | ainda não começou (não está em nenhuma fila) |
| **Aguardando vaga** | matrícula `em_andamento` **sem alocação ativa** | matriculado, na **fila** da área (§10) |
| **Em andamento** | matrícula `em_andamento` **com alocação ativa**, conclui **dentro** do ciclo | cursando, com vaga |
| **Em risco** | matrícula `em_andamento` com alocação ativa, conclusão prevista **após** o fim do ciclo | não fecha no prazo (§9) |
| **Concluída** | matrícula `concluida` | aprovado na área (§8.2) |
| **Interrompida** | matrícula `interrompida` (§6.1) | pausada, refaz no próximo ciclo |

- **Distinção-chave:** *Aguardando vaga* **≠** *Em andamento*. Só está **em andamento**
  quem tem **vaga alocada**; matriculado **sem vaga** é **aguardando** (na fila). O motor
  e o read-model **devem expor os dois separadamente** — a coordenação bate o olho e
  identifica quem está **travado na fila** vs. quem está de fato cursando.
- **Lista de Alunos (Matriculados):** três contagens por aluno — **Em andamento**,
  **Aguardando** e **Concluído** — para leitura imediata da situação da turma.
- **Detalhe do aluno:**
  - cada área **Aguardando vaga** mostra a **posição na fila** e a **previsão de início**
    (reaproveita a projeção de entrada de §10.1);
  - cada área **A iniciar** = área da fase **ainda não matriculada** (não confundir com
    "aguardando");
  - **Resumo de risco:** quando o aluno está *Em risco*, o detalhe exibe **por quê** —
    lista as áreas que concluem **após o fim do ciclo** (data prevista × fim do ciclo)
    **e** as áreas ainda **aguardando vaga** (que podem não começar a tempo).

---

## 7. Motor de alocação (geração da escala)

> **Modelo de SLOT-DIA (revisto):** cada **local** representa **um (campo + dia +
> turno)** — um campo que atende em 3 dias vira **3 locais/slots**. Cada slot é **1
> grupo** que roda **1×/semana** no seu dia, **em paralelo** com os outros dias do
> mesmo campo/área (ex.: Audiologia I terça/quinta/sexta = 3 grupos simultâneos).
> O aluno faz a área inteira **num slot**; numa área **composta**, ocupa **um slot por
> sub-área**. **`numero_encontros` do slot = `teto(CH da área ÷ horas por encontro)`**
> (ex.: Aud I 60h ÷ 4h30 ≈ 14). Isso acelera a conclusão e libera vaga mais cedo.
>
> **Slot = campo + dia + turno + horário** (não o campo físico). O mesmo campo pode
> ter o **mesmo dia em turnos diferentes** — 2 slots, 2 grupos. Cada slot tem **seus
> próprios responsáveis**: **1 docente** (obrigatório) + **0/1 preceptor** de campo
> (opcional, pode repetir). O slot é criado no passo *Áreas e Locais* e os
> responsáveis no passo *Configurações de campo*. Glossário completo em
> `REGRAS_MOTOR_ESCALA.md §2`.
>
> **Prioridade + Montagem manual (AR-8) — responsabilidade compartilhada:** a alocação é
> decidida em conjunto (a coordenação monta o essencial à mão, o motor completa). No cadastro,
> marca-se só uma **checkbox `prioridade`** por aluno — **sem ordenação manual** (o `ordenamento`
> vira derivado: prioritários primeiro, depois por matrícula). No passo **Montagem dos grupos**
> o sistema materializa o **molde** (caixas por slot, com datas e capacidade) e a coordenação
> **arrasta** os prioritários para as vagas; o resto o motor preenche ao gerar (prioritários
> não-colocados → depois por matrícula). O chip do aluno mostra a **CH da semana** (pico por
> janela sobreposta), respeitando o teto de **30h/semana** — colocar acima é recusado, e tirar
> (×) libera a CH. Aluno do **7º (mini-ciclo) só cursa Audiologia I**.

O motor gera a escala respeitando a **prioridade** e as restrições. Para cada
ciclo:

1. Ordena os alunos por **ordenamento** (menor = maior prioridade).
2. Para cada aluno, percorre suas matrículas `em_andamento`:
   - **Pré-requisito Audiologia I (§4): não bloqueia.** Se não houver registro de
     conclusão, o sistema apenas **sinaliza para conferência** — a alocação prossegue.
   - **Escolhe o local dentro da área (§7.3):** distribui os alunos pelos **locais
     ativos da área** preenchendo a **capacidade** de cada um. O aluno cai em **outro
     local da mesma área** quando o local preferido está **cheio**, quando há
     **conflito de dia/turno** com outra alocação dele, ou quando há **restrição de
     local** (§6.2). Só quando **todos os locais da área** estão cheios ou
     incompatíveis é que o aluno vai para a **fila** (§10).
   - Respeita **intervalo mínimo de 2h** entre áreas no mesmo dia.
   - **Teto de 30h semanais (§7.4):** não aloca se a área estourar as 30h da semana do
     aluno — nesse caso a matrícula vai para a **fila** e a coordenação é avisada.
3. Ao alocar, **projeta os encontros** (§8) e grava a alocação.

**Saída do motor:** `matrículas` (o quê) → `alocações` (onde) → `sessões` (quando).

### 7.1. A escala gerada é uma sugestão editável (ajuste manual) *(regra nova)*

A escala do motor é um **ponto de partida**, não um resultado fechado. A coordenação
pode **ajustá-la à mão** para chegar no resultado esperado. **Não muda a modelagem**
(usa `alocacoes`, `sessoes` e o campo `travada` que já existem) — é regra de **motor +
tela**.

- **Operações:** **mover** um aluno para outro local da mesma área; **adicionar** um
  aluno (da fila / elegível) numa vaga; **remover** um aluno de um local (libera a vaga).
  No **nível de grupo/onda** (mover aluno entre grupos, mover grupo inteiro, inclusive
  futuros), ver **§10.3**.
- **Trava automática:** toda alocação mexida à mão fica **`travada`** — numa futura
  regeração/remanejo o motor **respeita** o ajuste e só mexe no resto.
- **Ao ferir uma regra** (vaga cheia, passa de 30h, choque de horário, local restrito
  ao aluno): o sistema **avisa e deixa a coordenação decidir** (não bloqueia) — o
  objetivo é permitir o resultado esperado, inclusive em exceções.
- **Sentar a próxima turma "de agora":** uma alocação manual gera as sessões **a partir
  da data atual** (não recomeça do início do ciclo), permitindo dar sequência no meio
  do ano sem regenerar tudo.

### 7.2. Concluir grupo (dar sequência à próxima turma) *(regra nova)*

Atalho para **concluir de uma vez** o grupo atual de um local (todos os alunos daquela
leva), em vez de ajustar aluno por aluno. Ao concluir:

- os encontros dos alunos do grupo são **completados** (feitos = total) → as áreas
  **concluem** (§8) e a **vaga é liberada**;
- com a vaga livre, a coordenação **senta o próximo grupo** (fila) via **ajuste manual**
  (§7.1), começando de agora — dando **sequência à nova turma**.

Também usa só o que já existe (o ajuste de encontros de §8.3) — **sem mudança de
modelagem**.

### 7.3. Escolha de local dentro da área (capacidade → spill) *(regra nova)*

Uma área tem **N locais** (campos), cada um com sua **capacidade**. O motor **preenche
a capacidade** dos locais — a lógica de **grupos/ondas** (§10.2): uma leva enche um
local e cursa junta. A regra de **para qual local vai cada aluno**:

- **Preferência:** preencher os locais da área até a **capacidade** de cada um (mantém
  as levas coesas).
- **Spill (vai para outro local da mesma área) quando o local preferido:**
  1. está **cheio** (capacidade atingida);
  2. tem **conflito de dia/turno** com outra alocação do aluno;
  3. está **bloqueado** para aquele aluno por **restrição de local** (§6.2).
- **Fila:** só quando **todos os locais** da área estão **cheios ou incompatíveis** para
  o aluno é que ele entra na **fila** (§10) — estado *Aguardando vaga* (§6.3).

> Exemplo (Audiologia I, Local A cap. 4 · Local B cap. 4): alunos 1–4 enchem o A;
> aluno 5 vai para o B (A cheio); aluno 6, com conflito no A e no B, vai para a fila.

### 7.4. Teto de 30h semanais *(regra nova)*

Um aluno **não pode ultrapassar 30h de estágio por semana**. É um **limite** (teto),
**não uma meta** de preenchimento — é o que **segura as demais matrículas na fila**
mesmo quando há vaga disponível.

- Ao alocar, o motor **soma a carga semanal** já alocada ao aluno. Se a próxima área
  **estouraria as 30h** da semana, ela **não é alocada agora**: vai para a **fila**
  (estado *Aguardando vaga*, §6.3) com o motivo **"teto de 30h semanais atingido"**.
- **Sinalização:** o sistema **avisa a coordenação** de que as 30h do aluno já foram
  preenchidas (por isso a matrícula extra ficou aguardando) — não é bloqueio silencioso.
- Essa matrícula entra **quando abrir espaço na semana** — tipicamente quando uma área
  atual **conclui** e libera horas (gatilho de §13.1).
- É **regra de motor** (constante interna, ex.: `MAX_HORAS_SEMANAIS = 30`); **não vai ao
  banco**.

---

## 8. Encontros, projeção e conclusão automática

Esta é a **regra central** do sistema. A unidade da escala é o **ENCONTRO**.

- **Total de encontros = `locais.numero_encontros`** (número que vem do ESPELHO por
  cenário — ex.: 18, 40, 20…). É **fixo**.
- O motor **agenda exatamente esse número de encontros** por alocação, **semana a
  semana**, a partir do início do ciclo, pulando datas de **feriado/evento
  bloqueante**, **local sem cobertura** (docente **e** preceptor afastados no mesmo
  dia — ver §12) e **indisponibilidade do local**.
- A projeção continua **mesmo além do fim do ciclo**, se necessário — é isso que
  revela o **risco de "não fechar no prazo"**.
- As **horas** são consequência (`nº de encontros × duração do encontro`); ficam
  como informação secundária.

### 8.1. Sem controle de frequência (assume-se presença)

> **O sistema NÃO registra presença.** Conforme os dias passam, cada encontro cuja
> **data já passou** é **automaticamente contado como feito** — "hoje passou da
> data, logo o aluno participou". Os "encontros feitos" sobem sozinhos de 0 até o
> total. É uma **projeção do plano**, não um comparecimento real.

### 8.2. Contador de encontros (feitos × total)

Em cada área o sistema mostra **`feitos / total`** encontros (ex.: **14/18**):

- **Total** = `locais.numero_encontros` (fixo, do espelho).
- **Feitos** = encontros já decorridos (presença assumida) **±** o ajuste manual do
  professor (§8.3), limitado ao intervalo **[0, total]**.
- **Conclusão automática:** quando **feitos atingem o total (N)**, a área vira
  `concluida` e o aluno é **"aprovado" naquela área** — mesmo que isso ocorra
  **antes do fim do período da caixa** (ex.: reforço). No modelo grade-primeiro a
  conclusão antecipada **não gera evento e não libera vaga**: o aluno segue no
  grupo e nada é reprogramado (ver `REGRAS_MOTOR_ESCALA.md` §10.5). Se um ajuste
  derruba os feitos abaixo do total, a área **reabre**.
- **Incompleta (carry-forward) — estado novo:** se o **período da caixa fecha com
  feitos < N**, a área **não conclui** — vira **`incompleta`** e **refaz no próximo
  ciclo**. É distinto de `interrompida` (parada extraordinária, §6.1). Ver
  `REGRAS_MOTOR_ESCALA.md` §10.5.
- **Vaga liberada por saída/desmatrícula:** o preenchimento de uma vaga que abre no
  meio do ciclo é **decisão da coordenação** (não automático) — ver §10 e a Fase 4
  do grade-primeiro.

### 8.3. Ajuste manual: falta (−) e reforço (+)

Como não há controle de frequência, o professor/coordenação pode **corrigir o
contador** de encontros feitos de um aluno — **só aumentar ou diminuir**, por
exceção. Fica no **Cadastro (Alunos → Encontros)**, nunca na visualização.

- **− (falta):** o aluno faltou por algum motivo → o professor **diminui 1** dos
  feitos. Ex.: 14/18 → **13/18**. O total (18) não muda.
- **+ (reforço):** o aluno está quase fechando e merece recuperar (risco de "rodar")
  → o professor **soma 1** encontro. Ex.: 17/18 → **18/18**, fechando a carga e
  aprovando o aluno.
- É um **ajuste simples de contador** (sem data/hora), limitado a **[0, total]**, e
  fica registrado na atividade recente (auditoria).

> 🔮 **Módulo futuro (fora do escopo):** controle de presença real e sistemático
> (marcar todo encontro como compareceu/faltou) é outro módulo. O ajuste ± de §8.3
> é **exceção pontual**, não um diário de classe.

---

## 9. Progressão e alerta de risco

- A **progressão** do aluno é derivada das horas cumpridas × carga exigida, por
  área e no total da fase.
- Cada alocação tem uma **data prevista de conclusão** (data do último encontro que
  fecha a carga). Se essa data for **posterior ao fim do ciclo**, o aluno/área
  entra em **risco** ("não fecha no prazo") — sinalizado no painel.

---

## 10. Capacidade, fila de espera e projeção de entrada

- Cada **local** tem uma **capacidade** (nº de vagas simultâneas).
- **Fila de espera** (derivada): alunos com matrícula `em_andamento` numa área
  **sem alocação ativa**, ordenados por **prioridade (ordenamento)**.
- Situações de oferta × demanda por área: equilíbrio, demanda reprimida (fila sem
  vaga), vaga sobrando (pode matricular) e vaga ociosa + fila (conflito de horário).

### 10.1. Projeção de entrada da fila *(regra nova)*

Como o motor **materializa todas as caixas (grupos) do ciclo no bootstrap**
(grade-primeiro), a entrada da fila deixa de ser estimada por "quando uma vaga vai
liberar" — ela é **lida direto do molde**: o próximo da fila entra na **primeira
caixa futura da área que tenha vaga** e para a qual ele seja **viável**.

- **Previsão de entrada** do próximo da fila = a data de início da **primeira caixa
  futura viável** para ele (respeitando capacidade, dia/turno, 2h entre áreas no
  mesmo dia, teto de 30h e restrições de local).
- Quem não couber em **nenhuma** caixa do ciclo fica **aguardando vaga** → próximo
  ciclo.
- Regra de ordem: a prioridade de ocupação é **ordenamento**.

> Efeito prático: a comissão responde "quando o aluno X, esperando vaga em
> Audiologia II, começa?" **lendo a caixa futura onde ele encaixa** — não por chute.

### 10.2. Grupos (ondas por local) — modelo GRADE-PRIMEIRO *(revisto)*

> Motor autoritativo: **`REGRAS_MOTOR_ESCALA.md`**. O termo lúdico "caixa" = este
> **grupo** (onda por local). Mudou **quando/quanto** se gera (tudo no bootstrap),
> não o conceito de slot/onda.

A comissão pensa os alunos em **grupos**: um local com capacidade N recebe **até N
alunos que entram e concluem juntos** — uma **onda**.

- **Grupo = leva de alunos num (local, dia), numa janela** (início → conclusão).
  Cada par (local, dia) é um slot próprio: um campo com 2 dias/semana gera **2
  famílias de grupos independentes** (turno só desmembra se não for integral).
- **Materialização no bootstrap:** o motor gera **todos os grupos do ciclo de uma
  vez, ANTES de alocar alunos** (não mais "sob demanda"). As datas de cada grupo
  dependem só da **infraestrutura** — dia fixo do slot, pulando feriado/evento e
  dias sem cobertura (docente **e** preceptor afastados, §12) — fatiadas em blocos
  de `N = teto(carga da área / horas por encontro)` encontros. Contam-se **sessões
  viáveis** (não semanas), então feriado "empurra" a caixa sozinho.
- **Cascata:** os grupos de um mesmo slot são blocos **consecutivos** dessa fila de
  datas — o Grupo 2 começa quando o Grupo 1 termina, e assim por diante, até o
  último que **fecha dentro do ciclo** (bloco parcial no fim → não vira grupo).
  Com **`passagem_grupo`**, a onda seguinte começa **no último dia** da anterior
  (sobreposição de 1 dia — quem sai orienta quem entra); sem, começa **depois**.
  Aparece na aba Grupos (selo entre ondas) e na visão por campo (dia destacado).
- **Preenchimento:** com o molde pronto, alocam-se os alunos por **prioridade
  (`ordenamento`)**, com objetivo **cobertura > lotação** (todos concluírem vence
  caixa cheia), escolhendo a **caixa mais cheia com vaga** (empacotar) entre as
  **viáveis** — capacidade, conflito de dia/turno, **2h entre áreas** no mesmo dia,
  **teto de 30h** e restrições de local (§6.2). Uma área conclui com **uma caixa
  qualquer** que a atenda.
- **Grupo 1 (em andamento)** = alunos hoje no local, com datas **reais
  comprometidas**; **grupos futuros (previstos)** = projeção **re-derivável** do
  molde — mas o molde é **persistido** (fonte de verdade), não recomputado do zero
  a cada tela.
- **Matrícula no meio do ciclo:** entra numa **vaga sobrando de um grupo futuro** da
  área (nunca num que já começou — senão não fecha os N).
- **Conflito num grupo previsto:** se o dia+turno colide com outro compromisso do
  aluno na janela, o sistema **sinaliza a dependência** — *"entra ao concluir [área]
  (previsto DD/MM)"*.
- **Onde ver:** aba **Grupos** (por local: grupo atual + ondas previstas, janelas,
  membros, **CH semanal de pico** por aluno e **ocupação N/cap** por grupo).

### 10.3. Gestão manual de grupos — mover aluno / mover grupo *(regra nova)*

Os grupos propostos pelo motor (§10.2) são **ponto de partida editável** — a mesma
filosofia da escala (§7.1), agora no nível de **grupo/onda**. Dentro de uma **área**, a
coordenação rearranja livremente os grupos dos seus locais:

- **Trocar um aluno (substituição 1-por-1):** ao mover um aluno para outro grupo, escolhe-se
  **com quem ele troca** — o aluno A vai para o grupo de B e B vai para o de A. É uma
  **troca**, não um acréscimo: o tamanho de cada grupo **não muda** (nunca infla além da
  capacidade).
- **Trocar grupos inteiros (swap de posição):** dois grupos **trocam de onda/ordem** (ex.:
  **G3 ⇄ G2** — o que era 3º na fila vira 2º e vice-versa). Cada grupo **mantém seus
  membros**; só a posição na cascata muda. Nada de fundir grupos.
- **Só entre grupos que NÃO estão em andamento** (previstos). A onda 1 (em andamento) é
  editada pela via de alocação (§7.1, "Por campo"), não aqui.
- **Cada grupo se estabelece pela capacidade do local** — as trocas preservam isso por
  construção (1-por-1 ou swap de posição).
- Vale para **todas as áreas**. Um grupo pertence a um **local**, que pertence a uma
  **área**; o rearranjo ocorre entre os grupos dos locais **daquela área**, respeitando
  **capacidade** do local, **conflito de dia/turno** e **restrições de local** (§6.2).

**Fluido, sem trava — concretiza no dia 1 *(revisto)*:**

- A troca é sempre por **substituição/swap** (aluno↔aluno ou grupo⇄grupo), preservando a
  capacidade de cada grupo — só entre grupos **previstos** (ainda não iniciados).
- **NÃO trava e NÃO exige remanejo:** o arranjo é só a **ordem planejada**; o professor
  refaz quando quiser. O regenerador **preserva** o arranjo (persistido), mas ele
  permanece **editável**. Um grupo só se **concretiza no 1º dia** dos encontros
  (`data_inicio ≤ hoje` → vira onda em andamento, com sessões reais, e deixa de ser
  remanejável). Isso substitui, para grupos, a antiga "regra de congelamento" do §13.

**Impacto de modelagem (feito no repo real):** o arranjo manual é **persistido** para
sobreviver à regeração via a coluna **`grupo_alunos.fixado`** (migration
`f3b8c1d4e6a2`) — quando `true`, o motor **não remove nem realoca** aquele membro ao
regerar (grade-primeiro; ver `REGRAS_MOTOR_ESCALA.md` §9.1). No protótipo é o array
`S.grupo_travas` (pins `{aluno_id, local_id, onda}`).

**Visual (§10.2):** a aba **Grupos** tem **filtro por ÁREA** — seleciona-se a área e
veem-se **todos os seus locais/slots** com os grupos de cada um (em andamento + **na
fila**), com resumo por área (nº de locais, grupos em andamento, grupos na fila, alunos),
janelas, membros e os controles de troca. Grupos futuros são rotulados **"na fila"** (não
"previsto") — mais assertivo.

**Visão "Por campo" (calendário) — cor por GRUPO:** o calendário do cenário é **macro por
grupo/onda**, não por aluno — **uma cor por grupo**. **Cada grupo aparece em todos os seus
dias de encontro, do início ao fim** (a onda em andamento pelas sessões reais; as ondas
previstas por projeção semanal na sua janela), com **marcos de início e fim** por grupo e a
legenda listando a **janela (início→fim)** e o nº de alunos de cada um. Como as ondas em
cascata passam do fim do ciclo, o calendário **navega além do ciclo** (até o fim do último
grupo) para mostrar as faixas de todos. Assim a coordenação lê o macro (quando cada leva
roda) em vez do detalhe aluno-a-aluno.

---

## 11. Eventos e calendário institucional

- **Eventos** (acadêmicos, reuniões, feriados) podem **bloquear estágio** ou não —
  isso é um **atributo do evento** (`bloqueia_estagio`), sem regra "chumbada".
  - Ex.: atividades de **Linguagem têm precedência e não bloqueiam** → basta
    marcar o evento como não bloqueante.
- Encontro que cai em data de evento bloqueante é **empurrado** para a próxima data
  livre.
- **Origem** do evento: manual, Google Calendar (importado) ou API de feriados.
  Feriados nacionais/estaduais (RS) são importados automaticamente.

---

## 12. Docentes, preceptores e cobertura do local

### 12.1. Docentes e preceptores

- **Docentes** são os professores da UFCSPA: catálogo permanente (atravessa
  ciclos), com login institucional e e-mail.
- **Preceptores** são os responsáveis de campo (fonoaudiólogas/os), **externos à
  UFCSPA**: catálogo permanente também. **Não têm login institucional** — a **conta
  é gerada a partir do e-mail** (por isso o e-mail é **obrigatório**). Um preceptor
  pode responder por **N locais** (1 preceptor ↔ N locais).
- **Cada local tem um docente** (sempre) e, **opcionalmente, um preceptor de campo**.
  O preceptor de um local pode ser um **preceptor externo** (catálogo de preceptores)
  **ou** um **docente** (qualquer professor pode ser o preceptor de um local — inclusive
  o próprio docente responsável do local). Isso é uma **referência polimórfica** no
  local (`preceptor_tipo` = `externo` | `docente` | nenhum).
- A designação preceptor↔local é feita **por local**: no bootstrap, no passo
  **Preceptores** (que vem **depois de Locais**), uma tabela lista os locais e, em cada
  um, escolhe-se o responsável de campo (preceptor externo, docente, ou nenhum).

### 12.2. Regra de cobertura (docente OU preceptor)

**Para um encontro acontecer numa data, basta que UM dos responsáveis do local esteja
disponível.** O encontro **só cai** (local sem cobertura) quando **docente E preceptor
estiverem afastados ao mesmo tempo**.

- Local **sem preceptor** (só o docente): cai quando o docente está afastado.
- Local **com preceptor**: se o docente se afasta mas o preceptor está presente (ou
  vice-versa), o encontro **acontece normalmente**.
- Quando o preceptor de um local é o **próprio docente** dele (mesma pessoa nos dois
  papéis), não há redundância → o local é prejudicado quando essa única pessoa falta.
- Efeito: um local fica **temporariamente prejudicado** só nas datas em que **todos**
  os seus responsáveis estão fora — essas sessões são **removidas/realocadas** (§13).

### 12.3. Afastamentos

- Registram ausências (férias, licença, outro) com período. Cada afastamento
  referencia **uma pessoa: um docente OU um preceptor**.
- Encontros que caem numa data em que o **local fica sem cobertura** (§12.2) são
  **removidos/realocados**.
- **Desligar um docente ou um preceptor** (`ativo = false`) com o ciclo em andamento
  afeta as sessões futuras dos locais em que ele é responsável → marca a escala como
  **desatualizada** e dispara o **remanejamento** (§13). Nunca são apagados (preserva
  histórico).

---

## 13. Remanejamento (operação)

Mudanças durante o ciclo (docente desligado, local desativado/indisponível, evento
novo importado, **interrupção de estágio**, **conclusão que libera vaga com fila** —
§13.1) **não recalculam a escala sozinhas**:

- Cada mudança **acumula um gatilho** e liga a flag `escala_desatualizada` (banner
  de alerta no painel).
- Ao **Remanejar**, o sistema identifica **apenas as sessões futuras afetadas**,
  recalcula **só elas** e mostra uma **pré-visualização** ("vai afetar N alunos: X
  sessões movidas, Y realocadas, Z sem vaga") antes de confirmar.
- **Regra de congelamento — o motor NUNCA toca em:** área `concluida`, sessões
  `cumpridas` (passado), alocações `travadas` e **arranjos de grupo travados
  manualmente** (§10.3) — todos são trava manual e sobrevivem ao remanejo.

### 13.1. Gatilho: conclusão que libera vaga com fila esperando *(regra nova)*

A **conclusão automática** de uma área (§8.1/§8.2) acontece **sozinha** conforme as
datas passam e **libera a vaga** do local. Se, naquele momento, há **fila de espera**
na área, isso é um **gatilho de remanejamento** como qualquer outro — o sistema
**não pode deixar vaga livre + fila sem sinalizar**.

- **Detecção imediata:** ao abrir a vaga, o sistema liga `escala_desatualizada` e
  mostra o alerta no **painel principal** — ex.: *"Audiologia I: 4 vagas livres, 4 na
  fila — conclusão liberou vagas"*.
- **Materialização deliberada (1 clique):** ao **Remanejar**, os alunos **aguardando**
  entram nas vagas por **prioridade (`ordenamento`)** e passam de **"Aguardando vaga"
  → "Em andamento"** (§6.3), com sessões geradas **a partir de agora** (§7.1). **Não é
  realocação silenciosa** — vem com a **pré-visualização** de §13; a coordenação
  confere antes.
- **Respeita todas as restrições:** congelamento (não toca em concluída/cumprida/
  travada), **conflito de dia/turno**, **restrições de local do aluno** (§6.2) e o
  **teto de 30h semanais**. Quem não couber permanece **aguardando** com o motivo
  (ex.: "conflito de horário", "sem local liberado").
- **Ordem:** quando abrem várias vagas, entram **sempre os próximos da fila por
  ordenamento** (§10.1) — a mesma regra da projeção de entrada em cascata.

> Era exatamente o caso flagrado no protótipo: um grupo de Audiologia I concluiu (4
> vagas livres, previsão de início "hoje") e 4 alunos seguiam "aguardando" em vez de
> entrarem em andamento. O gatilho fecha esse buraco.

---

## 14. Encerramento do ciclo e histórico

- Ao encerrar, o sistema grava um **retrato (snapshot) por aluno**: as áreas **da
  fase dele**, com carga exigida, horas cumpridas e data de conclusão.
- **Situação:** `ciclo_completo` (todas as áreas da fase concluídas) ou `pendente`.
- **Pendências não impedem** o encerramento — são gravadas como estão.
- O histórico é **denormalizado de propósito** (copia valores, não referencia):
  o registro do ano **nunca muda**, mesmo que aluno/local/área sejam editados depois.

---

## 15. Autenticação, perfis e e-mails

- Acesso da comissão por login (e-mail institucional).
- Perfis: `administrador`, `coordenacao`, `consulta`.
- **E-mail em todos os cadastros de pessoas** (docentes, preceptores e alunos): é o
  **destino das notificações do sistema**. Para **preceptores** o e-mail é também a
  **conta** (são externos, sem login institucional) e portanto **obrigatório**.
- Os campos de e-mail são **exibidos e editáveis** nas telas de visualização e no
  bootstrap (pré-cadastro de docentes, preceptores e alunos).

---

## Apêndice — Pendências a confirmar com a coordenação

1. **Carga horária de cada estágio hospitalar** (Pediatria / Adulto /
   Neonatologia) e como o total de 160h da matriz se traduz em horas por cenário
   (ver §3).
2. Confirmar se **controle de presença** entrará em escopo futuro (§8.1).
11