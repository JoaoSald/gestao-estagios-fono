# Diff COMPLETO — UI atual × `versao_2` (definitivo em visual e funcionalidade)

> **Regra:** `versao_2` é 100% definitivo em **visual e funcionalidade**. Só a **lógica**
> (regras do motor) estava incompleta. Onde a UI atual difere do `versao_2`, é BUG a corrigir.
> Conclusão honesta: a camada de apresentação atual (FASE 5/8) ficou **genérica** e precisa
> ser **retraduzida 1:1** do `versao_2`, tela por tela. Abaixo, o diff exaustivo.

## 0. Transversais (valem para todas as telas)

| # | `versao_2` (correto) | Atual (bug) |
|---|---|---|
| T1 | **Cor da área** (`area.cor`) em toda parte: `.area-pill` (fundo `cor22`+texto `cor`), `.roster-dot`, `--laccent` nos cards, sessões no calendário. As 14 áreas têm cor. | Badges cinza genéricos; **zero cor de área**. |
| T2 | **Calendário mensal** reutilizável (grade, navegação de mês, chips coloridos, marcos, legenda) — usado em Eventos, Estágios/Por campo e Encontros do aluno. | **Não existe**; sessões viram chips de data. |
| T3 | **Sub-visões `.segmented`** (abas): Estágios (3), Eventos (2). | Ausentes (tela única por rota). |
| T4 | **Busca instantânea client-side** (`wireSearch`) com linha "Nenhum resultado". | Busca via HTMX no servidor (funciona, mas não é o mesmo comportamento/《feel》). |
| T5 | **Formulários = modais** (`window.Forms.*`, ver `forms.js`) com campos específicos por entidade (área com cor+sub-áreas; aluno com matrículas por fase + **restrições de local**; local completo; etc). | Modais genéricos; faltam campos (cor, sub-áreas, restrições) — verificar campo a campo vs `forms.js`. |

## 1. Login (`login.js`)
- **v2:** full-screen **split** — aside teal (logo, hero "Coordene a escala…", logo Saúde Digital, copyright) + card à direita com **e-mail + senha** (olho mostrar/ocultar), "Manter conectado", "Esqueci minha senha" (toast), separador "ou", **"Entrar com Google"** (SVG colorido).
- **Atual:** card central simples, sem split, sem senha/olho, sem Google, sem hero.

## 2. Welcome / sem ciclo (`welcome.js`)
- **v2:** hero "Nenhum ciclo ativo" + **Abrir novo ciclo** (modal, datas pré-preenchidas `ano-03-02`→`ano-12-11`) + **Ver histórico** + card **"Anos anteriores"** (lista por ano: egressos + completos).
- **Atual:** card com form de datas inline; **sem** lista de anos anteriores, **sem** "Ver histórico".

## 3. Painel (`painel.js`)
- **v2:** KPIs (Alunos, Locais ativos, Estágios gerados, Eventos próximos, **Alunos em risco**) · **Ações rápidas que ABREM o formulário (modal)**: Novo aluno/local/evento/afastamento + Remanejar · Próximos eventos · **Progresso da turma** (barra segmentada) · Atividade recente · **banner de vaga livre com fila** + banner de remanejo.
- **Atual:** KPIs e progresso OK; **ações rápidas viram links de navegação** (não abrem modal); **sem banner de vaga livre**.

## 4. Alunos — lista (`alunos.js`)
- **v2:** **duas seções por FASE** ("7º — mini-ciclo" e "9º/10º"), cada uma com "Novo aluno", contagem de matrículas (em andamento/concluídas) e **checkbox prioridade**.
- **Atual:** tabela única plana; sem separação por fase; sem contagem em-andamento/concluídas (só um número).

## 5. Aluno — detalhe (`aluno.js`)
- **v2:** cabeçalho (avatar, fase, **pré-requisito**) · **stat-row** (Áreas concluídas, Carga cumprida %, **Dias restantes**, Situação no prazo/risco) · **cards por área com faixa colorida** (`--laccent`) + barra colorida + "feitos/total · %" + previsão/conclusão/interrupção · **caixa "Por que está em risco"** · botão **Encontros** → **calendário mensal** (modal, só leitura, com eventos bloqueantes) · Interromper por área.
- **Atual:** cards sem cor; stats reduzidos; **sem calendário mensal**; sem caixa de risco.

## 6. Docentes (`docentes.js`)
- **v2:** colunas Nome · E-mail · Status(ativo/**desligado**) · **Locais (count)** · **Afastamentos (count)** · editar.
- **Atual:** Nome · E-mail · Status; **faltam** contagens de locais/afastamentos; status "Inativo" (v2 usa "desligado").

## 7. Preceptores (`preceptores.js`)
- **v2:** igual Docentes (Nome · E-mail · Status · Locais · Afastamentos).
- **Atual:** Nome · E-mail · Status; faltam counts.

## 8. Afastamentos (`afastamentos.js`)
- **v2:** Pessoa(+badge **papel** docente/preceptor) · Tipo(badge) · **Motivo** · Período(+**N dias**) · editar + remover.
- **Atual:** Pessoa · Período · Tipo; **falta** coluna Motivo, contagem de dias e **edição** (desabilitei).

## 9. Locais (`locais.js`)
- **v2:** **Área [pílula colorida]** · Campo + subline **Docente (+preceptor)** · Quando · **Ocupação uso/cap** · Status(ativo + **indisp. badge**) · ações: **Indisponibilidade** + editar + remover.
- **Atual:** Campo · Área(texto) · Dia·Turno · Cap · Encontros; sem cor, sem docente/preceptor, sem ocupação, sem status, **sem indisponibilidade**, sem remover.

## 10. Eventos (`eventos.js`)
- **v2:** **2 abas** (Lista + **Calendário mensal**) · tipo com **leg-dot colorido** (feriado/acadêmico/reunião/recesso) · Origem · Período · badge bloqueia · no calendário, chip colorido por tipo com contorno se bloqueia, clique abre edição.
- **Atual:** só Lista; tipo como texto; **sem calendário**.

## 11. Estágios (`estagios.js`) — **propósito trocado (crítico)**
- **v2:** tela **SÓ de visualização**; título "Estágios · N alocações" + badge **escala atualizada/desatualizada**; **3 abas**:
  - **Por aluno:** tabela (Aluno · **Área pílula** · Campo · Docente · Horário · Sessões · Conclusão prevista); clique → **calendário do aluno** (modal).
  - **Por campo:** seletor de cenário + **calendário mensal** do local + painel (docente, preceptor, horário, período, passagem, vagas, roster com progresso); **ajustes manuais aqui** (mover/remover/**concluir grupo**/adicionar).
  - **Grupos:** ondas por local filtradas por área; trocar aluno / trocar grupo; selo **montado/auto**; CH `h/30h`.
  - **SEM botão "Gerar escala".** Gerar = **bootstrap passo 10**; regerar = **Remanejar**.
- **Atual (errado):** board único de grupos com **botão "Gerar escala"** + mover/remover/adicionar no board. Sem as 3 abas, sem calendário, sem cores.

## 12. Remanejar (`remanejo.js`)
- **v2:** abre o **Painel com um MODAL** por cima — **prévia** do remanejamento **cirúrgico** (o que muda) + **aplicar** (só o afetado; nada nas concluídas). Quando nada pendente: modal "escala atualizada".
- **Atual:** página própria listando a fila + botão que **regera a escala inteira** (não é a prévia cirúrgica).

## 13. Histórico (`historico.js`)
- **v2:** read-only por ciclo/ano (egressos, situação). (Ver `historico.js` para colunas exatas.)
- **Atual:** tabela simples por linha do `historico`. Verificar layout/colunas vs v2.

## 14. Bootstrap (`bootstrap.js`, 10 passos)
- **v2:** stepper clicável (passos já visitados), cada passo com o card estilizado do protótipo; passo 3 **Áreas** (simples/compostas com sub-áreas + **chips coloridos** + edição de sub-áreas) **e** Locais (com resumo de slots paralelos por área); passo 5 config de campo (docente + preceptor por slot, com opção "novo preceptor"); passo 7 Alunos **por fase** com "Novo aluno" que pré-preenche o semestre; passo 9 **Montagem com cores de área** e cabeçalho de slot (encontros/horas/CH sem); passo 10 relatório = **mesma view de Grupos** de Estágios.
- **Atual:** wizard funcional, mas usa as tabelas **genéricas** (sem cores/counts), config de campo simplificada, montagem sem cores, relatório = board próprio (não a view de Grupos).

## 15. Encerrar (`encerrar.js`, 3 etapas)
- **v2:** etapas (Revisão do estado final com KPIs+pendências · Prévia do histórico · Confirmação forte digitando o ano). **Próximo do atual** — conferir textos/estilo.
- **Atual:** implementado; alinhar detalhes visuais.

## Encaminhamento sugerido
Retraduzir 1:1, tela por tela, validando contra o `versao_2`. Prioridade pelo grau de
divergência/uso: **(a) Estágios** (propósito), **(b) cores de área + componente de
calendário** (transversais T1/T2), **(c) Login/Welcome**, **(d) Locais/Eventos/Aluno-detalhe**,
**(e) Docentes/Preceptores/Afastamentos/Alunos-lista**, **(f) Painel/Remanejar**, **(g)
Bootstrap/Encerrar (ajustes visuais)**. Formulários (`forms.js`) verificados campo a campo.
