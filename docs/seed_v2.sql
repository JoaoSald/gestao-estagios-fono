-- ============================================================
-- Sistema de Gestão de Estágios — Fonoaudiologia UFCSPA
-- SEED (catálogos) — VERSÃO 3 (reestruturação: sub-áreas + slot)
-- GERADO de js/data/mock.js (protótipo versao_2, seed v12).
-- DOCENTES/PRECEPTORES atualizados p/ a lista oficial (docs/Nomes e emails_Professores e Supervisores.xlsx, jul/2026):
--   nomes completos + e-mails reais; catálogo recriado 1:1 com a planilha e locais remapeados por pessoa.
-- ciclo 2026 · areas 14 (2 compostas + 6 sub-áreas) · docentes 18 · preceptores 12 · locais (slot, 1 dia).
-- ============================================================
BEGIN;

-- 1. CICLO
INSERT INTO ciclos (id, data_inicio, data_fim, status, escala_desatualizada, criado_em) VALUES
  (1, '2026-03-02', '2026-12-11', 'em_andamento', false, '2026-02-14');

-- 2. AREAS (compostas: composta=true e SEM locais; sub-áreas: area_mae_id aponta p/ a mãe)
INSERT INTO areas (id, nome, cor, carga_exigida, fase, pre_requisito, composta, area_mae_id) VALUES
  (1, 'Audiologia I', '#7c3aed', 60, '7', true, false, NULL),
  (2, 'Motricidade Orofacial', '#ea580c', 120, '9_10', false, false, NULL),
  (3, 'Linguagem Infantil', '#0284c7', 160, '9_10', false, false, NULL),
  (4, 'Saúde Coletiva', '#0d9488', 160, '9_10', false, false, NULL),
  (5, 'LAD — Linguagem do Adulto/Idoso', '#ca8a04', 80, '9_10', false, false, NULL),
  (6, 'Voz', '#db2777', 80, '9_10', false, false, NULL),
  (7, 'Audiologia II', '#9333ea', 110, '9_10', false, true, NULL),
  (8, 'SADT (SA)', '#9333ea', 40, '9_10', false, false, 7),
  (9, 'Ambulatório ORL — TAN', '#9333ea', 10, '9_10', false, false, 7),
  (10, 'AMB. Santa Marta (SM)', '#9333ea', 60, '9_10', false, false, 7),
  (11, 'Hospitalar', '#dc2626', 160, '9_10', false, true, NULL),
  (12, 'Pediatria', '#dc2626', 50, '9_10', false, false, 11),
  (13, 'Adulto', '#e11d48', 60, '9_10', false, false, 11),
  (14, 'Neonatologia', '#f43f5e', 50, '9_10', false, false, 11);

-- 3. DOCENTES  (lista oficial — planilha "Professor", 18 nomes)
INSERT INTO docentes (id, nome, email, ativo) VALUES
  (1,  'Profa. Rafaela Soares Rech',                'rafaela.rech@ufcspa.edu.br',     true),
  (2,  'Profa. Fabiana de Oliveira',                'fabianao@ufcspa.edu.br',         true),
  (3,  'Profa. Isabela Menegotto',                  'isabelam@ufcspa.edu.br',         true),
  (4,  'Profa. Lisiane da Rosa Barbosa',            'lisianeb@ufcspa.edu.br',         true),
  (5,  'Profa. Eveline de Lima Nunes',              'evelinen@ufcspa.edu.br',         true),
  (6,  'Prof. Daniel Lucas Picanço Marchand',       'daniellm@ufcspa.edu.br',         true),
  (7,  'Profa. Andrea Wander Bonamigo',             'andreawb@ufcspa.edu.br',         true),
  (8,  'Profa. Barbara Costa Beber',                'barbaracb@ufcspa.edu.br',        true),
  (9,  'Profa. Mauriceia Cassol',                   'mcassol@ufcspa.edu.br',          true),
  (10, 'Profa. Deisi Cristina Gollo Marques Vidor', 'deisiv@ufcspa.edu.br',           true),
  (11, 'Profa. Marcia Angelica Peter Maahs',        'marciama@ufcspa.edu.br',         true),
  (12, 'Profa. Sheila Tamanini de Almeida',         'sheilat@ufcspa.edu.br',          true),
  (13, 'Profa. Allessandra Fraga da Re',            'alessandraf@ufcspa.edu.br',      true),
  (14, 'Profa. Cristina Loureiro Chaves Soldera',   'cristinalcs@ufcspa.edu.br',      true),
  (15, 'Profa. Letícia Pacheco Ribas',              'leticiapr@ufcspa.edu.br',        true),
  (16, 'Profa. Márcia Salgado Machado',             'marciasm@ufcspa.edu.br',         true),
  (17, 'Profa. Gabriele Donicht',                   'gabriele.donicht@ufcspa.edu.br', true),
  (18, 'Profa. Roberta Freitas Dias',               'roberta.freitas@ufcspa.edu.br',  true);

-- 3b. PRECEPTORES  (lista oficial — planilha "Preceptor", 12 nomes)
INSERT INTO preceptores (id, nome, email, ativo) VALUES
  (1,  'Fga. Andrea G .Tyska',                   'agtyska@gmail.com',                    true),
  (2,  'Fga. Lisiane Gregis',                    'lisi_gregis@hotmail.com',              true),
  (3,  'Fga. Marina Santos',                     'marina.santos@portoalegre.rs.gov.br',  true),
  (4,  'Fga. Michelle Dourado Ramos',            'michelle.ramos@portoalegre.rs.gov.br', true),
  (5,  'Fga. Mariana Feller Gonçalves da Silva', 'mariana.feller@yahoo.com.br',          true),
  (6,  'Fga. Camila de Oliveira Lucas Marques',  'camila.marques@portoalegre.rs.gov.br', true),
  (7,  'Fga. Karini Cunha',                      'karinicunha@gmail.com',                true),
  (8,  'Fga. Fabiane Zanini',                    'fabiane.zanini@hotmail.com',           true),
  (9,  'Fga. Carla Castelli',                    'castellictr@gmail.com',                true),
  (10, 'Fga. Doris',                             'dorisfono@hotmail.com',                true),
  (11, 'Fga. Aline Juliane Romann',              'jaline@ghc.com.br',                    true),
  (12, 'Fga. Mérope Bortolotto Dall''ago',       'merope@portoalegre.rs.gov.br',         true);

-- 4. LOCAIS (modelo SLOT: 1 campo+dia+turno por linha; horas_sessao = horas reais/encontro)
INSERT INTO locais
  (id, ciclo_id, area_id, unidade, campo, docente_id, preceptor_tipo, preceptor_id,
   dia_semana, turno, hora_inicio, hora_fim, horas_sessao, capacidade, carga_horaria, numero_encontros, passagem_grupo, ativo)
VALUES
  -- docente_id / preceptor_id remapeados p/ os novos ids do catálogo oficial.
  -- locais 1-3: preceptor era a docente 'Cibele' (fora da lista) -> sem preceptor (docente responde).
  (1, 1, 1, 'Santa Casa (HSCL)', 'Ambulatório - ORL', 14, NULL, NULL, 'terca', 'manha', '08:00', '12:30', 4.5, 4, 60, 14, false, true),
  (2, 1, 1, 'Santa Casa (HSCL)', 'Ambulatório - ORL', 14, NULL, NULL, 'quinta', 'tarde', '13:30', '18:00', 4.5, 4, 60, 14, false, true),
  (3, 1, 1, 'Santa Casa (HSCL)', 'Ambulatório - ORL', 14, NULL, NULL, 'sexta', 'tarde', '13:30', '18:00', 4.5, 4, 60, 14, false, true),
  (4, 1, 2, 'SMS', 'AMB. IAPI', 13, NULL, NULL, 'segunda', 'tarde', '13:30', '17:30', 4, 4, 120, 30, true, true),
  (5, 1, 2, 'Santa Casa (HCSA)', 'Ambulatório de Especialidades', 14, NULL, NULL, 'terca', 'manha', '08:00', '12:00', 4, 4, 120, 30, false, true),
  (6, 1, 2, 'Santa Casa (HSCL)', 'Ambulatório ORL — Reab. Orofacial', 11, NULL, NULL, 'segunda', 'manha', '08:00', '12:00', 4, 2, 120, 30, false, true),
  -- local 7: preceptor era 'Thiauna Leão' (fora da lista) -> sem preceptor.
  (7, 1, 3, 'Frei Pacífico', 'Clínica', 10, NULL, NULL, 'sexta', 'tarde', '13:30', '17:30', 4, 4, 160, 40, true, true),
  (8, 1, 3, 'Frei Pacífico/LIBRAS', 'Clínica', 10, 'externo', 8, 'terca', 'tarde', '13:30', '17:30', 4, 4, 160, 40, false, true),
  (9, 1, 3, 'Santa Casa (HCSA)', 'Ambulatório de Especialidades', 15, NULL, NULL, 'quarta', 'manha', '08:00', '12:00', 4, 4, 160, 40, false, true),
  (10, 1, 4, 'SMS', 'AMB. IAPI', 1, 'externo', 1, 'terca', 'tarde', '13:30', '17:30', 4, 2, 160, 40, false, true),
  (11, 1, 4, 'SMS', 'AMB. IAPI', 7, NULL, NULL, 'quarta', 'manha', '08:00', '12:00', 4, 2, 160, 40, false, true),
  (12, 1, 4, 'SMS', 'US Nova Brasília', 2, NULL, NULL, 'quarta', 'tarde', '13:30', '17:30', 4, 2, 160, 40, false, true),
  -- locais 13-14: preceptor era 'Fernanda Shutz' (fora da lista) -> sem preceptor.
  (13, 1, 4, 'SMS', 'EESCA NEB', 1, NULL, NULL, 'quarta', 'manha', '08:00', '12:30', 4.5, 2, 160, 36, false, true),
  (14, 1, 4, 'SMS', 'EESCA NEB', 1, NULL, NULL, 'quarta', 'tarde', '13:30', '17:30', 4, 2, 160, 40, false, true),
  (15, 1, 4, 'SMS', 'EESCA Vila Comerciários', 1, 'externo', 12, 'quinta', 'manha', '08:00', '12:00', 4, 1, 160, 40, false, true),
  (16, 1, 4, 'SMS', 'EESCA Camaquã', 1, 'externo', 3, 'quinta', 'manha', '08:00', '12:00', 4, 1, 160, 40, false, true),
  (17, 1, 4, 'SMS', 'EESCA Santa Marta', 1, 'externo', 4, 'terca', 'tarde', '13:30', '17:30', 4, 1, 160, 40, false, true),
  (18, 1, 8, 'Santa Casa (HCSA)', 'SADT (SA)', 16, NULL, NULL, 'segunda', 'manha', '08:00', '12:00', 4, 4, 40, 10, false, true),
  (19, 1, 8, 'Santa Casa (HCSA)', 'SADT (SA)', 16, NULL, NULL, 'sexta', 'manha', '08:00', '12:00', 4, 4, 40, 10, false, true),
  (20, 1, 9, 'Santa Casa (HSCL)', 'Ambulatório ORL — TAN', 16, NULL, NULL, 'terca', 'tarde', '13:00', '16:00', 3, 2, 10, 4, false, true),
  (21, 1, 10, 'SMS', 'AMB. Santa Marta (SM)', 3, 'externo', 6, 'segunda', 'integral', '08:00', '17:00', 8, 4, 60, 8, true, true),
  (22, 1, 10, 'SMS', 'AMB. Santa Marta (SM)', 3, 'externo', 6, 'terca', 'integral', '08:00', '17:00', 8, 4, 60, 8, false, true),
  (23, 1, 5, 'Santa Casa (HSCL)', 'Ambulatório - C', 17, NULL, NULL, 'sexta', 'tarde', '13:00', '17:00', 4, 4, 80, 20, false, true),
  (24, 1, 5, 'UFCSPA', 'Fisioterapia', 8, NULL, NULL, 'quarta', 'manha', '08:00', '12:00', 4, 4, 80, 20, false, true),
  (25, 1, 6, 'Santa Casa (HSCL)', 'Ambulatório - ORL', 9, NULL, NULL, 'sexta', 'tarde', '13:30', '17:30', 4, 4, 80, 20, false, true),
  (26, 1, 6, 'UFCSPA', 'Coral', 6, NULL, NULL, 'terca', 'manha', '08:00', '12:00', 4, 4, 80, 20, false, true),
  (27, 1, 6, 'Rádio Guaíba', 'Rádio', 9, NULL, NULL, 'quinta', 'tarde', '14:00', '18:00', 4, 2, 80, 20, false, true),
  (28, 1, 12, 'Santa Casa (HCSA)', 'U.I - SUS', 4, NULL, NULL, 'terca', 'manha', '08:00', '12:00', 4, 4, 50, 13, false, true),
  (29, 1, 12, 'Santa Casa (HCSA)', 'U.I - SUS', 4, NULL, NULL, 'quarta', 'manha', '08:00', '12:00', 4, 4, 50, 13, false, true),
  (30, 1, 13, 'Santa Casa (HSCL)', '2º Andar - AVC', 5, NULL, NULL, 'segunda', 'manha', '08:00', '12:00', 4, 4, 60, 15, false, true),
  (31, 1, 13, 'Santa Casa (HSCL)', '2º Andar - AVC', 5, NULL, NULL, 'quarta', 'manha', '08:00', '12:00', 4, 4, 60, 15, false, true),
  (32, 1, 13, 'GHC', 'Medicina Interna', 12, 'externo', 7, 'terca', 'manha', '08:00', '12:00', 4, 2, 60, 15, false, true),
  (33, 1, 13, 'GHC', 'Medicina Interna', 12, 'externo', 7, 'quinta', 'manha', '08:00', '12:00', 4, 2, 60, 15, false, true),
  -- local 34: preceptor era 'Cecilia A.' (fora da lista) -> sem preceptor.
  (34, 1, 13, 'GHC', 'Emergência', 12, NULL, NULL, 'quinta', 'tarde', '13:00', '16:00', 3, 2, 60, 20, false, true),
  (35, 1, 13, 'GHC', 'Neurologia', 12, 'externo', 11, 'quinta', 'manha', '08:00', '12:00', 4, 2, 60, 15, false, true),
  (36, 1, 14, 'Santa Casa (HSCL)', 'UTI Neonatal', 12, NULL, NULL, 'terca', 'tarde', '13:00', '16:00', 3, 4, 50, 17, false, true),
  (37, 1, 14, 'Santa Casa (HSCL)', 'UTI Neonatal', 12, NULL, NULL, 'quinta', 'tarde', '13:00', '16:00', 3, 4, 50, 17, false, true);

-- 5. Sequences
SELECT setval(pg_get_serial_sequence('ciclos','id'), (SELECT MAX(id) FROM ciclos));
SELECT setval(pg_get_serial_sequence('areas','id'), (SELECT MAX(id) FROM areas));
SELECT setval(pg_get_serial_sequence('docentes','id'), (SELECT MAX(id) FROM docentes));
SELECT setval(pg_get_serial_sequence('preceptores','id'), (SELECT MAX(id) FROM preceptores));
SELECT setval(pg_get_serial_sequence('locais','id'), (SELECT MAX(id) FROM locais));
COMMIT;
