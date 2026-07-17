# Atores do Motor de Alocação — Sistema de Gestão de Estágios (Fono UFCSPA)

> **Para que serve este documento.** Descrever, em linguagem de negócio (sem
> código), **quem** participa da montagem da escala de estágios e **como cada um
> afeta** o resultado. Serve para a **comissão validar as regras** antes da
> implementação. Cada "ator" é descrito pelo que ele **faz** e pelo **efeito**
> que isso dispara nos demais.
>
> Companheiro de: `REGRAS_DE_NEGOCIO.md` (regras em detalhe) e
> `DOCUMENTACAO_MODELO_DADOS_V2.md` (modelo de dados).
>
> **Como ler cada ator:** Papel → Estados → tabela de **Ação/Evento · Regra · Efeito no motor**.

---

## Legenda de estados

| Onde | Estados possíveis | Significado |
|---|---|---|
| **Matrícula** (aluno × área) | `em andamento` · `concluída` · `interrompida` | o que o aluno cursa naquela área |
| **Área do aluno** (derivado) | `a iniciar` · `em andamento` · `em risco` · `concluída` · `interrompida` | como a tela mostra o progresso |
| **Alocação** (aluno num local) | `ativa` · `concluída` · `cancelada` | onde o aluno faz o estágio |
| **Sessão** (encontro) | `prevista` · `cumprida` · `remanejada` · `cancelada` | cada encontro semanal |
| **Grupo** (onda num local) | `em andamento` · `previsto` | a leva de alunos que ocupa o local numa janela |
| **Ciclo** | `rascunho` · `em andamento` · `encerrado` | a "temporada" de estágios |

> **Regra de ouro do motor:** a escala é **gerada por prioridade**. Os alunos entram
> na fila por `ordenamento` (**menor número = maior prioridade**) e o motor tenta
> alocar um a um. Quem não couber numa vaga fica na **fila de espera** e entra quando
> uma vaga abrir.

---

## Novidades desta rodada (para validar na reunião)

Regras novas mapeadas com a coordenação e já refletidas neste documento e no protótipo:

1. **Preceptores e cobertura docente-OU-preceptor.** Cada local tem um docente e,
   opcionalmente, um **preceptor de campo** (fonoaudióloga(o) externa à UFCSPA, ou
   até outro docente). **Um encontro só cai quando docente E preceptor estão
   afastados no mesmo dia** — se um dos dois está, o estágio acontece. Preceptores
   não têm login institucional: a conta é o **e-mail** (docentes, preceptores e
   alunos têm e-mail para notificações). → atores **Docente**, **Preceptor**, **Local**.
2. **Restrições de local do aluno.** Por padrão o aluno pode ir a todos os locais;
   por condição especial a coordenação **desmarca** locais específicos e o motor não
   o aloca neles. → ator **Aluno**.
3. **Grupos (ondas por local) + passagem de grupo.** A capacidade do local é o
   **tamanho do grupo**; além do grupo atual, o sistema **projeta as ondas seguintes**
   (quem entra quando o grupo anterior conclui). Locais com **passagem de grupo** têm
   1 dia de sobreposição (quem sai orienta quem entra). → ator **Grupo**, **Local**.
4. **Teto de 30h semanais por aluno.** O motor não aloca um estágio que faça o aluno
   passar de **30h/semana**. → ator **Aluno**.

> As decisões em aberto dessas regras estão na seção **"Pendências para a comissão
> confirmar"**, no fim do documento.

---

# ATORES PRINCIPAIS

## 1. Aluno

**Papel:** quem faz o estágio. Tem uma **prioridade** (`ordenamento`) e uma **fase**
(5º semestre = mini-ciclo só de Audiologia I; 6º/7º = as demais áreas).

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Conclui uma área** | A área conclui **automaticamente** quando os encontros *feitos* atingem o total previsto (não é check manual). | A vaga daquele local **é liberada** → o próximo da **fila** entra. Carga cheia é creditada. |
| **Fica em risco** | Está "em risco" quando, **no ritmo atual**, a conclusão prevista cai **depois do fim do ciclo**. O motor projeta as sessões semana a semana (até além do fim do ciclo) e, se a data final passar do `data_fim`, marca risco. | Sinaliza para a coordenação (não muda a alocação sozinho). Aparece no painel de risco. |
| **Interrompe o estágio** | Por motivo extraordinário (ex.: saúde), a coordenação **interrompe** uma área do aluno. A matrícula vira `interrompida` (guarda motivo + data), **não é apagada**. | Alocação **cancelada** + sessões futuras canceladas → **vaga liberada** para a fila. No fim do ciclo a área fica **pendente**. |
| **Fica pendente (não concluiu)** | No **encerramento**, se o aluno **não concluiu todas** as áreas da sua fase, o ciclo dele fica `pendente` (o oposto de `ciclo completo`). | Vai para o **histórico** como pendente. No **próximo ciclo**, as concluídas voltam como concluídas (carry-forward) e as pendentes/interrompidas voltam a cursar. |
| **Entra na fila de espera** | Uma área matriculada `em andamento` que **não coube** numa vaga (lotou ou choque de horário) fica na fila. | A fila é **ordenada por prioridade**; entra quando uma vaga abrir. |
| **Tem prioridade (ordenamento)** | Menor número = alocado antes. Ao remover um aluno, a fila é **reindexada** (não deixa buraco 1,2,4…). | Define a **ordem** em que o motor tenta alocar. |
| **Chega com áreas já concluídas** (carry-forward) | Aluno pode entrar no ciclo com áreas **já concluídas antes** (ex.: Audiologia I para os de 6/7; áreas de anos anteriores). | O motor **não realoca** áreas concluídas — elas só contam a carga e liberam a vaga. |
| **Tem restrições de local** | Por padrão o aluno pode ir a **todos** os locais; por **condição especial** a coordenação **desmarca** locais específicos (bloqueio por local, não por área). Configurável no bootstrap e no dia a dia (cadastro do aluno). | O motor **pula os locais bloqueados** para aquele aluno e o aloca em outro local liberado da mesma área. Ao salvar, se sobrar **área matriculada sem nenhum local liberado**, o sistema **avisa/bloqueia**. |
| **Teto de 30h semanais** | Um aluno **não pode passar de 30h/semana** somando todos os seus estágios (horas por encontro × dias/semana). É uma **constante do motor** (não vai ao banco). | Ao alocar, o motor **não coloca** um local que faria o aluno estourar 30h na semana; a área fica **sem vaga** com o motivo "excederia 30h semanais". |

---

## 2. Área (disciplina de estágio)

**Papel:** a matéria/estágio a cursar (ex.: Audiologia I, Voz, Hospitalar - Adulto).
Define **quanta carga** exige e **regras de acesso**.

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Exige carga horária** | Cada área tem uma carga exigida (horas). O nº de encontros do cenário (local) é o que fecha essa carga. | Determina **quantas sessões** o aluno precisa cumprir. |
| **É pré-requisito bloqueante** | **Só Audiologia I** é pré-requisito. Enquanto o aluno não a **concluir**, ele **não pode** ser alocado nas áreas de 6º/7º. | O motor **pula** áreas de 6/7 de quem ainda não concluiu Audiologia I. |
| **Pertence a uma fase** | Fase 5 (mini-ciclo, só Audiologia I) ou 6/7 (as demais). | Filtra **quais áreas** entram no progresso e no histórico de cada aluno. |

---

## 3. Local (campo de estágio)

**Papel:** onde o estágio acontece (unidade + campo + docente + **preceptor de campo** +
dia + turno + horário). É o recurso **escasso** — tem capacidade limitada. Cada local
tem **um docente** (UFCSPA) e, **opcionalmente, um preceptor de campo** (que pode ser um
preceptor externo **ou** outro docente).

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Tem capacidade (nº de vagas)** | Cada local aceita um número máximo de alunos ao mesmo tempo. | Quando **lota**, os próximos da área vão para a **fila**. |
| **Tem dia e turno fixos** | O aluno não pode ter **dois estágios no mesmo dia+turno**. | Gera **conflito de horário**: o motor pula o local e tenta outro da mesma área. |
| **Pode ser restrito para um aluno** | Um aluno com condição especial pode ser **bloqueado** de locais específicos (ver ator Aluno → restrições de local). | O motor **não aloca** esse aluno no local bloqueado; procura outro local liberado da área. |
| **Tem passagem de grupo** (opcional) | Marca no local: o **último encontro de um grupo é o primeiro do próximo** (1 dia de sobreposição — quem sai orienta quem entra). | Na projeção de grupos, a onda seguinte **começa no último dia** da anterior (sem a marca, começa depois). O dia é destacado na visão por campo. |
| **Define o nº de encontros** | O cenário do ESPELHO diz **exatamente** quantos encontros tem (é o total fixo do contador). | O motor gera **exatamente esse número** de sessões, semana a semana. |
| **Tem responsáveis (docente + preceptor)** | Para haver estágio numa data, basta que **UM** dos responsáveis (docente **ou** preceptor) esteja disponível. Só cai quando **os dois** estão afastados no mesmo dia. | O motor **pula/empurra** só as datas em que o local fica **sem cobertura** (todos os responsáveis afastados). |
| **Fica inativo** | Um local pode ser desativado. | As alocações naquele local entram para **remanejo** (realocação para outro campo da área). |
| **Fica indisponível num período** | O local pode fechar em datas específicas. | As sessões nessas datas são **empurradas** para a próxima data livre. |

---

## 4. Docente

**Papel:** professor da UFCSPA, responsável por um ou mais locais (e possível
**preceptor** de campo de um local — qualquer docente pode ser preceptor).

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Entra em afastamento** (férias/licença) | Durante o afastamento o docente não cobre os locais dele. Mas se o local tiver **preceptor presente**, o estágio **acontece mesmo assim** (cobertura). | Só cai a sessão numa data se **o preceptor do local também estiver afastado** (ou o local não tiver preceptor). |
| **É desligado** | Docente inativo não recebe mais alocações. | Dispara **remanejo** dos alunos que estavam com ele. |

## 4b. Preceptor (responsável de campo)

**Papel:** fonoaudióloga(o) de campo **externa à UFCSPA**, responsável por um local.
**Não tem login institucional** — a **conta é o e-mail** (obrigatório). Um preceptor
pode responder por **vários locais**. O papel de preceptor de um local também pode ser
ocupado por um **docente**.

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Entra em afastamento** | Se o **docente do local está presente**, o estágio **acontece** (cobertura). | Só cai a sessão numa data se **o docente do local também estiver afastado**. |
| **É desligado** | Preceptor inativo deixa de cobrir seus locais. | Dispara **remanejo** nos locais em que ele era o responsável de campo. |
| **É o próprio docente do local** | Mesma pessoa nos dois papéis (sem redundância). | O local é prejudicado sempre que **essa única pessoa** faltar. |

---

# ARTEFATOS GERADOS PELO MOTOR

> Estes três são a **saída** do motor. Uma frase resume: a **matrícula** diz *o quê*,
> a **alocação** diz *onde*, a **sessão** diz *quando*.

## 5. Matrícula — *o quê*

**Papel:** o par aluno × área. É o que a coordenação cria ao matricular o aluno.

| Estado | Como chega nele |
|---|---|
| `em andamento` | matriculado e ainda cursando (o motor **só aloca estes**). |
| `concluída` | fechou a carga (automático) **ou** já veio concluída de antes (carry-forward). |
| `interrompida` | a coordenação interrompeu por motivo extraordinário. |

## 6. Alocação — *onde*

**Papel:** liga um aluno a um local (a vaga que ele ocupa).

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **É travada** (trava manual) | A coordenação pode **travar** uma alocação. | O motor **nunca mexe** numa alocação travada (nem no remanejo). |
| **Recebe ajuste de encontros** | Ajuste manual do professor: **+1** = reforço, **−1** = falta. | Move só o **contador de feitos** (limitado entre 0 e o total). Pode antecipar/atrasar a conclusão. |

## 7. Sessão (encontro) — *quando*

**Papel:** a menor unidade da escala — cada encontro semanal.

| Estado | Como chega nele |
|---|---|
| `prevista` | encontro futuro agendado. |
| `cumprida` | encontro já passou (**presença assumida** — não há controle de frequência). |
| `remanejada` | foi movida de data (por evento/afastamento/indisponibilidade). |
| `cancelada` | cancelada (ex.: aluno interrompeu o estágio). |

## 7b. Grupo (onda por local) — modelo GRADE-PRIMEIRO

> Motor autoritativo: **`REGRAS_MOTOR_ESCALA.md`**. "Caixa" = este grupo. Mudou
> **quando/quanto** se gera (tudo no bootstrap), não o conceito de slot/onda.

**Papel:** a forma como a comissão pensa os alunos — uma **leva** que ocupa um
**(local, dia)** numa **janela** (entra e conclui junta). A **capacidade** do local é
o tamanho do grupo. Um campo com 2 dias/semana gera **2 famílias de grupos**.

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Materialização (bootstrap)** | Todos os grupos do ciclo são gerados **de uma vez, antes de alocar** — por (local, dia), fatiando as datas viáveis (dia fixo, pulando feriado/sem-cobertura) em blocos de `N = teto(carga/horas)`. Contam-se **sessões viáveis**, não semanas. | O **molde** de caixas do ciclo, vazio e **persistido** — fonte de verdade. |
| **Grupo 1 (em andamento)** | Alunos hoje no local, com datas **reais comprometidas**. | Onda atual da escala. |
| **Grupos seguintes (previstos)** | Blocos **consecutivos** da mesma fila de datas (cascata): o Grupo 2 começa quando o 1 termina, até o último que **fecha no ciclo** (parcial → não vira grupo). | Projeção **re-derivável** do molde persistido. |
| **Preenchimento** | Aloca por prioridade (`ordenamento`); objetivo **cobertura > lotação**; caixa **mais cheia com vaga** (empacotar) entre as **viáveis** (capacidade, dia/turno, **2h entre áreas**, **30h**, restrições AR-2). | Uma área conclui com **uma caixa qualquer** que a atenda. |
| **Aluno matriculado no meio do ciclo** | Entra numa **vaga sobrando de um grupo FUTURO** da área (nunca num já iniciado — não fecharia os N). | Ocupa o assento do grupo futuro; sem criar grupo nem mexer em datas. |
| **Conflito de horário num grupo previsto** | Se o dia/turno colide com outro compromisso do aluno na janela, sinaliza a **dependência**. | Aviso no membro: "entra ao concluir [área] (previsto DD/MM)". |
| **Passagem de grupo** | Em locais marcados (`passagem_grupo`), a onda seguinte começa no **último dia** da anterior — os dois coincidem 1 dia. | Janelas "encostam"; selo de passagem + dia destacado no calendário. |
| **Afastamento/feriado no meio** | Único evento que altera datas: dia sem cobertura → **reflow** só do grupo **em andamento** (futuros re-derivam). | Empurra as datas dali pra frente; pode passar do ciclo → risco/descarte. |
| **Remanejo manual durável** | A coordenação move/troca/fixa membros; membro **`fixado`** não é mexido numa regeração. | Coluna `grupo_alunos.fixado` (§9.1 do motor). |

## 8. Fila de espera *(derivada)*

**Papel:** não é cadastro — é **calculada em tempo real**. É a lista de matrículas
`em andamento` **sem** alocação ativa.

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Uma vaga abre no meio do ciclo** (desmatrícula/interrupção) | A vaga **fica vazia até o grupo terminar** — preenchê-la é **decisão da coordenação**, não automático (grade-primeiro, Fase 4). Nova matrícula entra num **grupo futuro** com vaga. | Sem "efeito dominó" automático; a fila alimenta o preenchimento do bootstrap e os grupos futuros. |

---

# RESTRIÇÕES DO CALENDÁRIO

## 9. Evento (calendário institucional)

**Papel:** datas que afetam o estágio (feriados, recessos, eventos acadêmicos).

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Bloqueia estágio** | Um evento marcado como *bloqueia* impede estágio naquelas datas. | Sessões nessas datas são **empurradas** para a próxima data livre. |
| **Não bloqueia** (ex.: "Linguagem") | Alguns eventos **não** bloqueiam (é um **atributo** do evento, não regra fixa). | As sessões seguem normalmente. |

## 10. Afastamento (docente ou preceptor)

**Papel:** período em que um **docente OU um preceptor** está fora (férias/licença/outro).
Cada afastamento é de uma única pessoa.

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Período de afastamento** | Um local só fica **sem cobertura** numa data quando **todos** os seus responsáveis (docente **e** preceptor) estão afastados ao mesmo tempo. Um só afastado não derruba o estágio. | Só as sessões nas datas **sem cobertura** são **remanejadas** para depois. |

## 11. Indisponibilidade de local

**Papel:** período em que um **local** específico fica fechado.

| Ação / Evento | Regra | Efeito no motor |
|---|---|---|
| **Período indisponível** | O local não recebe estágio naquelas datas. | Sessões no período são **empurradas** para a próxima data livre. |

---

# ORQUESTRAÇÃO

## 12. Ciclo

**Papel:** a "temporada" de estágios (ex.: 2026). É a **máquina de estados** que
decide o que a coordenação pode fazer.

| Estado | O que acontece |
|---|---|
| `rascunho` | **bootstrap**: cadastra locais, alunos, matrículas e **gera a escala** pela 1ª vez. |
| `em andamento` | **operação** do dia a dia: ajustes, interrupções, remanejos. |
| `encerrado` | fechado: vira **snapshot no histórico** (o passado não muda). |

- **No máximo 1 ciclo ativo por vez** (rascunho ou em andamento).
- Quando algo muda o cenário (afastamento, evento, local inativo, interrupção…), o ciclo
  fica marcado como **"escala desatualizada"** → sinal para a coordenação **remanejar**.
- **Abrir novo ciclo** copia os **locais** do ciclo anterior (preserva o histórico).

## 13. Coordenação (operador humano)

**Papel:** quem opera o sistema. Não é "do motor", mas é quem **dispara** as ações.

| Ação | Efeito |
|---|---|
| **Gera a escala** | Roda o motor: aloca por prioridade e cria as sessões. |
| **Ajusta encontros** (+/−) | Registra reforço ou falta de um aluno. |
| **Interrompe estágio** | Tira o aluno de uma área (libera vaga, vira pendente). |
| **Remaneja** | Aplica os ajustes pendentes (empurra sessões afetadas, realoca). |
| **Encerra o ciclo** | Gera o histórico e fecha a temporada. |

---

## Mapa do preenchimento e dos gatilhos (resumo visual)

> **Grade-primeiro:** as vagas futuras já estão no **molde** (grupos previstos
> materializados no bootstrap). Uma vaga que abre no meio do ciclo **não** é
> preenchida automaticamente — a coordenação decide (*Remanejar*). Não há "efeito
> dominó automático".

```
  Aluno desmatricula / interrompe
                │
                ▼
     VAGA no grupo fica VAZIA (até o grupo terminar)
                │
                ▼
   Coordenação decide (Remanejar)  ──►  fila / nova matrícula → grupo FUTURO com vaga
                                              │
                                              ▼
                                    ocupa o assento (sem mexer nas datas)
```

```
  Evento bloqueia · Local sem cobertura (docente E preceptor fora) · Local indisponível · Local inativo
                │
                ▼
      Escala fica "desatualizada"
                │
                ▼
     Coordenação REMANEJA  ──►  sessões empurradas / alunos realocados
```

---

## Pendências para a comissão confirmar

**Gerais**
- [ ] A definição de **"em risco"** está correta? (conclusão prevista **além** do fim do ciclo)
- [ ] **Interrupção**: só a coordenação pode? Precisa registrar quem autorizou?
- [ ] Ao **desligar um docente/preceptor** no meio do ciclo, o remanejo é automático ou só sinalizado?
- [ ] **Presença assumida** (sem controle de frequência) segue valendo?
- [ ] Carga horária dos **estágios hospitalares** (Pediatria/Adulto/Neonatologia) — divisão 50/60/50 é oficial?
- [ ] Falta algum ator/evento que a comissão conhece e não está aqui?

**Preceptores e cobertura**
- [ ] A regra "só cai quando **docente E preceptor** estão fora" está correta para todos os locais?
- [ ] Quando o **preceptor é um docente**, confirmar que a ausência dele entra como afastamento de docente.
- [ ] Os **e-mails** (docentes/preceptores/alunos) são a via oficial de notificação?

**Restrições de local do aluno**
- [ ] Quem pode definir a restrição (só coordenação)? Precisa registrar o **motivo**?
- [ ] Se todos os locais de uma área forem restritos ao aluno, **bloquear o salvamento** é o comportamento desejado?

**Grupos e passagem**
- [ ] Grupos futuros são **projeção re-derivável do molde persistido** (o molde é a fonte de verdade; só a onda em andamento tem datas comprometidas) — isso está claro para a comissão?
- [ ] **Passagem de grupo**: quais locais realmente têm? (hoje é uma marca por local)
- [ ] A duração estimada de cada onda (para prever as janelas) está boa ou precisa afinar?

**Teto de 30h semanais**
- [ ] **30h/semana** é o limite correto? Vale para todos os alunos igualmente?
- [ ] Como contar as horas de locais **multi-dia** e de turno **integral** — a conta (horas × dias) está certa?
