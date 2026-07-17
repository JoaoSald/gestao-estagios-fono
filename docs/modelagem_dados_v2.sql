-- ============================================================
-- Sistema de Gestão de Estágios — Fonoaudiologia UFCSPA
-- DDL PostgreSQL — VERSÃO 2  (companion do modelagem_dados_v2.dbml)
-- Gerado como registro para a implementação em FastAPI.
--
-- ⚠️ SNAPSHOT HISTÓRICO — NÃO É A FONTE DE VERDADE DO SCHEMA.
--   O schema real é dono do Alembic (app/models/ + alembic/versions/).
--   Este arquivo é PRÉ-reestruturação e está defasado: aqui status_matricula é
--   só em_andamento/concluida (o real tem também interrompida e incompleta),
--   falta grupo_alunos.fixado, a fase_area é a antiga (5/6_7 vs 7/9_10) e a nota
--   de intervalo (1h30) foi atualizada para 2h entre áreas no mesmo dia.
--   Schema atual = migrations Alembic (última: f3b8c1d4e6a2) + docs/REGRAS_MOTOR_ESCALA.md.
--
-- REGRAS DE NEGÓCIO (v2):
--   1. Fase: alunos do 5º semestre = MINI-CICLO (só Audiologia I);
--      6º/7º cursam as demais áreas. Convivem no mesmo ciclo.
--   2. Audiologia I é PRÉ-REQUISITO BLOQUEANTE das áreas de 6/7
--      (areas.pre_requisito = true). Aplicado no motor de alocação.
--   3. Carry-forward: matrícula pode nascer com status='concluida'
--      (área cursada antes — ex.: Audiologia I dos alunos de 6/7).
--      O motor só aloca as 'em_andamento'.
--   4. As 3 áreas Hospitalares (Ped+Adulto+Neo) somam 160h.
--   5. COBERTURA DO LOCAL: cada local tem um docente e, opcional, um
--      PRECEPTOR de campo (externo OU um docente — ref polimórfica).
--      O encontro só cai quando docente E preceptor estão afastados no
--      mesmo dia. Preceptores são externos à UFCSPA (conta = e-mail).
--      Docentes, preceptores e alunos têm e-mail p/ notificações.
-- ============================================================

-- ---------- ENUMS ----------
CREATE TYPE turno_tipo        AS ENUM ('manha', 'tarde', 'integral', 'noite');
CREATE TYPE dia_semana_tipo   AS ENUM ('segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo');
CREATE TYPE fase_area         AS ENUM ('7', '9_10');
CREATE TYPE status_ciclo      AS ENUM ('rascunho', 'em_andamento', 'encerrado');
CREATE TYPE status_matricula  AS ENUM ('em_andamento', 'concluida');
CREATE TYPE status_alocacao   AS ENUM ('ativa', 'concluida', 'cancelada');
CREATE TYPE status_sessao     AS ENUM ('prevista', 'cumprida', 'remanejada', 'cancelada');
CREATE TYPE status_grupo      AS ENUM ('em_andamento', 'previsto');
CREATE TYPE tipo_afastamento  AS ENUM ('ferias', 'licenca', 'outro');
CREATE TYPE tipo_evento       AS ENUM ('academico', 'feriado', 'reuniao', 'recesso', 'outro');
CREATE TYPE origem_evento     AS ENUM ('manual', 'google', 'api_feriados');
CREATE TYPE tipo_atividade    AS ENUM ('ciclo', 'edicao', 'remanejo', 'sync');
CREATE TYPE situacao_historico AS ENUM ('ciclo_completo', 'pendente');
CREATE TYPE perfil_usuario    AS ENUM ('administrador', 'coordenacao', 'consulta');

-- ============================================================
-- CICLO  (agregador + máquina de estados)
-- ============================================================
CREATE TABLE ciclos (
  id                    SERIAL PRIMARY KEY,
  data_inicio           DATE          NOT NULL,
  data_fim              DATE          NOT NULL,
  status                status_ciclo  NOT NULL DEFAULT 'rascunho',
  passo_bootstrap       INT,
  escala_desatualizada  BOOLEAN       NOT NULL DEFAULT false,
  criado_em             TIMESTAMP,
  encerrado_em          TIMESTAMP,
  CONSTRAINT ck_ciclo_datas CHECK (data_fim > data_inicio)
);
-- INVARIANTE (nível de aplicação): no máximo UM ciclo com status
-- 'rascunho' OU 'em_andamento' por vez. Enforce no service layer do FastAPI
-- (ou via trigger dedicada) — índice de expressão constante não é portável.
COMMENT ON TABLE ciclos IS 'Espinha dorsal da orquestração; o estado decide a tela. No máximo um ciclo rascunho/em_andamento por vez (invariante de aplicação).';

-- ============================================================
-- CATÁLOGOS PERMANENTES (atravessam ciclos)
-- ============================================================
CREATE TABLE areas (
  id             SERIAL PRIMARY KEY,
  nome           VARCHAR      NOT NULL UNIQUE,
  cor            VARCHAR(7),
  carga_exigida  INT          NOT NULL,
  fase           fase_area    NOT NULL DEFAULT '9_10',
  pre_requisito  BOOLEAN      NOT NULL DEFAULT false,
  -- Área COMPOSTA (container, ex.: Audiologia II, Hospitalar): não é matriculável
  -- nem alocável (sem locais). O aluno cursa as SUB-ÁREAS (leaf).
  composta       BOOLEAN      NOT NULL DEFAULT false,
  -- Sub-área de uma composta: aponta para a área-mãe. Simples/mãe = NULL. A CH da
  -- mãe = soma das CHs das sub-áreas; matrícula e conclusão são POR SUB-ÁREA.
  area_mae_id    INT          REFERENCES areas(id),
  CONSTRAINT ck_area_carga CHECK (carga_exigida > 0)
);
-- No máximo UMA área pré-requisito (Audiologia I):
CREATE UNIQUE INDEX uq_area_prereq ON areas (pre_requisito) WHERE pre_requisito;
COMMENT ON COLUMN areas.pre_requisito IS 'True só em Audiologia I (fase 7): responsabilidade compartilhada p/ as áreas de 9/10 (não bloqueia no motor; a coordenação confere).';
COMMENT ON COLUMN areas.fase IS 'Fase do curso: 7 (mini-ciclo, só Audiologia I) ou 9_10 (demais).';
COMMENT ON COLUMN areas.composta IS 'Área-mãe/container (Audiologia II, Hospitalar): não matriculável/alocável; o aluno cursa as sub-áreas.';
COMMENT ON COLUMN areas.area_mae_id IS 'Sub-área: FK para a área-mãe composta. Área simples ou mãe = NULL.';

CREATE TABLE docentes (
  id     SERIAL PRIMARY KEY,
  nome   VARCHAR   NOT NULL UNIQUE,
  email  VARCHAR,
  ativo  BOOLEAN   NOT NULL DEFAULT true
);
COMMENT ON COLUMN docentes.ativo IS 'Desligar sem apagar histórico; desligar em andamento dispara remanejo.';
COMMENT ON COLUMN docentes.email IS 'Login institucional UFCSPA + destino das notificações.';

-- Preceptores: responsáveis de campo, EXTERNOS à UFCSPA. Sem login
-- institucional — a conta é o e-mail (por isso NOT NULL). Catálogo permanente;
-- 1 preceptor ↔ N locais.
CREATE TABLE preceptores (
  id     SERIAL PRIMARY KEY,
  nome   VARCHAR   NOT NULL,
  email  VARCHAR   NOT NULL,
  ativo  BOOLEAN   NOT NULL DEFAULT true
);
COMMENT ON TABLE preceptores IS 'Fonoaudiólogas(os) de campo, externos à UFCSPA. O responsável de campo de um local pode ser um preceptor (aqui) OU um docente (ver locais.preceptor_tipo).';

-- ============================================================
-- ALUNOS (por ciclo) + matrículas por área
-- ============================================================
CREATE TABLE alunos (
  id           SERIAL PRIMARY KEY,
  ciclo_id     INT      NOT NULL REFERENCES ciclos(id),
  nome         VARCHAR  NOT NULL,
  matricula    VARCHAR  NOT NULL,
  email        VARCHAR,
  semestre     INT,
  ordenamento  INT      NOT NULL,
  prioridade   BOOLEAN  NOT NULL DEFAULT false,
  criado_em    TIMESTAMP,
  CONSTRAINT uq_aluno_ciclo_matricula UNIQUE (ciclo_id, matricula)
);
CREATE INDEX idx_alunos_ordenamento ON alunos (ordenamento);
COMMENT ON COLUMN alunos.semestre IS '<=5 => fase 5 (mini-ciclo Audiologia I); >=6 => fase 6/7.';
COMMENT ON COLUMN alunos.ordenamento IS 'Ordem de alocacao — menor = maior prioridade. DERIVADA (AR-8): por fase, alunos com prioridade=true primeiro, depois por matricula. Nao e mais ordenacao manual.';
COMMENT ON COLUMN alunos.prioridade IS 'AR-8: marcado no bootstrap p/ POSICIONAR o aluno a mao na Montagem dos grupos. O motor honra a colocacao (pin) e preenche o resto (prioritarios nao-colocados -> depois por matricula).';

CREATE TABLE matriculas (
  id                       SERIAL PRIMARY KEY,
  aluno_id                 INT               NOT NULL REFERENCES alunos(id),
  area_id                  INT               NOT NULL REFERENCES areas(id),
  data_matricula           DATE,
  status                   status_matricula  NOT NULL DEFAULT 'em_andamento',
  data_conclusao_prevista  DATE,
  data_conclusao           DATE,
  CONSTRAINT uq_matricula_aluno_area UNIQUE (aluno_id, area_id)
);
COMMENT ON TABLE matriculas IS 'O QUE o aluno cursa. CARRY-FORWARD: pode nascer com status=concluida (área cursada antes). PRÉ-REQUISITO: o motor não aloca área de 6/7 sem a área pre_requisito do aluno concluída.';

-- ============================================================
-- LOCAIS DE ESTÁGIO
-- ============================================================
CREATE TABLE locais (
  id             SERIAL PRIMARY KEY,
  ciclo_id       INT               NOT NULL REFERENCES ciclos(id),
  area_id        INT               NOT NULL REFERENCES areas(id),
  unidade        VARCHAR,
  campo          VARCHAR           NOT NULL,
  docente_id     INT                        REFERENCES docentes(id), -- AR-7: NULLABLE (o slot nasce sem docente; atribuído em Configurações de campo). Migration 9fd4120b1555 (aplicada).
  preceptor_tipo VARCHAR,
  preceptor_id   INT,
  dia_semana     dia_semana_tipo   NOT NULL,
  turno          turno_tipo        NOT NULL,
  hora_inicio    TIME              NOT NULL,
  hora_fim       TIME              NOT NULL,
  capacidade        INT            NOT NULL,
  carga_horaria     INT            NOT NULL,
  horas_sessao      DOUBLE PRECISION,
  numero_encontros  INT            NOT NULL,
  passagem_grupo    BOOLEAN        NOT NULL DEFAULT false,
  ativo             BOOLEAN        NOT NULL DEFAULT true,
  CONSTRAINT ck_local_capacidade CHECK (capacidade > 0),
  CONSTRAINT ck_local_horas CHECK (hora_fim > hora_inicio),
  -- Preceptor de campo é FK POLIMÓRFICA (resolvida no app): preceptor_tipo diz
  -- em qual tabela preceptor_id aponta. Ambos nulos = sem preceptor separado.
  CONSTRAINT ck_local_preceptor CHECK (
    (preceptor_tipo IS NULL AND preceptor_id IS NULL)
    OR (preceptor_tipo IN ('externo', 'docente') AND preceptor_id IS NOT NULL)
  )
);
COMMENT ON COLUMN locais.numero_encontros IS 'Nº de encontros do cenário = teto(carga_horaria / horas_sessao); TOTAL fixo do contador; o motor agenda exatamente esse nº de sessões.';
COMMENT ON COLUMN locais.horas_sessao IS 'Horas REAIS de cada encontro (desconta almoço no integral). Base do numero_encontros e do teto de 30h/semana.';
COMMENT ON COLUMN locais.passagem_grupo IS 'PASSAGEM DE GRUPO: true = último encontro de um grupo é o primeiro do próximo (1 dia de sobreposição). Na projeção de grupos, a onda seguinte começa no último dia da anterior; false = começa depois.';
COMMENT ON COLUMN locais.preceptor_tipo IS 'Tipo do preceptor de campo: externo (ref preceptores) | docente (ref docentes) | null (só o docente responde). FK polimórfica resolvida na aplicação.';
COMMENT ON COLUMN locais.unidade IS 'Unidade concedente: SMS, Santa Casa (HSCL/HCSA), GHC, UFCSPA, Frei Pacífico, Rádio Guaíba…';
COMMENT ON COLUMN locais.dia_semana IS 'Modelo SLOT: 1 local = 1 (campo+dia+turno). Um campo pode ter N slots — dias e/ou turnos diferentes, inclusive o MESMO dia em turnos distintos (ex.: segunda manhã + segunda tarde = 2 grupos) — que rodam em PARALELO. Cada slot tem seus proprios responsaveis: docente_id (obrigatorio) + preceptor (opcional). Criado no passo Areas e Locais; responsaveis definidos no passo Configuracoes de campo.';

CREATE TABLE indisponibilidades_local (
  id           SERIAL PRIMARY KEY,
  local_id     INT      NOT NULL REFERENCES locais(id),
  motivo       VARCHAR,
  data_inicio  DATE     NOT NULL,
  data_fim     DATE     NOT NULL,
  CONSTRAINT ck_indisp_datas CHECK (data_fim >= data_inicio)
);

-- Restrições de local do aluno (BLOCKLIST). Ausência de linha = disponível
-- (padrão). Cada linha é uma exceção: local que o aluno NÃO pode frequentar.
-- Criada aqui (depois de alunos e locais) por causa das FKs.
CREATE TABLE restricoes_aluno_local (
  id        SERIAL PRIMARY KEY,
  aluno_id  INT  NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
  local_id  INT  NOT NULL REFERENCES locais(id) ON DELETE CASCADE,
  CONSTRAINT uq_restricao_aluno_local UNIQUE (aluno_id, local_id)
);
COMMENT ON TABLE restricoes_aluno_local IS 'Blocklist aluno × local (por LOCAL). O motor pula esses locais ao alocar o aluno; ele segue cursando a área em outro local liberado. Validação de aplicação: não deixar área matriculada em_andamento sem nenhum local liberado.';

-- ============================================================
-- SAÍDA DO MOTOR  (matriculas=O QUE · alocacoes=ONDE · sessoes=QUANDO)
-- ============================================================
CREATE TABLE alocacoes (
  id                 SERIAL PRIMARY KEY,
  aluno_id           INT              NOT NULL REFERENCES alunos(id),
  local_id           INT              NOT NULL REFERENCES locais(id),
  matricula_id       INT              NOT NULL REFERENCES matriculas(id),
  data_inicio        DATE             NOT NULL,
  data_fim_prevista  DATE             NOT NULL,
  travada            BOOLEAN          NOT NULL DEFAULT false,
  ajuste_encontros   INT              NOT NULL DEFAULT 0,
  status             status_alocacao  NOT NULL DEFAULT 'ativa',
  CONSTRAINT uq_alocacao_aluno_local UNIQUE (aluno_id, local_id)
);
COMMENT ON COLUMN alocacoes.travada IS 'Trava manual: o motor nunca mexe numa alocação travada.';
COMMENT ON COLUMN alocacoes.ajuste_encontros IS 'Ajuste manual do professor no contador de encontros feitos: +1 reforço, -1 falta.';

CREATE TABLE sessoes (
  id           SERIAL PRIMARY KEY,
  alocacao_id  INT             NOT NULL REFERENCES alocacoes(id),
  data         DATE            NOT NULL,
  hora_inicio  TIME,
  hora_fim     TIME,
  horas        NUMERIC(6,2),
  status       status_sessao   NOT NULL DEFAULT 'prevista'
);
CREATE INDEX idx_sessao_alocacao_data ON sessoes (alocacao_id, data);
COMMENT ON TABLE sessoes IS 'A menor unidade da escala = o ENCONTRO. O motor gera exatamente locais.numero_encontros sessões. Contador derivado: total = locais.numero_encontros; feitos = cumpridas + alocacoes.ajuste_encontros (limitado a [0,total]).';

-- ============================================================
-- GRUPOS (ondas por local): grupo atual (onda 1) + previstos (cascata da fila).
-- Materializados; regerados a cada geração/remanejo. PROJEÇÃO até o motor confirmar.
-- ============================================================
CREATE TABLE grupos (
  id           SERIAL PRIMARY KEY,
  ciclo_id     INT           NOT NULL REFERENCES ciclos(id) ON DELETE CASCADE,
  local_id     INT           NOT NULL REFERENCES locais(id) ON DELETE CASCADE,
  area_id      INT           NOT NULL REFERENCES areas(id),
  onda         INT           NOT NULL,
  status       status_grupo  NOT NULL,
  data_inicio  DATE          NOT NULL,
  data_fim     DATE          NOT NULL
);
COMMENT ON TABLE grupos IS 'Uma onda de alunos ocupando um local numa janela. Capacidade do local = tamanho do grupo. onda 1 = atual; 2,3… = previstos (cada um começa quando a onda anterior do local conclui).';

CREATE TABLE grupo_alunos (
  id        SERIAL PRIMARY KEY,
  grupo_id  INT      NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
  aluno_id  INT      NOT NULL REFERENCES alunos(id) ON DELETE CASCADE,
  aviso     VARCHAR,
  CONSTRAINT uq_grupo_aluno UNIQUE (grupo_id, aluno_id)
);
COMMENT ON COLUMN grupo_alunos.aviso IS 'Dependência/conflito na projeção (ex.: "entra ao concluir Voz (previsto 15/09)"). Nulo se entra sem conflito.';

-- ============================================================
-- CALENDÁRIO INSTITUCIONAL
-- ============================================================
CREATE TABLE afastamentos (
  id            SERIAL PRIMARY KEY,
  ciclo_id      INT               REFERENCES ciclos(id),
  docente_id    INT               REFERENCES docentes(id),
  preceptor_id  INT               REFERENCES preceptores(id),
  tipo          tipo_afastamento  NOT NULL DEFAULT 'ferias',
  motivo        VARCHAR,
  data_inicio   DATE              NOT NULL,
  data_retorno  DATE              NOT NULL,
  criado_em     TIMESTAMP,
  CONSTRAINT ck_afast_datas CHECK (data_retorno >= data_inicio),
  -- Cada afastamento é de UMA pessoa: docente OU preceptor (exatamente um).
  CONSTRAINT ck_afast_pessoa CHECK ((docente_id IS NOT NULL) <> (preceptor_id IS NOT NULL))
);
COMMENT ON TABLE afastamentos IS 'Ausências de docentes OU preceptores. Quando o preceptor de um local é um docente, a ausência dele é um afastamento de docente.';

CREATE TABLE eventos (
  id                SERIAL PRIMARY KEY,
  ciclo_id          INT             NOT NULL REFERENCES ciclos(id),
  nome              VARCHAR         NOT NULL,
  tipo              tipo_evento     NOT NULL,
  origem            origem_evento   NOT NULL DEFAULT 'manual',
  data_inicio       DATE            NOT NULL,
  data_fim          DATE            NOT NULL,
  bloqueia_estagio  BOOLEAN         NOT NULL DEFAULT true,
  google_event_id   VARCHAR,
  CONSTRAINT ck_evento_datas CHECK (data_fim >= data_inicio),
  CONSTRAINT uq_evento_ciclo_nome_data UNIQUE (ciclo_id, nome, data_inicio)
);
COMMENT ON COLUMN eventos.bloqueia_estagio IS 'Regra "evento de Linguagem não bloqueia" vira atributo, sem hardcode.';

-- ============================================================
-- OPERAÇÃO
-- ============================================================
CREATE TABLE fila_remanejo (
  id        SERIAL PRIMARY KEY,
  ciclo_id  INT      NOT NULL REFERENCES ciclos(id),
  quando    DATE     NOT NULL,
  texto     VARCHAR  NOT NULL
);

CREATE TABLE atividade (
  id        SERIAL PRIMARY KEY,
  ciclo_id  INT              NOT NULL REFERENCES ciclos(id),
  quando    DATE             NOT NULL,
  texto     VARCHAR          NOT NULL,
  tipo      tipo_atividade   NOT NULL DEFAULT 'edicao'
);

-- ============================================================
-- HISTÓRICO  (snapshot denormalizado — o passado não muda)
-- ============================================================
CREATE TABLE historico (
  id                   SERIAL PRIMARY KEY,
  ciclo_id             INT                 NOT NULL REFERENCES ciclos(id),
  ano                  INT                 NOT NULL,
  aluno_nome           VARCHAR             NOT NULL,
  matricula            VARCHAR,
  areas                JSONB,
  carga_horaria_total  INT,
  situacao             situacao_historico  NOT NULL,
  encerramento         DATE,
  criado_em            TIMESTAMP
);
COMMENT ON COLUMN historico.areas IS 'Array por área da fase: {nome, carga_exigida, horas_cumpridas, data_conclusao}.';
COMMENT ON COLUMN historico.situacao IS 'ciclo_completo (todas as áreas da fase concluídas) | pendente.';

-- ============================================================
-- AUTENTICAÇÃO
-- ============================================================
CREATE TABLE usuarios (
  id          SERIAL PRIMARY KEY,
  nome        VARCHAR          NOT NULL,
  email       VARCHAR          NOT NULL UNIQUE,
  senha_hash  VARCHAR          NOT NULL,
  perfil      perfil_usuario   NOT NULL DEFAULT 'consulta',
  ativo       BOOLEAN          NOT NULL DEFAULT true,
  created_at  TIMESTAMP
);
