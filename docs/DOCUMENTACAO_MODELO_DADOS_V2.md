# Documentação do Modelo de Dados — Sistema de Gestão de Estágios (v2)

**Curso de Fonoaudiologia — UFCSPA**
**Arquitetura alvo:** FastAPI + Jinja2/HTMX (renderização no servidor, sem SPA) · SQLAlchemy · PostgreSQL · CSS puro
**Fonte:** `modelagem_dados_v2.dbml.txt`, `proposta-orquestracao-sistema-fono.md` e o protótipo navegável (v2)

---

## 1. Visão geral — como o sistema funciona

O sistema organiza a vida de um **ciclo de estágio** (equivalente a um ano letivo) em **três momentos**, e quase toda a modelagem existe para dar suporte a essa jornada:

| Momento | O que é | Estado do ciclo |
|---|---|---|
| **Abertura (bootstrap)** | Carrossel de 7 passos que cadastra a base e gera a primeira escala | `rascunho` |
| **Operação (dia a dia)** | Painel de rotina; edições acendem o alerta de *Remanejar* | `em_andamento` |
| **Encerramento** | Grava o histórico do ano e zera a operação para o próximo ciclo | `encerrado` |

O conceito central que amarra tudo é o de **máquina de estados**: o ciclo tem um `status`, e é esse status que decide qual tela o usuário vê ao entrar no sistema. Isso substitui a lógica da versão 1 (Flask + MongoDB), onde a escala era sempre reconstruída do zero de forma destrutiva.

A premissa de negócio mais importante da v2 é: **depois do bootstrap, nenhuma mudança refaz o ciclo inteiro.** Qualquer alteração cadastral durante a operação não mexe na escala diretamente — ela apenas marca o ciclo como *desatualizado* (`escala_desatualizada = true`), enfileira o gatilho e acende um banner. O gestor então aciona o **Remanejamento**, que recalcula **somente o afetado**, preservando o que já é válido.

### O trio que descreve a escala

Três tabelas, lidas em sequência, respondem às três perguntas da escala:

- **`matriculas`** → **O QUE** o aluno cursa (quais áreas)
- **`alocacoes`** → **ONDE** ele cursa (em qual local/cenário de prática)
- **`sessoes`** → **QUANDO** ele cursa (as datas concretas, a menor unidade)

Progresso, previsão de conclusão e alerta de risco **todos derivam de `sessoes`**.

### Módulos do sistema

A modelagem se organiza em 8 módulos (os `TableGroup` do DBML):

| Módulo | Tabelas |
|---|---|
| **Ciclo** (orquestração) | `ciclos` |
| **Apoio** (catálogos permanentes) | `areas`, `docentes`, `preceptores` |
| **Alunos** | `alunos`, `matriculas`, `restricoes_aluno_local` |
| **Estágio** (motor de alocação) | `locais`, `locais_dias`, `alocacoes`, `sessoes`, `grupos`, `grupo_alunos` |
| **Calendário institucional** | `afastamentos`, `indisponibilidades_local`, `eventos` |
| **Operação** | `fila_remanejo`, `atividade` |
| **Histórico** | `historico` |
| **Autenticação** | `usuarios` |

---

## Módulo 1 — Ciclo (orquestração)

### Tabela: `ciclos`

**1. Nome da tabela:** `ciclos`

**2. Módulo/Área:** Ciclo / Orquestração — é a espinha dorsal do sistema inteiro.

**3. Objetivo:** Armazena cada edição anual do programa de estágios e funciona como uma **máquina de estados**. Existe para agregar tudo que pertence a um ano (alunos, locais, eventos, escala) sob um único registro e para governar qual fase da jornada o sistema está — abertura, operação ou encerramento. Arquivar um ano é simplesmente encerrar o ciclo; nada é apagado.

**4. Funcionalidades relacionadas:**
- Tela de **Boas-vindas** ("Abrir novo ciclo") quando não há ciclo ativo.
- **Carrossel de bootstrap** — o campo `passo_bootstrap` permite retomar exatamente onde o rascunho parou, mesmo após fechar o navegador.
- **Painel de Operação** — exibido enquanto o ciclo está `em_andamento`.
- **Banner de remanejo** — ligado/desligado pelo campo `escala_desatualizada`.
- **Encerramento de ciclo** (transição para `encerrado`).

**5. Principais campos:**
- `status` — o estado atual (`rascunho`, `em_andamento`, `encerrado`); é o que decide a tela.
- `data_inicio` / `data_fim` — o intervalo do ciclo; a base para prever fechamento de carga e calcular o alerta de risco ("não fecha no prazo").
- `passo_bootstrap` — em qual passo do carrossel o rascunho parou (nulo fora do rascunho); permite a retomada.
- `escala_desatualizada` — flag booleana que liga o banner de remanejo no painel.
- `criado_em` / `encerrado_em` — carimbos de auditoria.

**6. Relacionamentos:** É a tabela "pai" de quase todo o sistema (1:N):
- `1:N` com `alunos`, `locais`, `eventos`, `afastamentos`, `fila_remanejo`, `atividade`, `historico`.
- Todas essas tabelas carregam `ciclo_id`, o que permite isolar e arquivar um ano sem misturar turmas.

**7. Regras de negócio:**
- **Só pode existir UM ciclo `rascunho` OU `em_andamento` por vez** — nunca dois ciclos ativos simultaneamente.
- Transições permitidas: `rascunho → em_andamento` (ao confirmar o relatório do bootstrap) e `em_andamento → encerrado` (no fim do ano).
- Validação: `data_fim > data_inicio`.
- O encerramento é **irreversível** e exige confirmação forte (digitar o ano).

### Resumo do módulo Ciclo

`ciclos` é a raiz da árvore de dados. Ele não guarda regra de negócio complexa; sua força está em ser o **agregador** e o **relógio de estado**. Toda tabela transacional aponta para ele via `ciclo_id`, de modo que "encerrar o ano" é uma operação de marcação de estado — não uma exclusão. É a leitura do campo `status` que roteia o usuário para a tela certa, e a flag `escala_desatualizada` é o elo entre uma edição feita na operação e o alerta que pede o remanejo.

---

## Módulo 2 — Apoio (catálogos permanentes)

Estas tabelas **atravessam ciclos** — sobrevivem de um ano para o outro e não têm `ciclo_id`. Ficam fora do assistente de bootstrap.

### Tabela: `areas`

**1. Nome da tabela:** `areas`

**2. Módulo/Área:** Apoio / Catálogo permanente.

**3. Objetivo:** Guarda o catálogo fixo das **10 áreas** do curso (Audiologia I, Motricidade Orofacial, Linguagem Infantil, Saúde Coletiva, Audiologia II, LAD, Voz e os 3 cenários hospitalares). Existe para padronizar as competências que todo aluno precisa cumprir e para definir, por área, a carga exigida, a **fase** a que pertence (5º ou 6º/7º) e se é **pré-requisito** dos demais estágios.

**4. Funcionalidades relacionadas:**
- Cálculo de progresso por área do aluno (X/N áreas **da fase** concluídas).
- Cadastro de locais (cada local pertence a uma área).
- Matrícula do aluno por área.
- Filtro das áreas por fase no cadastro do aluno (5º vê só Audiologia I; 6º/7º vê as demais).
- Cores das pílulas/badges de área na interface.

**5. Principais campos:**
- `nome` — identifica a área; **único**.
- `carga_exigida` — horas obrigatórias para concluir a área (ex.: 160h); usada para creditar carga no progresso. *(A conclusão em si é dirigida por **encontros**, não por horas — ver `matriculas` §7 e Regras de Negócio §8.)*
- `fase` — `5` (mini-ciclo, só Audiologia I) ou `6_7` (demais áreas); define quais áreas cada aluno enxerga.
- `pre_requisito` — booleano; **só Audiologia I = `true`**. Bloqueia a alocação das áreas de 6º/7º enquanto não concluída.
- `cor` — cor `#hex` usada na UI para a badge da área.

**6. Relacionamentos:**
- `1:N` com `locais` (uma área tem vários cenários de prática).
- `1:N` com `matriculas` (uma área é cursada por vários alunos).

**7. Regras de negócio:**
- `nome` é **único**.
- Já vem **pré-cadastrada** — por ser catálogo fixo, não precisa de passo no bootstrap.
- Não tem `ciclo_id`: é permanente e compartilhada entre todos os anos.
- **Fase determina a matriz do aluno:** 5º semestre cursa só a área com `fase = 5` (Audiologia I); 6º/7º cursa as áreas `fase = 6_7`.
- **Pré-requisito bloqueante:** nenhuma área de 6º/7º é alocada enquanto a área `pre_requisito` (Audiologia I) não estiver concluída.

### Tabela: `docentes`

**1. Nome da tabela:** `docentes`

**2. Módulo/Área:** Apoio / Catálogo permanente.

**3. Objetivo:** Cadastra os professores que atuam nos estágios. Existe como entidade permanente porque **o mesmo docente atua em vários anos** — por isso o docente nunca guarda datas de ciclo.

**4. Funcionalidades relacionadas:**
- Passo 2 do bootstrap (cadastro de docentes, sempre **antes** dos afastamentos).
- Cadastro de locais (cada local tem um docente responsável).
- Registro de afastamentos (férias/licenças) por docente.

**5. Principais campos:**
- `nome` — identifica o docente; **único**.
- `email` — login institucional UFCSPA + destino das notificações do sistema.
- `ativo` — permite "desligar" um docente sem apagar histórico.

**6. Relacionamentos:**
- `1:N` com `locais` (um docente responde por vários cenários).
- `1:N` com `afastamentos` (um docente pode ter vários períodos de ausência).
- Pode figurar como **preceptor de campo** de um local (ver `locais.preceptor_tipo = docente`).

**7. Regras de negócio:**
- `nome` é **único**.
- **Soft delete via `ativo`**: nunca se apaga um docente; desativa-se. Isso preserva o histórico.
- **Desligar um docente com o ciclo em andamento dispara remanejo**: as sessões futuras dele ficam órfãs, o ciclo é marcado `escala_desatualizada = true` e os alunos são reencaixados em outro cenário da mesma área.
- **Docente nunca guarda datas de ciclo** — o vínculo temporal surge via `locais` (que pertencem a um ciclo) e via `afastamentos` (que têm datas próprias).

### Tabela: `preceptores`

**1. Nome da tabela:** `preceptores`

**2. Módulo/Área:** Apoio / Catálogo permanente.

**3. Objetivo:** Cadastra os **responsáveis de campo** dos locais — fonoaudiólogas(os) que acompanham o estágio no cenário. São **externos à UFCSPA** e **não têm login institucional**: a **conta é gerada a partir do e-mail**. Catálogo permanente (atravessa ciclos); um preceptor pode responder por **vários locais**.

**4. Funcionalidades relacionadas:**
- Passo **Preceptores** do bootstrap (uma **tabela por local**, logo **depois** de Locais): em cada local escolhe-se o responsável de campo.
- Cadastro/edição de preceptores (nome + e-mail) na sidebar.
- Registro de afastamentos por preceptor.

**5. Principais campos:**
- `nome` — nome do preceptor.
- `email` — **obrigatório**: é a **conta** (sem login institucional) e o destino das notificações.
- `ativo` — soft delete.

**6. Relacionamentos:**
- Referenciado por `locais` (FK **polimórfica** `preceptor_tipo`/`preceptor_id`, quando `preceptor_tipo = externo`).
- `1:N` com `afastamentos` (via `afastamentos.preceptor_id`).

**7. Regras de negócio:**
- `email` **obrigatório** (é a conta).
- **Soft delete via `ativo`**; desligar em andamento dispara remanejo nos locais em que é responsável.
- O responsável de campo de um local pode ser um preceptor (aqui) **ou** um docente — decisão por local.

### Resumo do módulo Apoio

`areas`, `docentes` e `preceptores` são os cadastros **permanentes** do sistema — as peças que não pertencem a nenhum ano específico. `areas` define *o padrão de competências* (o que precisa ser cursado e por quantas horas); `docentes` define *quem ministra* (UFCSPA); `preceptores` define os *responsáveis de campo* (externos). Todos são referenciados pelo módulo de Estágio: um `local` cruza uma área, um docente e (opcional) um preceptor de campo. A regra de ouro aqui é a **preservação de histórico**: nenhum é apagado — áreas são fixas; docentes e preceptores são desativados, nunca removidos, para que registros de anos anteriores continuem íntegros.

---

## Módulo 3 — Alunos

### Tabela: `alunos`

**1. Nome da tabela:** `alunos`

**2. Módulo/Área:** Alunos.

**3. Objetivo:** Armazena os estudantes matriculados **em um ciclo específico**. Diferentemente dos catálogos, o aluno pertence a um ano — o que permite arquivar turmas sem misturá-las. Guarda também a **prioridade de alocação**, informação crítica para o motor de escala.

**4. Funcionalidades relacionadas:**
- Passo 5 do bootstrap (cadastro da turma).
- Lista de alunos e tela de detalhe (X/N áreas da fase, % de carga, prazo, card por área, calendário individual).
- Motor de alocação (ordena os alunos por prioridade antes de distribuir vagas).

**5. Principais campos:**
- `ciclo_id` — a que ano o aluno pertence.
- `nome` / `matricula` — identificação.
- `email` — destino das notificações do sistema (padrão `matricula@aluno.ufcspa.edu.br`).
- `semestre` — semestre atual, que define a **fase**: `≤ 5` → fase 5 (mini-ciclo, só Audiologia I); `≥ 6` → fase 6/7 (demais áreas). No ciclo convivem os dois grupos.
- `ordenamento` — **prioridade na alocação: menor valor = maior prioridade**. É por esta ordem que o motor distribui as vagas.

**6. Relacionamentos:**
- `N:1` com `ciclos` (vários alunos por ciclo).
- `1:N` com `matriculas` (um aluno cursa várias áreas).
- `1:N` com `alocacoes` (um aluno ocupa vários locais ao longo do ciclo).

**7. Regras de negócio:**
- Par (`ciclo_id`, `matricula`) é **único** — não pode haver matrícula duplicada dentro do mesmo ciclo.
- Índice em `ordenamento` para acelerar a ordenação do motor.
- Cadastrar/remover aluno com o ciclo em andamento **dispara remanejo** (ajusta só a alocação daquele aluno; a vaga que abre pode ser oferecida ao próximo na ordem de prioridade).
- **Reindexação da prioridade:** ao remover um aluno, o `ordenamento` dos demais é reindexado para uma sequência contígua `1..N` (sem buracos), preservando a ordem relativa.

### Tabela: `matriculas`

**1. Nome da tabela:** `matriculas`

**2. Módulo/Área:** Alunos (tabela de junção aluno × área).

**3. Objetivo:** É a junção que diz **o que** cada aluno cursa. Substitui os campos dinâmicos `data_matricula_<area>` e as listas `areas_matriculadas`/`areas_concluidas` da versão 1 (MongoDB). Cada linha representa uma área que o aluno está cursando ou já concluiu.

**4. Funcionalidades relacionadas:**
- Estados por área na tela do aluno: **em andamento** (tem matrícula ativa), **concluída** (matrícula fechada) e **a iniciar** (área do catálogo *sem* matrícula — estado derivado, não armazenado).
- Motor de alocação (só aloca sessões para áreas `em_andamento`).
- Cálculo automático de conclusão.

**5. Principais campos:**
- `aluno_id` / `area_id` — o par que define a matrícula.
- `status` — `em_andamento`, `concluida`, `interrompida` (parada extraordinária, §6.1) ou **`incompleta`** (período da caixa fechou com feitos < N → carry-forward; grade-primeiro §10.5).
- `data_matricula` — quando o aluno começou a área.
- `data_conclusao_prevista` — **calculada pelo motor**: a data da última sessão que fecha a carga exigida.
- `data_conclusao` — preenchida quando a área efetivamente conclui.

**6. Relacionamentos:**
- `N:1` com `alunos`.
- `N:1` com `areas`.
- `1:N` com `alocacoes` (a matrícula que originou cada alocação).
- Efetivamente, `matriculas` é a tabela associativa que resolve o **N:N entre `alunos` e `areas`**.

**7. Regras de negócio:**
- Par (`aluno_id`, `area_id`) é **único** — o aluno não se matricula duas vezes na mesma área.
- **Conclusão é automática, nunca check manual**: a área fecha quando os **encontros feitos** (encontros já decorridos ± ajuste manual do professor) atingem o **total de encontros** do local (`numero_encontros`) — não por horas. Ao fechar, o status vira `concluida` e a `data_conclusao` é registrada. Se um ajuste derruba os feitos abaixo do total, a área **reabre** (ver Regras de Negócio §8).
- **Área concluída nunca mais entra em alocação** (regra de congelamento).
- Área do catálogo sem linha de matrícula = estado "a iniciar" (**derivado**, não gravado).

### Tabela: `restricoes_aluno_local`

**1. Nome da tabela:** `restricoes_aluno_local`

**2. Módulo/Área:** Alunos.

**3. Objetivo:** Restrições de **local** de um aluno. Por **condição especial**, um aluno pode **não poder** frequentar certos locais. É uma **blocklist**: o padrão é estar disponível em todos os locais; cada linha é uma **exceção** (um local bloqueado para aquele aluno).

**4. Funcionalidades relacionadas:**
- Cadastro do aluno (bootstrap **e** operação): árvore "Disponibilidade por local", agrupada por área, com checkbox por local (desmarcar = bloquear).
- Motor de alocação: pula os locais bloqueados do aluno.

**5. Principais campos:**
- `aluno_id` — o aluno.
- `local_id` — o local que ele **não** pode frequentar.

**6. Relacionamentos:**
- `N:1` com `alunos` e `N:1` com `locais` (par único).

**7. Regras de negócio:**
- **Granularidade por LOCAL** (não por área): o aluno segue cursando a área, mas só é alocado nos locais **liberados** dela.
- **Ausência de linha = disponível** (padrão). Guarda-se só o que foi desmarcado.
- **Validação (aplicação):** não pode sobrar uma área matriculada `em_andamento` **sem nenhum local liberado** — a UI **avisa/bloqueia** ao salvar.
- No protótipo (`versao_2`) isso é representado como o array `aluno.locais_bloqueados`; no modelo relacional é esta tabela associativa.

### Resumo do módulo Alunos

Os dois se complementam: `alunos` guarda *quem* está no ciclo e *com que prioridade*; `matriculas` guarda *o que cada um cursa*. A matrícula é **flexível, a critério do professor**: pode-se matricular o aluno em **todas as áreas da fase de uma vez** ou em **apenas algumas**, acrescentando as demais depois — as áreas matriculadas sem vaga imediata ficam na fila de espera (ver seção dedicada). É essa granularidade que dá ao sistema os três estados por área (em andamento / concluída / a iniciar) e alimenta o motor, que só distribui sessões sobre matrículas `em_andamento`, sempre respeitando o `ordenamento`. A conclusão de área acontece sozinha, dirigida pelos encontros decorridos — nunca por marcação manual.

---

## Módulo 4 — Estágio (motor de alocação)

Este é o coração operacional: `locais` = a oferta; `alocacoes` = ONDE o aluno cursa; `sessoes` = QUANDO.

### Tabela: `locais`

**1. Nome da tabela:** `locais`

**2. Módulo/Área:** Estágio / Cenários de prática.

**3. Objetivo:** Cada linha é um **cenário de prática** de um ciclo: o cruzamento de área + campo (local físico) + docente + dia + turno + horário + capacidade. É a "oferta" que o motor usa para montar a escala. Muda de ano para ano — por isso pertence a um ciclo.

**4. Funcionalidades relacionadas:**
- Passo 4 do bootstrap.
- Tela de Locais na operação (+ indisponibilidade temporária).
- Motor de alocação (respeita capacidade, horário e disponibilidade do docente).

**5. Principais campos:**
- `ciclo_id`, `area_id`, `docente_id` — os três vínculos que posicionam o local.
- `unidade` — a unidade/instituição do cenário (agrupa campos de um mesmo local físico).
- `campo` — o cenário físico em texto (Clínica-Escola, Hospital, UBS…).
- `preceptor_tipo` / `preceptor_id` — **preceptor de campo** do local (FK **polimórfica**): `externo` → aponta para `preceptores`; `docente` → aponta para `docentes` (docente-como-preceptor); ambos nulos → sem preceptor separado (só o docente responde). **Cobertura:** o encontro só cai quando docente **e** preceptor estão afastados no mesmo dia — se um dos dois está presente, o estágio acontece.
- `dia_semana` / `turno` / `hora_inicio` / `hora_fim` — a janela; usados no conflito de horário e no **intervalo mínimo de 2h entre áreas no mesmo dia**. Locais **multi-dia** guardam os dias adicionais em `locais_dias` (no protótipo, um array `dias`).
- `capacidade` — vagas simultâneas (o antigo `grupo_aluno`).
- `numero_encontros` — **total fixo de encontros do cenário, vindo do ESPELHO** (ex.: 18, 40, 20). É o eixo do motor: define quantas sessões agendar e quando a área conclui (encontros feitos ≥ total).
- `carga_horaria` — horas que o estágio nesse local cobre (consequência dos encontros × duração; informação secundária).
- `passagem_grupo` — **passagem de grupo**: se `true`, o último encontro de um grupo é o primeiro do próximo (1 dia de sobreposição). Na projeção de grupos, a onda seguinte começa no último dia da anterior; se `false`, começa depois.
- `ativo` — desativação sem apagar histórico.

**6. Relacionamentos:**
- `N:1` com `ciclos`, `areas` e `docentes`.
- `1:N` com `locais_dias` (dias adicionais de um local multi-dia).
- `1:N` com `alocacoes` (um local recebe vários alunos, até o limite de `capacidade`).
- `1:N` com `indisponibilidades_local` (um local pode ter vários períodos indisponíveis).

**7. Regras de negócio:**
- Validação: `capacidade > 0`.
- **Soft delete via `ativo`**: desativar um local com o ciclo em andamento **dispara remanejo** (as sessões futuras daquele local voltam para a fila).
- A área/campo/docente de uma alocação **derivam do local** — não se duplicam nas tabelas filhas.

### Tabela: `alocacoes`

**1. Nome da tabela:** `alocacoes`

**2. Módulo/Área:** Estágio / Saída do motor de alocação.

**3. Objetivo:** Representa **um aluno ocupando um local** — o "ONDE" da escala. É gerada pelo motor durante o bootstrap e ajustada cirurgicamente no remanejo. Amarra o aluno, o local e a matrícula que originou o vínculo.

**4. Funcionalidades relacionadas:**
- Geração da escala (passo final do bootstrap).
- Remanejamento (recalcula só as alocações afetadas).
- Tela de estágios (escala gerada) e calendário individual do aluno.
- Trava manual da comissão.

**5. Principais campos:**
- `aluno_id` / `local_id` / `matricula_id` — os três vínculos.
- `data_inicio` — quando a ocupação começa.
- `data_fim_prevista` — recalculada a cada remanejamento.
- `ajuste_encontros` — ajuste manual do professor no contador de encontros feitos (+ reforço / − falta), limitado a `[0, total]`; é o que permite antecipar ou reabrir a conclusão por exceção.
- `travada` — **trava manual: o motor nunca mexe numa alocação travada**.
- `status` — `ativa`, `concluida` ou `cancelada`.

**6. Relacionamentos:**
- `N:1` com `alunos`, `locais` e `matriculas`.
- `1:N` com `sessoes` (uma alocação se desdobra em várias datas concretas).

**7. Regras de negócio:**
- Par (`aluno_id`, `local_id`) é **único** — o aluno não ocupa o mesmo local duas vezes.
- **Regra de congelamento**: alocação `travada` nunca é tocada pelo motor.
- Recriada na geração; no remanejo é ajustada, não reconstruída do zero.

### Tabela: `sessoes`

**1. Nome da tabela:** `sessoes`

**2. Módulo/Área:** Estágio / Saída do motor — a menor unidade da escala.

**3. Objetivo:** As **datas concretas** de cada estágio (substitui o array `calendario[]` embutido da v1). É a granularidade que faz o sistema "andar sozinho": sessões passadas contam horas; o remanejo move apenas as futuras que colidem.

**4. Funcionalidades relacionadas:**
- Cálculo de horas cumpridas e % de carga por área.
- Conclusão automática de área.
- Remanejamento cirúrgico (identifica exatamente quais sessões futuras colidem).
- Calendário individual do aluno.

**5. Principais campos:**
- `alocacao_id` — a ocupação a que a sessão pertence.
- `data` — o dia da sessão.
- `hora_inicio` / `hora_fim` — herdadas do local, mas **gravadas na sessão** (o histórico não muda se o local mudar depois).
- `horas` — horas daquela sessão; somam no progresso.
- `status` — `prevista`, `cumprida`, `remanejada` ou `cancelada`.

**6. Relacionamentos:**
- `N:1` com `alocacoes`. É a folha da árvore da escala.

**7. Regras de negócio:**
- **Transição automática**: sessão com `data` no passado e status `prevista` vira `cumprida`, somando horas na área.
- **Regra de congelamento**: sessões `cumpridas` (passado) nunca são movidas pelo remanejo.
- Horários são **copiados** do local no momento da geração — não referenciados — para blindar o histórico contra alterações futuras do local.
- Índice em (`alocacao_id`, `data`) para navegação eficiente do calendário.

### Tabelas: `grupos` e `grupo_alunos`

**1. Nome das tabelas:** `grupos` (+ associativa `grupo_alunos`).

**2. Módulo/Área:** Estágio (saída do motor — **molde de caixas materializado no bootstrap**; ver `REGRAS_MOTOR_ESCALA.md`).

**3. Objetivo:** Materializar o conceito de **grupo** com que a comissão pensa: uma **onda** de alunos que ocupa um **(local, dia)** numa **janela** (entra e conclui junta). A capacidade do local é o **tamanho do grupo**. No modelo **grade-primeiro**, o motor materializa **todos os grupos do ciclo de uma vez no bootstrap** (não só o atual) — datas = infraestrutura, independentes de aluno — e só depois preenche.

**4. Funcionalidades relacionadas:**
- Aba **Grupos** na tela de Estágios (por local: atual + previstos, com janelas, membros, **CH de pico** por aluno e **ocupação N/cap** por grupo).
- Motor: materializa **o molde no bootstrap**; grupos futuros são **re-deriváveis**, o molde é **persistido** (fonte de verdade); membros **`fixado`** sobrevivem à regeração.

**5. Principais campos (`grupos`):**
- `local_id` / `area_id` — o cenário e a área.
- `onda` — `1` = grupo atual; `2, 3…` = ondas seguintes (cascata).
- `status` — `em_andamento` (atual) | `previsto`.
- `data_inicio` / `data_fim` — a janela (datas reais na onda atual; re-derivável nas futuras).
- `grupo_alunos`: `grupo_id`, `aluno_id`, `aviso` (dependência/conflito, ex.: "entra ao concluir Voz (previsto 15/09)"), **`fixado`** (remanejo manual: se `true`, o motor **não mexe** no membro ao regerar — migration `f3b8c1d4e6a2`).

**6. Relacionamentos:**
- `grupos` `N:1` com `locais`, `areas`, `ciclos`; `1:N` com `grupo_alunos`.
- `grupo_alunos` `N:1` com `grupos` e `alunos` (par único).

**7. Regras de negócio (grade-primeiro — ver `REGRAS_MOTOR_ESCALA.md`):**
- **Materialização:** o molde de **todos os grupos do ciclo** é gerado no **bootstrap**, por **(local, dia)**, fatiando as datas viáveis (dia fixo, pulando feriado/sem-cobertura) em blocos de `N = teto(carga / horas_sessao)`. Contam-se **sessões viáveis**, não semanas.
- **Cascata:** ondas do mesmo slot são blocos **consecutivos**; a seguinte começa quando a anterior fecha, até a última que **cabe no ciclo** (parcial → não vira grupo). Com **`locais.passagem_grupo`**, começa no **último dia** da anterior (sobreposição de 1 dia); sem, depois.
- **Preenchimento:** por `ordenamento`, objetivo **cobertura > lotação**, caixa **mais cheia com vaga**; 4 restrições duras (**30h**, **2h entre áreas** no mesmo dia, dia/turno, **restrições de local** §6.2). Uma área conclui com **uma caixa qualquer** que a atenda.
- **Matrícula no meio do ciclo** → o aluno entra em **vaga sobrando de um grupo futuro** (nunca num já iniciado).
- **Persistência:** o molde é **persistido** (fonte de verdade); a onda em andamento tem datas comprometidas, as futuras **re-derivam**. No protótipo (`versao_2`) é a coleção `grupos` com membros embutidos; no relacional são estas duas tabelas.

### Resumo do módulo Estágio

Este módulo é o motor da v2 e materializa o trio **O QUE → ONDE → QUANDO**. `locais` é a oferta de cenários de um ano; `alocacoes` conecta cada aluno a um local (respeitando capacidade, conflitos de dia/turno e o intervalo mínimo de **2h entre áreas no mesmo dia**); `sessoes` explode essa conexão nas datas concretas. A inteligência do sistema está em `sessoes`: é dela que saem as horas cumpridas, a conclusão automática e o alerta de risco. E é o par de mecanismos **trava manual** (`alocacoes.travada`) + **congelamento do passado** (`sessoes.cumprida`) que garante o princípio da v2 — o remanejo é cirúrgico e nunca destrói o que já é válido.

---

## Módulo 5 — Calendário institucional

Períodos e eventos que o motor precisa respeitar ao montar/remanejar a escala.

### Tabela: `afastamentos`

**1. Nome da tabela:** `afastamentos`

**2. Módulo/Área:** Calendário institucional.

**3. Objetivo:** Tabela **genérica de ausências** (férias, licenças, outros). Substitui a antiga tela isolada de "Férias" da v1. Cada linha é um período de ausência de **uma pessoa: um docente OU um preceptor**.

**4. Funcionalidades relacionadas:**
- Passo **Afastamentos** do bootstrap (depois de Docentes, Locais e Preceptores).
- Tela de Afastamentos na operação (seletor docente/preceptor).
- Visão consolidada (pessoa × dias de ausência).
- Remanejamento (ajusta só as sessões **sem cobertura** no período — ver regra abaixo).

**5. Principais campos:**
- `docente_id` — o docente ausente (nulo se o afastamento for de preceptor).
- `preceptor_id` — o preceptor ausente (nulo se o afastamento for de docente).
- `ciclo_id` — o ciclo de referência.
- `tipo` — `ferias`, `licenca` ou `outro`.
- `motivo` — texto livre ("congresso X", "atestado médico"…).
- `data_inicio` / `data_retorno` — o período.
- `criado_em` — auditoria: distingue o que foi bootstrap do que foi ajuste no meio do ciclo.

**6. Relacionamentos:**
- `N:1` com `docentes` **ou** `N:1` com `preceptores` (exatamente uma das duas FKs preenchida).
- `N:1` com `ciclos`.

**7. Regras de negócio:**
- Validação: `data_retorno >= data_inicio`.
- **Exatamente uma pessoa por afastamento**: `docente_id` XOR `preceptor_id`.
- **Regra de cobertura:** um afastamento só suspende os encontros de um local nas datas em que **todos** os responsáveis do local (docente **e** preceptor) estão afastados ao mesmo tempo. Um único afastado não derruba o estágio se o outro responsável cobre.
- Qualquer inclusão/edição/remoção com o ciclo em andamento **dispara remanejo**.
- Obs.: quando o preceptor de um local é um docente (`locais.preceptor_tipo = docente`), a ausência dele é registrada como afastamento **de docente**.

### Tabela: `indisponibilidades_local`

**1. Nome da tabela:** `indisponibilidades_local`

**2. Módulo/Área:** Calendário institucional.

**3. Objetivo:** Registra **indisponibilidade temporária** de um local (imprevisto no campo, docente em congresso). Usa o padrão "tabela de períodos" em vez de um flag — ao fim do período, o local volta a valer sozinho.

**4. Funcionalidades relacionadas:**
- Tela de Locais na operação (só aparece na operação, **nunca no bootstrap**).
- Remanejamento (só as sessões futuras daquele local no período voltam para a fila).

**5. Principais campos:**
- `local_id` — o local indisponível.
- `motivo` — texto livre.
- `data_inicio` / `data_fim` — o período de indisponibilidade.

**6. Relacionamentos:**
- `N:1` com `locais` (um local pode ter vários períodos indisponíveis).

**7. Regras de negócio:**
- **Exclusiva da Operação** — no bootstrap todos os locais entram disponíveis.
- **Reversão automática**: ao fim do período, o local volta a valer sem ação manual.
- Cadastrar uma indisponibilidade com o ciclo em andamento **dispara remanejo**.

### Tabela: `eventos`

**1. Nome da tabela:** `eventos`

**2. Módulo/Área:** Calendário institucional.

**3. Objetivo:** Guarda os eventos do calendário do ciclo: feriados (via API), acadêmicos/reuniões (manual) e importados (Google Calendar). Determina em quais datas o estágio é (ou não) bloqueado.

**4. Funcionalidades relacionadas:**
- Passo 6 do bootstrap.
- Tela de Eventos e "Próximos eventos" do painel.
- Sincronização com Google Calendar e API de feriados.
- Motor de alocação (empurra sessões que caem em datas bloqueantes).

**5. Principais campos:**
- `ciclo_id` — o ciclo do evento.
- `nome` / `tipo` (`academico`, `feriado`, `reuniao`, `recesso`, `outro`).
- `origem` — `manual`, `google` ou `api_feriados`; permite **re-sincronizar sem duplicar nem apagar os manuais**.
- `data_inicio` / `data_fim` — o período.
- `bloqueia_estagio` — **atributo que substitui o hardcode da regra "evento de Linguagem não bloqueia"** da v1.
- `google_event_id` — chave do Google Calendar (upsert quando `origem = google`).

**6. Relacionamentos:**
- `N:1` com `ciclos`.

**7. Regras de negócio:**
- Validação: `data_fim >= data_inicio`.
- Índice **único** em (`ciclo_id`, `nome`, `data_inicio`) — evita duplicação na re-sincronização.
- Só eventos com `bloqueia_estagio = true` empurram sessões; a antiga regra hardcoded virou um simples atributo booleano.
- Evento novo/alterado bloqueante com o ciclo em andamento **dispara remanejo**.

### Resumo do módulo Calendário institucional

As três tabelas respondem à mesma pergunta sob ângulos diferentes: **quando o estágio NÃO pode acontecer.** `afastamentos` bloqueia por *pessoa* (docente ou preceptor) — e só derruba o local quando **todos** os seus responsáveis faltam no mesmo dia; `indisponibilidades_local` bloqueia por *local*; `eventos` bloqueia por *data do calendário*. Todas alimentam o motor na geração e viram **gatilhos de remanejo** quando alteradas na operação. Duas escolhas de design se repetem aqui: (1) modelar ausência como **período com datas** (que se auto-reverte) em vez de flag permanente; e (2) transformar regras antes hardcoded (feriados, "Linguagem não bloqueia") em **dados** — atributos e origens — para que a comissão configure sem tocar em código.

---

## Módulo 6 — Operação

Tabelas de apoio ao Painel de Operação: a fila de mudanças pendentes e o feed de atividade.

### Tabela: `fila_remanejo`

**1. Nome da tabela:** `fila_remanejo`

**2. Módulo/Área:** Operação.

**3. Objetivo:** Acumula os **gatilhos pendentes** que tornam a escala desatualizada (docente afastado, local indisponível, evento importado…). É o que mantém `ciclos.escala_desatualizada = true` até o remanejo ser aplicado.

**4. Funcionalidades relacionadas:**
- Banner de remanejo no painel ("3 alterações pendentes afetam a escala").
- Pré-visualização do remanejamento (o que será recalculado).

**5. Principais campos:**
- `ciclo_id` — o ciclo afetado.
- `quando` — a data em que o gatilho entrou.
- `texto` — descrição do gatilho acumulado.

**6. Relacionamentos:**
- `N:1` com `ciclos`.

**7. Regras de negócio:**
- Enquanto houver itens na fila, o ciclo permanece `escala_desatualizada = true` e o banner fica aceso.
- A fila é esvaziada quando o remanejamento é confirmado e aplicado.

### Tabela: `atividade`

**1. Nome da tabela:** `atividade`

**2. Módulo/Área:** Operação.

**3. Objetivo:** Feed de **atividade recente** do Painel de Operação — um log legível das ações relevantes (edições, remanejos, sincronizações, marcos do ciclo).

**4. Funcionalidades relacionadas:**
- Card "Atividade recente" do painel.

**5. Principais campos:**
- `ciclo_id` — o ciclo.
- `quando` — quando a atividade ocorreu.
- `texto` — descrição legível.
- `tipo` — `ciclo`, `edicao`, `remanejo` ou `sync`.

**6. Relacionamentos:**
- `N:1` com `ciclos`.

**7. Regras de negócio:**
- É um registro **informativo** (não dispara comportamento); serve à transparência da operação.

### Resumo do módulo Operação

Estas duas tabelas são o "sistema nervoso" do painel do dia a dia. `fila_remanejo` é **acionável** — cada linha é uma mudança que ainda não foi refletida na escala e que mantém o alerta aceso; esvaziá-la é o objetivo do botão *Remanejar*. `atividade` é **informativa** — o diário de bordo do ciclo. Juntas, elas materializam o princípio-chave da v2: mudanças não se aplicam sozinhas à escala; elas se **acumulam visivelmente** e esperam a decisão do gestor.

---

## Módulo 7 — Histórico

### Tabela: `historico`

**1. Nome da tabela:** `historico`

**2. Módulo/Área:** Histórico / Arquivo de anos encerrados.

**3. Objetivo:** Um **retrato (snapshot) denormalizado de propósito**, gravado no encerramento do ciclo — um registro por aluno. Copia os valores em vez de referenciá-los, para que o registro do ano **nunca mude**, mesmo que aluno, local ou área sejam editados/removidos depois. É a garantia de que "o histórico é o que aconteceu", não "o que as tabelas dizem hoje".

**4. Funcionalidades relacionadas:**
- Encerramento de ciclo (etapa que grava o snapshot).
- Tela de Histórico (abas por ano; egressos com situação e carga total; somente leitura).

**5. Principais campos:**
- `ciclo_id` — vínculo para auditoria/drill-down (o único que ainda referencia).
- `ano` — chave de navegação da tela (2026 · 2025…).
- `aluno_nome` / `matricula` — **cópias (snapshot)**, não FKs.
- `areas` — JSON com uma entrada por área: `{nome, carga_exigida, horas_cumpridas, data_conclusao}` — inclusive as não concluídas, com as horas em que pararam.
- `carga_horaria_total` — soma das horas cumpridas no ciclo.
- `situacao` — `ciclo_completo` (todas as áreas **da fase** do aluno concluídas) ou `pendente`.
- `encerramento` — data do encerramento.

**6. Relacionamentos:**
- `N:1` com `ciclos` (apenas para auditoria).
- **Deliberadamente NÃO tem FK para `alunos` ou `areas`** — os dados são copiados, não referenciados.

**7. Regras de negócio:**
- **Denormalização intencional**: copia valores para blindar o passado.
- Gravado uma vez, no encerramento; **somente leitura** daí em diante.
- Pendências (aluno que não fechou todas as áreas da sua fase) **não impedem** o encerramento — são gravadas como estão.

### Resumo do módulo Histórico

`historico` é a única tabela que quebra de propósito a regra da normalização. Enquanto todo o resto do sistema usa FKs para evitar duplicação, aqui a duplicação é o objetivo: um registro imutável do que aconteceu naquele ano, imune a edições futuras. Ela é o produto final do Fluxo 3 (Encerramento) e a fonte da tela de consulta por ano. O detalhe elegante é que **nada é apagado no encerramento** — alunos, alocações e sessões continuam no banco amarrados ao `ciclo_id`; o snapshot em `historico` é apenas a camada de consulta rápida e à prova de alterações.

---

## Módulo 8 — Autenticação

### Tabela: `usuarios`

**1. Nome da tabela:** `usuarios`

**2. Módulo/Área:** Autenticação / Controle de acesso.

**3. Objetivo:** Guarda os usuários da comissão que acessam o sistema, com perfil de permissão. Base da tela de login e do controle de o que cada perfil pode fazer.

**4. Funcionalidades relacionadas:**
- Tela de login (autenticação por e-mail institucional).
- Controle de permissões por perfil.
- (Extensível) recuperação de senha, gestão de usuários.

**5. Principais campos:**
- `nome` — identificação.
- `email` — **único**; usado no login.
- `senha_hash` — a senha **armazenada com hash**, nunca em texto puro.
- `perfil` — `administrador`, `coordenacao` ou `consulta`; define o nível de acesso.
- `ativo` — permite desativar acesso sem apagar o usuário.
- `created_at` — auditoria.

**6. Relacionamentos:**
- **Isolada** — não referencia nem é referenciada pelas tabelas transacionais na modelagem atual. (Auditoria por usuário, se necessária no futuro, entraria por aqui.)

**7. Regras de negócio:**
- `email` é **único**.
- **Senha sempre criptografada** (`senha_hash`) — nunca em texto puro.
- Perfil padrão `consulta` (menor privilégio) no cadastro.
- **Soft delete via `ativo`**: desativar em vez de apagar.

### Resumo do módulo Autenticação

`usuarios` é um módulo transversal e autocontido: controla *quem entra* e *o que pode fazer*, sem se acoplar aos dados do ciclo. Segue as práticas padrão de segurança — e-mail único, senha com hash, perfis de permissão e desativação em vez de exclusão. Na modelagem atual ela é intencionalmente isolada; se o sistema precisar rastrear autoria das ações (quem fez cada edição/remanejo), o caminho natural é adicionar uma FK de `usuarios` na tabela `atividade`.

---

## Mapa consolidado de relacionamentos

```
                       areas (catálogo fixo, atravessa ciclos)
                        ▲  ▲
                        │  └────────────────┐
ciclos ─┬─< locais ─────┘                   │
        │      ▲  └─< indisponibilidades_local
        │      │
        │      └── docente_id → docentes ─< afastamentos
        │
        ├─< alunos ─< matriculas (aluno × área)  ─┐
        │      │                                  │ (matricula_id)
        │      └─< alocacoes (aluno × local) ─────┘ ─< sessoes
        │
        ├─< eventos
        ├─< fila_remanejo
        ├─< atividade
        └─< historico (snapshot por aluno, gravado no encerramento)

usuarios  (autenticação — isolada)
```

### Leitura rápida das relações

| De | Para | Cardinalidade | Motivo |
|---|---|---|---|
| `alunos` → `ciclos` | FK `ciclo_id` | N:1 | Aluno pertence a um ano |
| `locais` → `ciclos` | FK `ciclo_id` | N:1 | Oferta muda por ano |
| `locais` → `areas` | FK `area_id` | N:1 | Local pertence a uma área |
| `locais` → `docentes` | FK `docente_id` | N:1 | Local tem um docente |
| `matriculas` → `alunos` / `areas` | FKs | N:N resolvido | Aluno cursa N áreas; área tem N alunos |
| `alocacoes` → `alunos` / `locais` / `matriculas` | FKs | N:1 cada | Aluno ocupa local por uma matrícula |
| `sessoes` → `alocacoes` | FK `alocacao_id` | N:1 | Datas concretas de uma ocupação |
| `afastamentos` → `docentes` **ou** `preceptores` / `ciclos` | FKs | N:1 | Ausências de um docente OU preceptor (XOR) |
| `indisponibilidades_local` → `locais` | FK `local_id` | N:1 | Períodos indisponíveis de um local |
| `eventos` → `ciclos` | FK `ciclo_id` | N:1 | Eventos de um ano |
| `fila_remanejo` / `atividade` → `ciclos` | FK `ciclo_id` | N:1 | Fila e feed por ciclo |
| `historico` → `ciclos` | FK `ciclo_id` | N:1 | Apenas auditoria (dados são snapshot) |

### As regras de negócio que atravessam vários módulos

1. **Único ciclo ativo:** só um `rascunho`/`em_andamento` por vez.
2. **O estado decide a tela:** `ciclos.status` roteia o usuário (Boas-vindas / Bootstrap / Painel).
3. **Nada se aplica sozinho na operação:** edições setam `escala_desatualizada = true`, enfileiram em `fila_remanejo` e acendem o banner; o motor só age no *Remanejar*.
4. **Remanejo cirúrgico:** recalcula só o afetado. **Nunca toca** em área `concluida`, sessão `cumprida` (passado) nem alocação `travada`.
5. **Conclusão automática:** dirigida pelas `sessoes` (encontro no passado vira `cumprido` → conta como feito → fecha a área quando os **encontros feitos ± ajuste** atingem o **total** `numero_encontros`; horas são consequência).
6. **Preservação de histórico:** soft delete (`ativo`) em docentes/locais/usuários; catálogos permanentes; e o snapshot imutável de `historico` no encerramento.
7. **Regras viraram dados:** o que era hardcode na v1 (feriados, "Linguagem não bloqueia") agora é atributo (`bloqueia_estagio`, `origem`) configurável pela comissão.
8. **Fila de espera é derivada:** matrícula `em_andamento` sem alocação ativa = aluno aguardando vaga. Quando uma vaga abre, o próximo da fila (por prioridade, entre os que cabem no horário) é promovido — ver seção dedicada abaixo.

---

## Regra de negócio — Fila de espera e promoção por vaga

Esta seção detalha a regra de **promoção da fila de espera**: quando um aluno conclui uma área e libera uma vaga, o próximo aluno que aguarda naquela área é alocado no lugar. É uma das regras mais importantes da operação e, por isso, ganha documentação própria.

> **⚠️ Reconciliação grade-primeiro (`REGRAS_MOTOR_ESCALA.md`):** neste modelo as vagas
> futuras já vêm **materializadas no molde** (grupos previstos). Então: (a) a
> **conclusão antecipada** por reforço **não libera vaga** (o aluno segue no grupo,
> §10.5); (b) **desmatrícula/interrupção** deixa a vaga **vazia até o grupo terminar**
> — sem promoção automática; (c) uma vaga aberta no meio do ciclo é **decisão da
> coordenação** (via *Remanejar*), e nova matrícula entra numa **vaga sobrando de
> grupo futuro**. O fluxo de *Remanejar* abaixo continua válido como a **ferramenta
> humana** dessa decisão; o "efeito dominó automático" **não** se aplica.

> **Status de implementação (protótipo v2):** o que já está implementado é a **projeção** — a fila e o balanço oferta × demanda são derivados em tempo real (`ofertaDemandaAreas`), e a **previsão de data de início em cascata** de cada aluno da fila é calculada por `previsaoInicioArea` e exibida no card da aba **Ofertas** (Alunos → Ofertas → clicar numa área). A **promoção efetiva** descrita abaixo (criar a alocação + sessões do promovido via *Remanejar*) é **o alvo de projeto, ainda não implementada** no motor. A previsão em cascata está especificada em Regras de Negócio §10.1.

### Conceito — a fila de espera não é armazenada, é derivada

Não existe tabela `fila_espera` nem campo `aguardando`. A fila de espera de uma área é **calculada em tempo de consulta** pelo cruzamento de duas tabelas:

> **Aluno na fila de espera** = tem **matrícula `em_andamento`** naquela área **E não tem** nenhuma **alocação ativa** amarrada a essa matrícula.

O aluno na fila **já está matriculado** — o que falta a ele é a *alocação*. Promover alguém, portanto, significa **criar uma alocação** (e suas sessões), nunca criar uma nova matrícula.

Os três motivos que colocam um aluno na fila (o sistema não os distingue na estrutura — todos resultam em "matrícula sem alocação"):
1. **Capacidade lotada** — todos os locais ativos da área atingiram o limite.
2. **Conflito de horário** — há vaga, mas o único horário bate com outro estágio que o aluno já tem no mesmo dia/turno.
3. **Nenhum local ativo** — não existe local ativo naquela área no ciclo.

### O evento que dispara a promoção

O gatilho é a **liberação de uma vaga**, cuja origem principal é a **conclusão de área**:

1. Aluno A conclui a área X → sua matrícula vira `concluida` **e** sua alocação vira `concluida`.
2. Alocação `concluida` deixa de ocupar vaga → **vaga livre = `capacidade − alocações ativas`** naquele local.
3. Monta-se a fila de espera da área X (matrículas `em_andamento` sem alocação ativa).
4. Ordena-se por `alunos.ordenamento` (menor = maior prioridade).
5. Promove-se o **primeiro que couber** na vaga → cria alocação + gera sessões.

> Outras origens de vaga (aumento de `capacidade`, novo local cadastrado na operação) já são gatilhos de remanejo existentes e disparam a mesma varredura de promoção. A conclusão é apenas a fonte mais orgânica.

### As duas decisões de negócio definidas

**Decisão 1 — Aplicação: via Remanejar, com prévia.**
A promoção **não é automática e silenciosa**. Coerente com o princípio "nada altera a escala sozinho na operação", a conclusão que libera vaga **gera um gatilho em `fila_remanejo`** e acende o banner. O gestor clica em **Remanejar**, vê a pré-visualização (quem será promovido, se o início tardio estoura o prazo) e confirma. A promoção vira mais uma categoria na tela de remanejo, ao lado de "sessões movidas" e "realocadas".

**Decisão 2 — Desempate: prioridade entre os que cabem.**
A vaga liberada pertence a um local com dia/turno/horário fixos. Entre os alunos da fila que **cabem** naquele horário (sem conflito com estágios que já têm), vence o de maior prioridade (`ordenamento`). Um aluno mais prioritário que **não cabe** é pulado *apenas para essa vaga* e continua na fila aguardando uma vaga compatível. Isso evita deixar a vaga ociosa.

### O que a regra afeta no funcionamento atual

| Área do sistema | Mudança necessária |
|---|---|
| **Conclusão de área** | Além de marcar a matrícula `concluida`, passa a marcar também a **alocação `concluida`** — é isso que libera a contagem de vaga. |
| **Cálculo de capacidade** | "Vaga livre" = `capacidade − alocações ATIVAS`. Alocação `concluida` não conta mais como ocupação. |
| **Motor de remanejo** | Ganha um passo de "varredura de vagas liberadas → promoção por prioridade + encaixe". Nova categoria na pré-visualização. |
| **`fila_remanejo`** | Novo tipo de gatilho: *"conclusão liberou vaga em \<área\>"*. |
| **`atividade`** (feed) | Novo registro tipo `remanejo`: *"\<aluno\> promovido da lista de espera em \<área\>"*. |
| **Previsão de conclusão / risco** | Aluno promovido começa no meio do ciclo → sua previsão pode ultrapassar `ciclos.data_fim` → entra no KPI "alunos em risco". |

### Impacto no modelo de dados

**Nenhuma tabela nova é necessária.** A fila permanece derivada de `matriculas × alocacoes`, e o desempate usa `alunos.ordenamento`, que já existe. A regra é essencialmente **lógica de back-end (FastAPI)**, não estrutura.

- **Único ponto de atenção:** `ordenamento` hoje é **global por aluno**. Como desempate de fila ele funciona (mais prioritário na vida = mais prioritário na fila). Se um dia a comissão quiser prioridade **por área**, aí sim seria necessário um campo de prioridade em `matriculas`. Por ora, o global resolve.

### Como exibir na área de Alunos

Duas visões, ambas 100% derivadas (sem tabela nova):

**1. No detalhe do aluno** — no card da área que ele aguarda:
```
Linguagem   ⏳ Aguardando vaga · 2º na fila (por prioridade)
```

**2. Visão consolidada por área** (útil para a comissão enxergar demanda × oferta):
```
Lista de espera — Linguagem              capacidade total: 12 · ocupadas: 12
 1º  Otávio Barros      (ordenamento 4)   aguarda desde 12/03
 2º  Mariana Teixeira   (ordenamento 7)
 3º  Lucas Ferreira     (ordenamento 9)
```

A posição é calculada na hora — em SQL, `ROW_NUMBER() OVER (PARTITION BY area_id ORDER BY ordenamento)` sobre as matrículas em espera; o "aguarda desde" sai de `matriculas.data_matricula`.

### Como a matrícula é criada — a critério do professor (tudo ou em partes)

Quem matricula o aluno nas áreas é o **professor/coordenação**, pela tela de Alunos. A matrícula é **flexível**:

- Pode-se matricular o aluno em **todas as áreas da fase de uma vez** — nesse caso, as áreas que não couberem já numa vaga ficam na **fila de espera** desde o início e vão entrando conforme as vagas liberam.
- Ou pode-se matricular em **apenas algumas** áreas agora e **acrescentar as demais depois** (por exemplo, ao concluir uma, cadastrar a próxima).

A conclusão de uma área tem, então, **dois efeitos independentes**:

1. **Vaga liberada → o próximo da fila daquela área pode entrar** (por prioridade). Hoje isso é exposto como **projeção** — a previsão de entrada da fila em cascata (ver Regras de Negócio §10.1); o avanço efetivo da escala é aplicado via **Remanejar**.
2. **Abrir a próxima área do aluno**, quando ele ainda não foi matriculado nela — é uma ação **manual** do professor (o sistema não deduz "qual é a próxima", pois não há ordem fixa entre as áreas). Se o aluno já tiver sido matriculado em todas as áreas no início, este passo é dispensável.

A interface **avisa a comissão** de quando há vaga a preencher e de quando há aluno a matricular — é o que a visão de oferta × demanda abaixo resolve.

### Painel de oferta × demanda por área (na tela de Alunos)

Além da lista de espera, a área de Alunos exibe, por área, o **balanço entre capacidade e ocupação**. Isso responde a duas perguntas de uma vez: *tem gente esperando?* e *tem vaga sobrando?* Tudo derivado, sem tabela nova:

- **capacidade total** = soma de `locais.capacidade` dos locais **ativos** da área.
- **ocupadas** = nº de `alocacoes` **ativas** em locais da área.
- **vagas livres** = `capacidade total − ocupadas`.
- **fila** = nº de matrículas `em_andamento` **sem** alocação ativa na área.

Cruzando **vagas livres × fila**, surgem quatro situações — cada uma com uma ação sugerida à comissão:

| Vagas livres | Fila | Situação | O que mostrar / ação |
|:---:|:---:|---|---|
| 0 | 0 | **Equilíbrio** | Tudo ocupado, ninguém esperando. Nada a fazer. |
| 0 | > 0 | **Demanda reprimida** | "3 aguardando, sem vaga" — a fila só anda quando alguém concluir ou a capacidade aumentar. |
| > 0 | 0 | **Vaga sobrando** | "2 vagas livres" — a comissão **pode matricular manualmente** um aluno elegível nessa área. |
| > 0 | > 0 | **Vaga ociosa com fila** ⚠️ | Sinal de **conflito de horário**: há vaga *e* gente esperando, mas quem espera não cabe no dia/turno das vagas livres. Merece destaque — pode exigir remanejo manual ou novo local. |

A quarta linha é a mais valiosa de sinalizar: sem ela, "tem vaga e tem fila ao mesmo tempo" parece um bug, quando na verdade é a regra de encaixe (prioridade **entre os que cabem**) agindo corretamente.

**Exemplo visual na tela de Alunos:**
```
Oferta × demanda por área — Ciclo 2026

 Área             Cap.  Ocup.  Livres  Fila   Situação
 Linguagem         12    12      0      3     ⚠ demanda reprimida (3 aguardando)
 Audiologia I      10     8      2      0     ○ 2 vagas sobrando — pode matricular
 Voz                8     6      2      2     ⚠ vaga ociosa + fila (conflito de horário)
 Disfagia          10    10      0      0     ✓ equilíbrio
```

### Consulta SQL de referência (oferta × demanda por área)

```sql
WITH cap AS (   -- capacidade e ocupação por área
  SELECT l.area_id,
         SUM(l.capacidade)                                        AS capacidade,
         COUNT(al.id) FILTER (WHERE al.status = 'ativa')          AS ocupadas
  FROM locais l
  LEFT JOIN alocacoes al ON al.local_id = l.id
  WHERE l.ativo = true AND l.ciclo_id = :ciclo_id
  GROUP BY l.area_id
),
fila AS (       -- quantos aguardam por área
  SELECT m.area_id, COUNT(*) AS fila
  FROM matriculas m
  WHERE m.status = 'em_andamento'
    AND NOT EXISTS (SELECT 1 FROM alocacoes al
                    WHERE al.matricula_id = m.id AND al.status = 'ativa')
  GROUP BY m.area_id
)
SELECT ar.nome AS area,
       COALESCE(cap.capacidade, 0)                      AS capacidade,
       COALESCE(cap.ocupadas, 0)                        AS ocupadas,
       COALESCE(cap.capacidade, 0) - COALESCE(cap.ocupadas, 0) AS vagas_livres,
       COALESCE(fila.fila, 0)                           AS fila
FROM areas ar
LEFT JOIN cap  ON cap.area_id  = ar.id
LEFT JOIN fila ON fila.area_id = ar.id
ORDER BY ar.nome;
```

### Consulta SQL de referência (fila de espera por área)

```sql
SELECT
  ar.nome                                                        AS area,
  a.nome                                                         AS aluno,
  a.ordenamento,
  m.data_matricula                                               AS aguarda_desde,
  ROW_NUMBER() OVER (PARTITION BY m.area_id ORDER BY a.ordenamento) AS posicao
FROM matriculas m
JOIN alunos a  ON a.id  = m.aluno_id
JOIN areas  ar ON ar.id = m.area_id
WHERE m.status = 'em_andamento'
  AND NOT EXISTS (
    SELECT 1 FROM alocacoes al
    WHERE al.matricula_id = m.id
      AND al.status = 'ativa'
  )
ORDER BY ar.nome, posicao;
```
