# Regras do Motor de Escala — Modelo Grade-Primeiro

## 0. Contexto, usuários e ciclo

Sistema web para a **comissão de estágio do curso de Fonoaudiologia** organizar
os estágios obrigatórios dos alunos. Hoje isso é feito em planilha Excel e dá
muito trabalho — o objetivo da refatoração é tornar essa rotina **simples,
visual e confiável**.

**Perfis:**

- **Comissão de estágio** (≈ 5 coordenadoras): **único perfil que edita** —
  cadastra alunos, locais, férias e eventos, roda a alocação e faz os ajustes.
- **Professores e alunos** (≈ 30 alunos por turma + docentes): **apenas
  visualizam** os calendários e o panorama.

**Ciclo = 1 ano.** Cada aluno tem **um ano de estágio** para fechar a carga
horária de todas as suas áreas. Tudo que este documento chama de *ciclo* é esse
ano letivo de estágio.

**Cadastro no início do ciclo (inputs do bootstrap):**

- **alunos da turma** — áreas matriculadas, carga horária a cumprir em cada
  área e, quando for o caso, a **marcação de prioritário** (flag manual, ver
  §5);
- **locais de estágio** — área, campo, docente (+ preceptor opcional), dia,
  turno, horário e nº de vagas (= os *slots* do §2);
- **férias/afastamentos dos docentes** e **eventos do calendário acadêmico**
  (feriados, eventos que bloqueiam datas).

Com isso cadastrado, a comissão clica em **"Gerar alocação"** e o motor roda as
fases descritas abaixo.

## 1. Ideia central: grade-primeiro

A geração da escala **não é puxada pela demanda**. Ela é **grade-primeiro**:
primeiro o sistema materializa **todo o molde do ciclo — todos os grupos (caixas)
possíveis de todos os locais**, depois preenchem-se com alunos.

O que muda de fundo é **de quem a data é função**:

- **Puxado pela demanda (errado):** o motor só gera encontros "à medida que aloca
  aluno" — por isso alguns locais ficam com uma onda só.
- **Grade-primeiro (correto):** a data é função **apenas da infraestrutura**
  (calendário + afastamentos + nº de encontros). Os alunos entram *depois*, e
  trocar quem está na fila **não redesenha as caixas** — só muda o conteúdo delas.

Isso também elimina a fonte de inconsistência de haver **dois cálculos de data**
no motor: existe **uma única fonte de verdade** — as datas reais das caixas,
geradas no bootstrap.

Consequência central para o dia a dia: **a grade do aluno é gerada para o ciclo
inteiro de uma vez**. Depois de fechado o bootstrap, o sistema apenas
**acompanha o tempo passando** — terminou um grupo, o próximo grupo do aluno
**já começa de imediato**, conforme o que foi planejado. Nada é puxado para
frente nem empurrado para trás depois disso.

## 2. Vocabulário

- **Slot (unidade ofertável):** o que se oferta não é o *campo físico*, e sim o
  **slot = campo + dia da semana + turno + horário**. Um mesmo campo pode expor
  **vários slots**, cada um para um **grupo diferente**, rodando em paralelo —
  inclusive no **mesmo dia com turnos diferentes** (ex.: "AMB. IAPI" segunda de
  manhã *e* segunda à tarde = 2 slots, 2 grupos; "Ambulatório ORL" seg/qua/sex =
  3 slots). Cada slot tem **seus próprios responsáveis**: **1 docente**
  (obrigatório) e **0 ou 1 preceptor** de campo (opcional; a mesma pessoa pode se
  repetir em vários slots). No bootstrap, o **slot** (área, campo, dia, turno,
  horário, capacidade, carga) é criado no passo *Áreas e Locais*, e os
  **responsáveis** (docente + preceptor) são escolhidos no passo *Configurações
  de campo*. O aluno cumpre a área inteira **dentro de um slot** (1×/semana no dia
  fixo). No schema, cada slot = 1 linha em `locais` (`docente_id` +
  `preceptor_tipo`/`preceptor_id`).
- **Caixa (vaga de onda / grupo):** uma corrida completa de um grupo numa área —
  `N` sessões consecutivas no dia fixo de um par (local, dia). Tem período, lista
  de datas reais, capacidade (`grupo_aluno`) e ocupantes. **Terminar a caixa =
  concluir a área.**
- **Molde / grade do ciclo:** o conjunto de **todas as caixas possíveis** de
  todos os pares (local, dia), rodando em paralelo no tempo, do início ao fim do
  ciclo. Gerado uma vez, no bootstrap. Determinístico — independe de aluno.
- **Caixas candidatas de (aluno, área):** todas as caixas, em qualquer
  local/horário, que atendem aquela área. **O aluno precisa de uma só** para
  concluir a área.

## 3. Restrições duras (viabilidade)

Barram a entrada de um aluno numa caixa. São **quatro**:

1. **Teto de 30h/semana** — em toda semana que a caixa ocupa, `horas_da_semana +
   horas_da_sessão ≤ 30`. O cálculo é **semana a semana**: caixas que **não se
   sobrepõem no tempo não competem entre si** — quando uma caixa termina, as
   horas (e o dia da semana) daquela caixa ficam livres para outra área dali em
   diante.
2. **Intervalo mínimo de 1h30** entre duas áreas que caiam no **mesmo dia**.
3. **Sem conflito de dia/turno** — não dobrar o mesmo turno **em caixas cujos
   períodos se sobrepõem**. O mesmo dia/turno pode ser reutilizado por outra área
   depois que a caixa anterior encerra.
4. **Blocklist de local** — o local não pode estar na lista de restrições do aluno.

Fora essas quatro, o objetivo é **alocar a galera e fechar as caixas**.

## 4. Fase 1 — Materialização do molde (bootstrap)

O sistema gera **todo o molde de uma vez: todos os grupos possíveis do ciclo**,
para todos os locais. Unidade atômica = **(local, dia)**. Um local que atende
segunda e terça gera **duas famílias de caixas independentes**. Turno só
desmembra se não for integral.

```
Para cada par (local, dia) do ciclo:
  1. N = numero_encontros = ceil(carga_da_área / horas_por_sessão)
  2. datas_viaveis = todas as ocorrências desse dia-da-semana,
     de inicio_ciclo até fim_ciclo, REMOVENDO:
        - feriados / eventos que bloqueiam a data
        - dias sem cobertura de responsáveis:
            · docente E preceptor ambos afastados; ou
            · slot só com docente (sem preceptor) e docente afastado
              → a área fica DESATIVADA durante o período do afastamento
  3. Fatia datas_viaveis em blocos consecutivos de tamanho N
  4. Cada bloco completo vira uma caixa:
        { area, local, dia, turno, periodo:[1ª..Nª data],
          datas:[...], capacidade: grupo_aluno, ocupantes:[] }
  5. Bloco final incompleto (< N) → NÃO vira caixa (capacidade perdida no ciclo)
```

**Empurrar por feriado sai de graça:** como se conta **sessões viáveis** (não
semanas corridas), a sessão que cairia num feriado simplesmente pula pra próxima
data válida e a caixa termina mais tarde sozinha, sem regra de "empurrar".

Exemplo — local terça, N=4, ciclo a partir de 03/03, feriado em 14/04:

- Fila de terças viáveis: 03, 10, 17, 24/03, 31/03, 07/04, ~~14/04~~, 21/04, 28/04…
- Caixa 1 = [03, 10, 17, 24/03] → **03/03–24/03**
- Caixa 2 = [31/03, 07/04, 21/04, 28/04] → **31/03–28/04** (o feriado empurrou as
  duas últimas sessões automaticamente)
- Caixa 3 = próximas 4 terças viáveis… até o fim do ciclo.

As caixas saem **encadeadas** (a próxima começa onde a anterior terminou) porque
são fatias consecutivas da mesma fila — sem gerenciar "início da próxima onda".

## 5. Fase 2 — Rascunho: prioridade 100% manual (marca e arrasta)

Com o molde pronto, o bootstrap entra em **fase de rascunho**. A prioridade
**não é um peso do algoritmo** — ela é feita **manualmente mesmo**:

1. a coordenação **marca** os estudantes prioritários (flag no aluno);
2. e **arrasta** cada um (drag & drop) **para onde precisa que ele faça** —
   qualquer caixa, de qualquer área/local do molde, conforme desejar.

Só isso: **marcar e arrastar**. Não há ranking, peso nem ordem de prioridade
calculada pelo motor — quem decide onde o prioritário fica é a coordenação, na
mão. Toda alocação feita no rascunho fica **travada**: a alocação automática
(Fase 3) não desfaz o que a coordenação cravou e apenas preenche os demais
alunos ao redor.

### 5.1 Operações do rascunho

| Operação | O que faz | Efeito |
|---|---|---|
| **Marcar prioritário** | liga a flag de prioridade no aluno, destacando-o para o arraste manual | marcação |
| **Arrastar (mover)** | arrasta o aluno para uma caixa de qualquer área/local | conteúdo |
| **Substituir** | troca dois alunos entre duas caixas (1-a-1), preservando o tamanho de cada uma | conteúdo |
| **Remover** | tira o aluno da caixa → volta para a **fila** (aguardando) daquela área | libera 1 assento |
| **Adicionar da fila** | puxa um aluno da fila para uma caixa com vaga | ocupa 1 assento |
| **Travar / destravar** | marca uma alocação como intocável, para a alocação automática não desfazer o ajuste manual | protege conteúdo |

Arrastar aluno no rascunho mexe **só no conteúdo** — o molde (caixas e suas
datas) **não muda**.

### 5.2 Cálculo em tempo real

Toda operação acima, **antes de confirmar**, recalcula e mostra o impacto contra
as **4 restrições duras** (§3):

1. **CH semanal do aluno** — a CH relevante é a da **semana de pico**: somam-se
   as horas de todas as caixas do aluno que se sobrepõem em cada semana e
   mostra-se o maior valor vs. o teto (ex. `26h/30h`). Caixas que não se
   sobrepõem não somam.
2. **Conflito de dia/turno** — a caixa destino não pode cair no mesmo dia/turno de
   outra caixa do aluno cujas janelas se sobreponham.
3. **Intervalo de 1h30** — se duas áreas caem no mesmo dia, ≥1h30 entre elas.
4. **Blocklist** — o local da caixa destino não pode estar bloqueado para o aluno.

Feedback da **caixa**: ocupação `N/cap`, com destaque de "fechou" (cheia) vs
"fraca" (meia-vazia).

### 5.3 Violação de restrição dura → **bloqueia**

Quando o ajuste manual violaria qualquer uma das 4 restrições duras, o sistema
**não executa o movimento**. Em vez disso:

- explica o **motivo** exato (ex.: "passaria de 30h na semana de 07/04";
  "conflito de terça/manhã com Audiologia"; "faltam 1h30 entre áreas no mesmo
  dia"; "local bloqueado para este aluno"); e
- **sugere a caixa viável mais cedo** para aquele aluno naquela área.

As 4 restrições duras são **invioláveis também no ajuste manual** — não há
override.

## 6. Fase 3 — Alocação automática (bootstrap)

Depois do rascunho, roda a **alocação automática**: o motor coloca cada aluno em
sua caixa, **planejando a grade do ciclo inteiro do aluno de uma vez**.

### 6.1 Encadeamento no tempo: vaga na semana = dia reutilizável

O motor **sabe quando cada caixa termina**. Então, ao montar a grade anual do
aluno, ele **encadeia áreas em sequência**: quando uma área conclui, aquele dia
da semana (e aquelas horas) **abrem na semana do aluno**, e o motor **usa esse
mesmo dia para a próxima área**, numa caixa que comece dali em diante. O sistema
**calcula isso automaticamente** — o teto de 30h e o conflito de dia/turno são
avaliados **semana a semana**, nunca somando caixas que não coexistem no tempo.

Resultado: ao final do bootstrap, o aluno tem a **grade completa do ciclo** —
todos os grupos dele, do primeiro ao último, já com datas. Depois disso o
sistema só acompanha: **terminou um grupo, começa de imediato o outro**, sem
clique, sem gatilho, sem remanejo.

### 6.2 Objetivo: cobertura acima de lotação

O objetivo é **lexicográfico** (nesta ordem, sem inverter):

1. **Cobertura** — maximizar o nº de alunos que **concluem suas áreas
   obrigatórias** no ciclo. Esse é o alvo real.
2. **Lotação** — empacotar: fechar o máximo de caixas na capacidade. É objetivo
   **secundário** — "caixa cheia" é um proxy de eficiência de campo, nunca um fim
   que justifique deixar um aluno de fora.

Regra prática do desempate: **uma caixa 3/4 onde todo mundo conclui vence uma
caixa 4/4 que joga um aluno para a fila.**

### 6.3 Dois botões de controle

- **Ordem dos alunos** = `ordenamento` (ordem total, sem empates) — vale apenas
  para os alunos **restantes**, que a coordenação não posicionou na mão. Os
  **prioritários já foram marcados e arrastados no rascunho** (§5) e entram
  travados; a automática não os move.
- **Escolha da caixa** = **empacotamento** (caixa mais cheia com vaga). Decide
  *onde cada um vai*, subordinado à cobertura.

### 6.4 Ordenar as áreas do aluno pela escassez (evita fila desnecessária)

O preenchimento é guloso e resolve **área por área**. Se resolver as áreas numa
ordem ruim, ele "queima" o aluno em um conflito evitável:

> O aluno pega a caixa de Motricidade da terça de manhã; a única caixa viável de
> Audiologia dele também é terça de manhã **no mesmo período** → conflito → fila
> em Audiologia. Se tivesse pego outra caixa de Motricidade (ou uma que termina
> antes de a de Audiologia começar), as duas fechavam.

Correção (heurística clássica de CSP — *most-constrained-first*): **antes de
alocar, ordenar as áreas de cada aluno pela escassez** — a que tem **menos caixas
viáveis para ele** primeiro. Resolve-se antes quem tem menos opção, e sobra
folga para as áreas mais flexíveis.

```
Para cada aluno em ordem do ordenamento
(prioritários já arrastados no rascunho entram travados; a automática só
completa o que faltar deles e aloca os demais):
    areas_pendentes = áreas matriculadas ainda não alocadas
                      (alocações travadas do rascunho já contam como resolvidas)
    ordena areas_pendentes por (nº de caixas viáveis para ESTE aluno) crescente

    Para cada área nessa ordem:
        viaveis = caixas que atendem a área, com vaga, que passam nas 4 restrições
                  duras JÁ considerando as caixas que o aluno acabou de receber
                  — inclusive caixas FUTURAS em dias/turnos que só liberam depois
                  que outra caixa do aluno terminar (encadeamento §6.1)
        se viaveis vazio:
            aluno → AGUARDANDO VAGA nessa área (fila do próximo ciclo)
        senão:
            escolhe a caixa MAIS CHEIA que ainda tem vaga     # empacota
            desempate: início mais cedo
            aloca o aluno nessa caixa
```

Empacotamento vence conforto (início mais cedo) — mas **cobertura vence
empacotamento**, e as 4 restrições duras nunca são violadas.

### 6.5 Transparência é saída de primeira classe

Como o preenchimento é **heurístico** (não garante o ótimo global), o motor
**tem de explicar suas decisões** — não é opcional:

- por que cada aluno ficou na caixa em que ficou;
- por que cada aluno da fila **não coube** (qual restrição barrou, em qual
  semana, contra qual outra área).

Sem isso a coordenação não confia na sugestão.

### 6.6 Consolidação — sempre tentar fechar

O preenchimento (§6.4) é guloso e decide **caixa a caixa, no momento** de cada
colocação. Visto o quadro final, ainda sobram **caixas fracas** (meia-vazias)
que poderiam ser fundidas. Por isso, **logo após o preenchimento**, o motor roda
uma passada de **consolidação**: da caixa mais fraca para a menos fraca, tenta
mover cada ocupante para uma caixa **mais cheia da MESMA área** que tenha vaga e
passe nas 4 restrições duras. Duas caixas pela metade viram uma cheia; a que
esvazia sai do uso.

É pura eficiência de lotação (§6.2, objetivo **secundário**), com guardas que a
tornam segura:

- **Cobertura nunca cai** — só se move para um destino viável da mesma área, então
  o aluno continua concluindo aquela área; a consolidação **nunca manda ninguém
  para a fila**.
- **Só concentra** — o destino tem de estar **igual ou mais cheio** que a origem
  (nunca espalha).
- **Pins são intocáveis** — ocupantes fixados no rascunho (§5) não se movem.
- **Empacotamento vence conforto** — como no §6.4, uma caixa mais cheia (ainda que
  comece mais tarde) vence uma mais vazia mais cedo.

## 7. Fase 4 — Eventos de meio de ciclo

Depois de fechado o bootstrap, a grade anual de todos os alunos está pronta e o
sistema **só acompanha o tempo passando** — e isso é **automático, por data**: o
próximo grupo do aluno entra em andamento no dia do seu 1º encontro e a área é
marcada como concluída quando os encontros se cumprem, **sem banner e sem clique**
(§8.5). O molde é **fixo** e o motor **não mexe em quem já teve a grade gerada**.

Só uma classe de evento altera a escala já gerada: **eventos de infraestrutura**
(§7.1). E mesmo esses **não se aplicam sozinhos** — entram numa **lista de
pendências** e são aplicados pela comissão pelo **Remanejar** (§7.3): revisar o
impacto → confirmar → aplicar **só no afetado**. O Remanejar **nunca regera o
ciclo inteiro**.

### 7.1 O que gera pendência de remanejo (só infraestrutura)

| Gatilho | Ação (pontual, aplicada no Remanejar) |
|---|---|
| **Feriado novo** incluído no meio do ciclo | data vira inválida → reflow (§8.3) |
| **Evento novo** que bloqueia a data | idem |
| **Afastamento sem cobertura**: docente **E** preceptor afastados; ou, se o slot tem **só docente**, o docente afastado | área/slot **desativada no período** → datas inválidas → reflow (§8.3) |
| **Local desativado / inválido** | datas do local viram inválidas → reflow; se a caixa não fecha, **descarte com carry-forward** (§8.3) |
| **Docente/preceptor desligado** (`ativo` = falso) | idem afastamento sem cobertura |
| **Novo local/área** com alunos **aguardando na fila** | gera a grade do novo local e aloca os **elegíveis** da fila (§8.4) |
| **Aluno novo / troca de área** (edição da comissão) | coloca numa caixa **futura** com vaga (§8.1/§8.6) |

Regra geral: **editar pontualmente sem refazer tudo** — reaproveita o que está
válido e mexe só no estritamente afetado.

### 7.2 O que NÃO gera pendência (nada a revisar)

- **Aluno conclui uma área / vaga aberta** — não dispara nada; o **próximo grupo
  entra em andamento automaticamente** (por data) e a conclusão é derivada, **sem
  banner**. A grade do ciclo inteiro já foi feita no bootstrap.
- **Desistência / interrupção de aluno** — o grupo **fica desfalcado**; não se
  mexe nos demais (§8.2).
- **Ajuste manual** da comissão (mover/trocar/adicionar aluno) — é a própria
  edição válida; não marca nada a revisar.
- **Cadastro comum** não-estrutural (renomear, corrigir um dado) — só registra no
  log de atividade.
- **Frequência** — o sistema **não contabiliza** presença: assume que o aluno
  compareceu e realizou o encontro. O professor controla por fora (§8.5). O
  sistema é um **painel visual** da evolução do aluno para a coordenação acompanhar.

### 7.3 Como funciona o Remanejar (revisar impacto → aplicar pontual)

Os eventos de infraestrutura (§7.1) entram numa **lista de pendências** e acendem
o aviso **"há mudanças a revisar"**. **Nada é aplicado automaticamente.** Ao abrir
o **Remanejar**, a comissão vê um **resumo do impacto** de aplicar as pendências —
por exemplo: *"o novo feriado de 14/04 empurra 2 sessões da caixa X; a conclusão
do aluno Y passa de 20/11 para 27/11; 1 caixa passa do fim do ciclo (risco)"*. A
comissão então **confirma**, e o sistema aplica o reflow / descarte / alocação
**só nas caixas e alunos afetados** — **nunca regera o ciclo**. Caixas concluídas
não são tocadas; caixas futuras já se re-derivam do molde sozinhas (§8.3).

## 8. Fase 4 — detalhamento (dia a dia)

**Filosofia — responsabilidade compartilhada.** O sistema **propõe** a escala e
dá **visibilidade** do andamento; a verdade da presença é do docente, **fora do
sistema**. O dia a dia é deliberadamente **leve** — quanto menos o motor mexe e
quanto mais simples a solução, melhor.

### 8.1 Nova matrícula no meio do ciclo

Aluno do ciclo que pega uma área nova **entra numa vaga sobrando de uma caixa já
existente** — sem criar caixa nova nem mexer em datas. Detalhe que cai da regra
"uma caixa = N encontros": tem de ser uma caixa cujo **início ainda é futuro**
(se já começou, o aluno perdeu encontros e não fecha os N). Escolha = **caixa
futura mais cedo** da área com vaga, passando nas 4 restrições duras. Sem caixa
futura viável → fila / próximo ciclo. Raio: 1 caixa. Essa colocação entra na
**revisão do Remanejar** (§7.3): a comissão vê onde o aluno entraria e confirma.

### 8.2 Desistência / interrupção

A vaga **fica vazia até a caixa terminar** — o grupo segue desfalcado. Não
reprograma, não reoferta, não cascateia, **não gera gatilho de remanejo**. Não
se mexe nos demais alunos. Raio: nenhum além do assento que ficou vago.

### 8.3 Feriado / evento / afastamento sem cobertura / local inválido

**Estes são os únicos eventos de meio de ciclo que alteram datas de caixas já
existentes.** Cobre:

- **feriado ou evento novo** que cai num dia de encontro;
- **afastamento sem cobertura** (é um **período**: da saída até o retorno) —
  acontece só quando **ninguém cobre o local no período**: docente **e** preceptor
  afastados juntos; ou, num slot **só com docente** (sem preceptor), o docente
  afastado. Nesse período o **local fica temporariamente inativo**; ao voltar o
  responsável, **reativa sozinho** (o afastamento é período). Se houver preceptor
  presente enquanto o docente se afasta (ou vice-versa), **há cobertura → não
  bloqueia**;
- **local inválido / desativado**, ou **docente e preceptor desligados**.

Todas as datas do período afetado viram **inválidas** → **reflow**: as sessões,
da 1ª data bloqueada em diante, empurram para as próximas datas viáveis (no caso
do afastamento, para **depois do retorno**).

Escopo do reflow — **todas as caixas do (local, dia) andam para frente**, mas por
mecanismos diferentes:

- só a **caixa em andamento** tem datas **comprometidas (reais)** → é a única
  **empurrada ativamente** (a partir da 1ª data bloqueada);
- as **caixas futuras (previstas) são projeções** que se **re-derivam do molde** —
  já nascem contando o novo bloqueio e **começam mais tarde** sozinhas; na prática
  deslocam junto;
- as **caixas concluídas** (atrás) não são tocadas.

Efeitos colaterais: a caixa em andamento pode **passar do fim do ciclo** →
conclusões viram **risco**; se não fecha mais dentro do ciclo, é **descartada** e
seus alunos voltam à fila **com carry-forward** — a matrícula segue
`em_andamento` e os **encontros já cumpridos são preservados**, então o aluno
retoma numa próxima caixa em `feitos/total` (uma caixa nova, para alunos novos,
começa `0/total`). Afeta **apenas esse par (local, dia)** — os outros locais
ficam intactos.

Raio: o (local, dia) afetado — caixa em andamento empurrada + caixas futuras
deslocadas (re-derivadas); outros locais ficam intactos.

### 8.4 Novo local/área cadastrado

**Único remanejo que realoca alunos**, e só nesta condição: existe **fila de
alunos aguardando** para esse local/área. Ação:

1. gera **toda a grade** do novo local (Fase 1 restrita a ele);
2. aloca os **elegíveis da fila** que puderem entrar, respeitando **todas as
   regras** (as 4 restrições duras e o encadeamento §6.1).

Alunos que **já têm grade gerada** não são tocados — o sistema não puxa ninguém
pra frente nem empurra pra trás para aproveitar o local novo. Raio: 1 local +
alunos da fila.

### 8.5 Presença e status de conclusão

O sistema **não contabiliza frequência**. Pressupõe que o aluno compareceu e
realizou o encontro em cada data da caixa; o controle real de presença é do
professor, **por fora do sistema**.

Status de conclusão da área (por aluno):

- **período da caixa terminou** → área **marcada como concluída** para os
  ocupantes. A partir daí o motor **não realoca mais essa área** para o aluno —
  ela sai do escopo e o sistema foca apenas no que ainda falta. Concluir **não
  dispara evento nenhum**: não libera gatilho, não remaneja, não cascateia — o
  próximo grupo do aluno já começa conforme a grade pré-gerada.

O sistema **deriva "em andamento / futuro / concluído" pela data** (e pelos
encontros cumpridos), não por um estado gravado manualmente: o próximo grupo
entra em andamento **sozinho** no dia do 1º encontro, e a área conclui sozinha ao
atingir os encontros. É só o tempo passando — sem banner, sem clique.

### 8.6 Aluno trocou de área

Edição pontual da comissão, combinação de duas regras já existentes:

1. **Saída da área antiga** = desistência daquela caixa (§8.2): o assento fica
   vago até a caixa terminar, sem cascata nos demais;
2. **Entrada na área nova** = nova matrícula (§8.1): caixa **futura mais cedo**
   da nova área com vaga, passando nas 4 restrições duras. Sem caixa futura
   viável → fila.

Raio: 2 caixas (a que ele deixa + a que ele entra). Nenhum outro aluno é tocado.

## 9. Acompanhamento, alertas e visualização

O sistema **acompanha a carga horária** de cada aluno em cada área ao longo do
ano (com base nas datas planejadas das caixas, já que presença é presumida —
§8.5) e dá visibilidade para todos os perfis:

- **Alerta de risco de não fechar CH:** quando o motor **prevê que um aluno não
  vai fechar as horas de alguma área até o fim do ano** — tipicamente porque um
  reflow (§8.3) empurrou a caixa para além do fim do ciclo, ou porque o aluno
  está **aguardando vaga** numa área sem caixa futura viável — ele emite alerta
  para a comissão. O alerta é **informativo**: sinaliza o risco, mas não
  remaneja nada sozinho.
- **Calendário individual do aluno:** cada aluno (e a comissão) vê seu
  calendário completo do ano — todas as caixas, datas e locais — com opção de
  **exportar/enviar**.
- **Pendências de infra a revisar:** quando há eventos de infraestrutura
  pendentes (§7.3), o sistema sinaliza **"há mudanças a revisar"**; o Remanejar
  mostra o impacto antes de a comissão aplicar. Nada é aplicado sozinho.
- **Panorama geral (dashboard):** visão da turma para a comissão e docentes —
  quem está alocado, quem está na fila, quem tem **risco de não fechar carga
  horária**, quais locais estão lotados vs. com vaga, etc. **Todas as caixas do
  molde aparecem, inclusive as vazias** (podem receber aluno novo ou realocação).

Leitura é aberta aos perfis autorizados (professores e alunos); **edição é
exclusiva da comissão** (§0).

## 10. Arquivamento anual (histórico)

Ao final do ano, o sistema **arquiva os dados como histórico daquele ano de
estágio**. Como cada aluno tem exatamente 1 ano de estágio, fica preservado o
**registro completo da jornada**: grade planejada, caixas cursadas, áreas
concluídas, pendências que foram para a fila. O arquivo é **somente leitura** —
o ciclo seguinte começa com um bootstrap novo (áreas pendentes/incompletas
entram como matrícula no novo ciclo).

## 11. Decisões cravadas

1. **Caixa parcial no fim do ciclo** → não é criada (capacidade perdida).
2. **Local com mais de um dia** → cada dia é uma família de caixas separada;
   turno só desmembra se não for integral.
3. **Uma caixa = uma conclusão de área** — a mesma área pode existir em várias
   caixas (locais/horários diferentes); o aluno precisa de **uma qualquer**.
4. **Prioridade é manual** — prioridade não é peso de algoritmo: a coordenação
   **marca** o aluno como prioritário e **arrasta** para onde quiser (travado).
   O `ordenamento` da alocação automática (ordem total, sem empates) só rege os
   alunos não posicionados na mão.
5. **Grade anual de uma vez** — a grade do aluno é planejada para o ciclo inteiro
   no bootstrap (com encadeamento de áreas no tempo); depois disso não se move
   pra frente nem pra trás.
6. **Vaga aberta não é gatilho** — conclusão de área, desistência e ajuste manual
   não geram pendência de remanejo; grupo desfalcado segue desfalcado.
7. **Sem contabilização de frequência** — presença é presumida; o professor
   controla por fora.
8. **Afastamento sem cobertura desativa a área** — 2 responsáveis fora, ou 1
   fora quando o slot só tem docente, invalida as datas do período.
9. **Novo local só remaneja a fila** — gera a grade do local e aloca os
   elegíveis aguardando; quem já tem grade não é tocado.
10. **Ciclo = 1 ano** — cada aluno tem um ano para fechar todas as áreas;
    ao final, os dados são arquivados como histórico somente leitura.
11. **Intervalo mínimo entre áreas no mesmo dia = 1h30.**
12. **Só a comissão edita** — professores e alunos apenas visualizam
    (calendário individual e dashboard).
13. **Alertas são informativos** — o sistema avisa o risco de não fechar CH,
    mas nunca remaneja sozinho por causa de um alerta.
14. **Remanejar = revisar impacto → aplicar pontual** — só eventos de
    infraestrutura geram pendência; o Remanejar mostra o impacto e aplica **só o
    afetado**, **nunca regera o ciclo**. Concluídas não são tocadas; futuras
    re-derivam do molde.
15. **Progressão no tempo é automática e por data** — o próximo grupo entra em
    andamento no 1º encontro e a área conclui ao cumprir os encontros, sem banner
    nem clique.
16. **Caixa descartada usa carry-forward** — quando um local morre, o aluno
    mantém `em_andamento` e **preserva os encontros já feitos** ao voltar à fila
    (retoma em `feitos/total`; caixa nova começa `0/total`).
17. **Caixas sempre visíveis** — todas as caixas do molde aparecem, inclusive as
    vazias (recebem aluno novo / realocação).
