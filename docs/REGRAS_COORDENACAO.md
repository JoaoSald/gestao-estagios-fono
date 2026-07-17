# Como funciona o Sistema de Gestão de Estágios

**Curso de Fonoaudiologia · UFCSPA**
*Guia para a coordenação, em linguagem simples, sem termos técnicos*
*Atualizado em 09/07/2026*

---

## Em uma frase

O sistema é um **planejador da escala de estágios**. A coordenação cadastra os
alunos, os locais e o calendário do ano, e o sistema **monta automaticamente quem faz
qual estágio, onde, em que dias e até quando**, respeitando prioridade, vagas,
horários e as regras do curso. Ele também **prevê** quando cada vaga vai abrir e quando
cada aluno da fila vai poder começar.

> **Importante entender:** o sistema **planeja**, não controla presença. Ele assume
> que os encontros planejados acontecem e vai marcando como "feitos" conforme as datas
> passam. Não é um diário de classe.

---

## O ano de estágios (o "ciclo")

Cada ano letivo de estágios é um **ciclo**. O sistema trabalha com **um ciclo por vez**,
e ele passa por três momentos:

1. **Abertura (montagem):** a coordenação cadastra tudo do ano, ou seja, locais,
   professores, preceptores, alunos, matrículas e o calendário, e no fim manda **gerar
   a escala**.
2. **Operação (o dia a dia):** com a escala pronta, a coordenação acompanha o
   andamento, faz ajustes, matricula alunos novos, registra ausências e **remaneja**
   quando algo muda.
3. **Encerramento:** ao fim do ano, o ciclo é fechado e vira um **registro histórico**,
   uma "foto" do que aconteceu, que não muda mais.

Ao **abrir um novo ano**, o sistema já **traz os locais do ano anterior** como ponto
de partida (a coordenação só ajusta o que mudou), preservando o histórico.

---

## Quem são as "peças" do sistema

- **Aluno:** quem faz o estágio. Tem uma **ordem de prioridade** (definida pela
  coordenação) que decide quem é alocado primeiro quando as vagas são disputadas.
- **Área:** cada estágio do curso (Audiologia I, Voz, Motricidade Orofacial, etc.).
  Cada área exige uma **carga horária** para ser concluída.
- **Local:** onde o estágio acontece, ou seja, uma unidade e um cenário (hospital,
  UBS, clínica-escola…), com dia, turno, horário e um **número de vagas**.
- **Docente:** o professor da UFCSPA responsável pelo local.
- **Preceptor:** a(o) fonoaudióloga(o) **de campo**, responsável pelo local mas que
  **não é da UFCSPA** (ver a seção "Presença de docente ou preceptor").
- **Calendário:** feriados, eventos acadêmicos, férias/licenças e fechamentos de
  local, que o sistema respeita ao montar a escala.

---

## As fases: 5º semestre e 6º/7º

No mesmo ano convivem dois grupos de alunos, com regras diferentes:

- **5º semestre:** cursa **somente o Estágio de Audiologia I**.
- **6º/7º semestre:** cursa **as demais áreas**.

**Audiologia I é pré-requisito:** um aluno só faz os estágios de 6º/7º depois de
**concluir Audiologia I**. Na prática, todo aluno de 6º/7º já chega com Audiologia I
concluída (fez no 5º semestre).

**O aluno só cursa o que falta.** Se ele já concluiu algumas áreas em anos anteriores,
essas áreas já entram como "concluídas" e o sistema **planeja apenas as que faltam**.

### Carga horária de cada área

| Área | Fase | Carga |
|---|---|---|
| Audiologia I | 5º | 60h |
| Motricidade Orofacial | 6º/7º | 120h |
| Linguagem Infantil | 6º/7º | 160h |
| Saúde Coletiva | 6º/7º | 160h |
| Audiologia II | 6º/7º | 120h |
| LAD (Linguagem do Adulto/Idoso) | 6º/7º | 80h |
| Voz | 6º/7º | 80h |
| Hospitalar Pediatria | 6º/7º | 50h *(a confirmar)* |
| Hospitalar Adulto | 6º/7º | 60h *(a confirmar)* |
| Hospitalar Neonatologia | 6º/7º | 50h *(a confirmar)* |

> O Estágio Hospitalar aparece na matriz como **um único de 160h**, mas na prática se
> divide em 3 cenários. A divisão 50/60/50 é **provisória** e precisa ser confirmada.

---

## Matrícula: quem cursa o quê

A coordenação **matricula** cada aluno nas áreas que ele vai cursar. Isso é **flexível**:

- Pode matricular o aluno em **todas as áreas de uma vez** ou em **algumas agora e o
  resto depois**.
- Pode matricular **no começo do ano** ou **no meio do ciclo**. Nesse segundo caso, o
  aluno entra na fila e é encaixado num grupo futuro (ver "Grupos" e "Fila de espera").
- As áreas em que o aluno não couber de imediato numa vaga ficam **aguardando** e
  entram assim que uma vaga abre.

---

## Como o sistema monta a escala

Ao mandar **gerar a escala**, o sistema percorre os alunos **por ordem de prioridade**
e, para cada um, tenta encaixá-lo nos estágios que ele cursa. Ao escolher um local, ele
respeita **todas** estas regras ao mesmo tempo:

- **Vagas do local:** cada local tem um limite de alunos simultâneos.
- **Sem choque de horário:** o aluno não pode ter dois estágios no mesmo dia e turno,
  e há um **intervalo mínimo de 2h** entre áreas no mesmo dia.
- **Restrições do aluno:** se a coordenação bloqueou certos locais para aquele aluno
  (ver abaixo), ele não é colocado neles.
- **Limite de 30 horas por semana:** o sistema **não sobrecarrega** o aluno, pois a
  soma dos estágios dele **não passa de 30h semanais**.
- **Calendário:** feriados, eventos que bloqueiam, férias/licenças e fechamentos de
  local são descontados das datas.

Se, respeitando tudo isso, **não houver vaga possível** para o aluno numa área, ele
fica **aguardando na fila**, e o sistema mostra **o motivo** (sem vaga, choque de
horário, restrição de local, ou limite de 30h).

### Restrições de local do aluno

Por padrão, **todo aluno pode ir a qualquer local**. Mas alguns alunos têm **condições
especiais** e **não podem** frequentar determinados locais. A coordenação, no cadastro
do aluno, **desmarca** os locais em que ele não pode entrar (pode desmarcar um local ou
uma área inteira). O aluno **continua cursando a área**, só que **em outro local** dela.

> Se a coordenação desmarcar **todos** os locais de uma área que o aluno cursa, o
> sistema **avisa e não deixa salvar**. É preciso liberar pelo menos um local ou
> tirar a matrícula daquela área.

---

## Grupos (as "levas" de alunos)

A coordenação pensa os alunos em **grupos**. Um local com 4 vagas recebe **até 4 alunos
que entram e concluem juntos**, e isso é um **grupo** (uma "leva").

- O **Grupo 1** é quem está no local **agora**.
- Quando o Grupo 1 termina e **libera as vagas**, entra o **Grupo 2**, e assim por
  diante. O sistema **projeta esses próximos grupos**, mostrando **quando cada um deve
  entrar**, com base na previsão de conclusão do grupo anterior.
- Quem entra em cada próximo grupo sai da **fila**, por ordem de prioridade.

> Os próximos grupos são **uma previsão** (uma estimativa), não a escala definitiva.
> Eles se confirmam quando o sistema regera a escala.

### Passagem de grupo

Alguns locais têm **passagem de grupo**: o **último encontro de um grupo é o primeiro
do próximo**. Os dois grupos se encontram por **1 dia**, para quem está saindo
**orientar quem está entrando**. A coordenação marca essa opção no cadastro do local,
e o sistema mostra esse **dia de passagem** na visão por campo.

---

## Fila de espera e previsão de entrada

Nem todo aluno cabe de imediato, e os que sobram ficam na **fila de espera** daquela
área, **por ordem de prioridade**. Como o sistema sabe a **previsão de conclusão** de
quem está alocado, ele consegue responder perguntas como:

- *"Quando vai abrir vaga neste local?"* Quando o grupo atual concluir.
- *"Quando o aluno X, que está esperando, vai poder começar?"* Na próxima vaga que
  abrir, seguindo a prioridade.

Se a entrada de um aluno num grupo esbarrar num **choque de horário** com outro estágio
dele, o sistema avisa a dependência. Por exemplo: *"entra assim que concluir Voz
(previsto para 15/09)"*.

---

## Presença de docente OU preceptor (quando o estágio acontece)

Cada local tem um **docente** e, muitas vezes, um **preceptor de campo**. O preceptor é
uma(um) fonoaudióloga(o) **de fora da UFCSPA**, responsável por aquele local. Um mesmo
preceptor pode responder por **vários locais**, e um professor também pode atuar como
preceptor de um local.

**A regra do encontro:** para o estágio acontecer num dia, **basta que um dos dois esteja
presente**, o docente **ou** o preceptor.

- Se o professor está de férias, mas o preceptor está lá, **o estágio acontece**.
- O encontro **só é suspenso** se **os dois** estiverem ausentes no mesmo dia. Nesse
  caso, o sistema empurra o encontro para uma data livre.

Quando o local não tem preceptor separado, o **docente** é o único responsável, e se
ele falta, o encontro é remarcado.

---

## Ausências e imprevistos

- **Férias e licenças (afastamentos):** registrados por período, para **docentes e
  preceptores**. O sistema só suspende encontros nas datas em que **docente e preceptor
  faltam juntos** (ver a seção acima).
- **Local temporariamente fechado:** os encontros naquelas datas são **remarcados**
  para depois.
- **Eventos do calendário** (feriados, semana acadêmica, reuniões): podem **bloquear**
  o estágio ou não. Por exemplo, atividades de **Linguagem têm precedência e não
  bloqueiam**, e isso é configurável evento a evento, sem depender de programação.
- **Notificações por e-mail:** docentes, preceptores e alunos têm **e-mail** cadastrado
  para receber avisos do sistema. Como o preceptor é externo (sem login da UFCSPA), a
  conta dele é criada a partir do **e-mail**.

---

## Encontros, progresso e conclusão

- Cada estágio tem um **número de encontros** previsto (vindo do espelho).
- Conforme as **datas passam**, cada encontro já decorrido é contado como **feito**
  (presença assumida). O contador vai de "0 de N" até "N de N".
- Quando os encontros feitos **atingem o total**, a área é **concluída
  automaticamente**, o aluno é aprovado nela e a **vaga é liberada** para o próximo da
  fila. Não há marcação manual de conclusão.
- **Ajuste pontual (falta ou reforço):** como não há controle de presença, o professor
  pode, por exceção, **descontar 1 encontro** (falta) ou **conceder 1 encontro**
  (reforço) de um aluno. É um ajuste de contador, registrado para acompanhamento.
- **Alerta de risco:** se, no ritmo atual, a conclusão de um aluno cair **depois do fim
  do ano**, o sistema o marca **em risco**, para a coordenação agir a tempo.

---

## Mudanças no meio do ano

O ano de estágios é vivo. Quando algo muda, o sistema **não refaz a escala sozinho**.
Ele **sinaliza** que a escala está desatualizada e a coordenação decide **remanejar**.

- **Matricular um aluno no meio do ciclo:** ele entra na fila e é encaixado num grupo
  futuro, conforme prioridade e previsão de vaga.
- **Interromper um estágio:** por motivo extraordinário (ex.: saúde), a coordenação
  pode **interromper** uma área de um aluno. A vaga é **liberada** para a fila, a área
  fica **pendente** e o aluno a **refaz no ano seguinte**. Isso é diferente de
  "excluir aluno", que serve só para corrigir um cadastro errado.
- **Remanejar:** ao clicar em remanejar, o sistema mostra **quais alunos e encontros
  serão afetados** antes de confirmar, e recalcula **apenas o necessário**. Ele **nunca
  mexe** no que já passou nem no que a coordenação **travou** manualmente.

---

## Ajustar a escala na mão

A escala que o sistema monta é uma **sugestão**. Nem sempre o resultado automático é
exatamente o que a coordenação quer, então dá para **acertar na mão**:

- **Mover** um aluno de um local para outro da mesma área.
- **Encaixar** um aluno numa vaga específica.
- **Tirar** um aluno de um local (a vaga é liberada).
- Cada ajuste feito à mão fica **travado**, então numa futura remontagem o sistema
  **respeita** a sua decisão e só mexe no resto.
- Se um ajuste ferir uma regra (vaga cheia, passar de 30h, choque de horário, local
  restrito ao aluno), o sistema **avisa**, mas deixa a coordenação **decidir**.

Junto disso vem o atalho **"concluir grupo"**: em vez de fechar aluno por aluno, a
coordenação conclui a leva atual de um local de uma vez, **libera as vagas** e **senta
a próxima turma** nas vagas abertas, começando de agora. É assim que se **dá sequência
de uma turma para a outra** no mesmo local.

Há também o caminho **aluno por aluno**: pelo ajuste de encontros (falta ou reforço),
a coordenação completa os encontros de um aluno até o total e aquela área dele conclui.
"Concluir grupo" é só o atalho que faz isso para a leva inteira de uma vez.

---

## Encerramento e histórico

Ao encerrar o ano, o sistema grava uma **foto** de cada aluno: as áreas que ele cursou,
as horas cumpridas e as datas de conclusão. Cada aluno fica marcado como **ciclo
completo** ou **pendente**. Esse registro **nunca muda**, mesmo que cadastros sejam
editados depois. É a memória do ano.

---

## Pontos a confirmar com a coordenação

- [ ] A **carga horária dos estágios hospitalares** (Pediatria, Adulto, Neonatologia):
      a divisão 50/60/50 é oficial?
- [ ] O **limite de 30h por semana** por aluno está correto e vale para todos?
- [ ] A regra "o encontro só cai quando **docente e preceptor** faltam juntos" vale
      para todos os locais?
- [ ] **Passagem de grupo:** quais locais realmente têm esse dia de sobreposição?
- [ ] **Restrições de local:** só a coordenação define? Precisa registrar o motivo?
- [ ] A **presença assumida** (sem controle de frequência) continua valendo, ou o
      controle de presença entra em uma etapa futura?
- [ ] Está claro que os **próximos grupos e a fila são uma previsão**, não a escala
      final?
- [ ] Falta alguma regra do curso que a coordenação conhece e não está descrita aqui?

---

*Este guia descreve o comportamento do sistema em linguagem do dia a dia. A
especificação detalhada, para a equipe técnica, está nos demais documentos do projeto.*
