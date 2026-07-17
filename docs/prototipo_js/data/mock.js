/* ============================================================================
   mock.js — Dados iniciais (seed) do protótipo.
   Áreas, docentes e locais espelham o "ESPELHO GERAL ESTÁGIOS 2026" e a
   carga horária da matriz curricular. Tudo em pt-BR.
   ============================================================================ */
(function () {
  'use strict';

  // ---- PRNG determinístico (para o seed ser reproduzível) -------------------
  let _s = 20260705;
  function rnd() { _s = (_s * 1103515245 + 12345) & 0x7fffffff; return _s / 0x7fffffff; }
  function pick(arr) { return arr[Math.floor(rnd() * arr.length)]; }
  function pickN(arr, n) {
    const c = arr.slice(); const out = [];
    while (out.length < n && c.length) out.push(c.splice(Math.floor(rnd() * c.length), 1)[0]);
    return out;
  }

  // ---- Catálogo fixo de ÁREAS ------------------------------------------------
  //  `fase`: '7' = mini-ciclo do 7º semestre (só Audiologia I) · '9_10' = estágios
  //   do 9º/10º semestre.
  //  `pre_requisito`: Audiologia I precisa estar concluída para cursar as de 9/10.
  //  `area_mae`: quando preenchido, esta área é uma SUB-ÁREA obrigatória de uma área
  //   composta (o aluno precisa cumprir a CH de CADA sub-área para concluir a mãe).
  //   Ex.: Audiologia II = SADT + ORL/TAN + Santa Marta; Hospitalar = Ped + Adu + Neo.
  //   Áreas simples (Voz, Motricidade…) têm area_mae null — o aluno cumpre em qualquer local.
  const areas = [
    { id: 'ar-aud1',     nome: 'Audiologia I',              carga_exigida: 60,  cor: '#7c3aed', fase: '7',    pre_requisito: true, area_mae: null, composta: false },
    { id: 'ar-mo',       nome: 'Motricidade Orofacial',     carga_exigida: 120, cor: '#ea580c', fase: '9_10', area_mae: null, composta: false },
    { id: 'ar-ling-inf', nome: 'Linguagem Infantil',        carga_exigida: 160, cor: '#0284c7', fase: '9_10', area_mae: null, composta: false },
    { id: 'ar-sc',       nome: 'Saúde Coletiva',            carga_exigida: 160, cor: '#0d9488', fase: '9_10', area_mae: null, composta: false },
    { id: 'ar-lad',      nome: 'LAD — Linguagem do Adulto/Idoso', carga_exigida: 80, cor: '#ca8a04', fase: '9_10', area_mae: null, composta: false },
    { id: 'ar-voz',      nome: 'Voz',                       carga_exigida: 80,  cor: '#db2777', fase: '9_10', area_mae: null, composta: false },
    // Audiologia II — COMPOSTA (container): total 110h = SADT 40 + TAN 10 + Santa Marta 60.
    // O container não é matriculável/alocável; o aluno cursa as SUB-ÁREAS (leaf, area_mae=id).
    { id: 'ar-aud2',      nome: 'Audiologia II',            carga_exigida: 110, cor: '#9333ea', fase: '9_10', area_mae: null,      composta: true },
    { id: 'ar-aud2-sadt', nome: 'SADT (SA)',                carga_exigida: 40,  cor: '#9333ea', fase: '9_10', area_mae: 'ar-aud2', composta: false },
    { id: 'ar-aud2-tan',  nome: 'Ambulatório ORL — TAN',    carga_exigida: 10,  cor: '#9333ea', fase: '9_10', area_mae: 'ar-aud2', composta: false },
    { id: 'ar-aud2-sm',   nome: 'AMB. Santa Marta (SM)',    carga_exigida: 60,  cor: '#9333ea', fase: '9_10', area_mae: 'ar-aud2', composta: false },
    // Hospitalar — COMPOSTA (container): total 160h = Pediatria 50 + Adulto 60 + Neonatologia 50.
    { id: 'ar-hosp',     nome: 'Hospitalar',                carga_exigida: 160, cor: '#dc2626', fase: '9_10', area_mae: null,      composta: true },
    { id: 'ar-hosp-ped', nome: 'Pediatria',                 carga_exigida: 50,  cor: '#dc2626', fase: '9_10', area_mae: 'ar-hosp', composta: false },
    { id: 'ar-hosp-adu', nome: 'Adulto',                    carga_exigida: 60,  cor: '#e11d48', fase: '9_10', area_mae: 'ar-hosp', composta: false },
    { id: 'ar-hosp-neo', nome: 'Neonatologia',              carga_exigida: 50,  cor: '#f43f5e', fase: '9_10', area_mae: 'ar-hosp', composta: false },
  ];

  // ---- DOCENTES (permanentes, atravessam ciclos) ---------------------------
  //  Professores responsáveis da UFCSPA. Têm login institucional; o e-mail é
  //  usado para as notificações do sistema. As fonoaudiólogas de campo entram
  //  como PRECEPTORES (catálogo próprio, ver abaixo) — vinculados ao local.
  const docentes = [
    { id: 'dc-alle', nome: 'Profa. Allessandra Fraga da Re',            email: 'alessandraf@ufcspa.edu.br',      ativo: true },
    { id: 'dc-rafa', nome: 'Profa. Rafaela Soares Rech',                email: 'rafaela.rech@ufcspa.edu.br',     ativo: true },
    { id: 'dc-andb', nome: 'Profa. Andrea Wander Bonamigo',             email: 'andreawb@ufcspa.edu.br',         ativo: true },
    { id: 'dc-fabi', nome: 'Profa. Fabiana de Oliveira',                email: 'fabianao@ufcspa.edu.br',         ativo: true },
    { id: 'dc-isab', nome: 'Profa. Isabela Menegotto',                  email: 'isabelam@ufcspa.edu.br',         ativo: true },
    { id: 'dc-deis', nome: 'Profa. Deisi Cristina Gollo Marques Vidor', email: 'deisiv@ufcspa.edu.br',           ativo: true },
    { id: 'dc-gabr', nome: 'Profa. Gabriele Donicht',                   email: 'gabriele.donicht@ufcspa.edu.br', ativo: true },
    { id: 'dc-mama', nome: 'Profa. Marcia Angelica Peter Maahs',        email: 'marciama@ufcspa.edu.br',         ativo: true },
    { id: 'dc-leti', nome: 'Profa. Letícia Pacheco Ribas',              email: 'leticiapr@ufcspa.edu.br',        ativo: true },
    { id: 'dc-maur', nome: 'Profa. Mauriceia Cassol',                   email: 'mcassol@ufcspa.edu.br',          ativo: true },
    { id: 'dc-lisi', nome: 'Profa. Lisiane da Rosa Barbosa',            email: 'lisianeb@ufcspa.edu.br',         ativo: true },
    { id: 'dc-evel', nome: 'Profa. Eveline de Lima Nunes',              email: 'evelinen@ufcspa.edu.br',         ativo: true },
    { id: 'dc-shei', nome: 'Profa. Sheila Tamanini de Almeida',         email: 'sheilat@ufcspa.edu.br',          ativo: true },
    { id: 'dc-cris', nome: 'Profa. Cristina Loureiro Chaves Soldera',   email: 'cristinalcs@ufcspa.edu.br',      ativo: true },
    { id: 'dc-mmac', nome: 'Profa. Márcia Salgado Machado',             email: 'marciasm@ufcspa.edu.br',         ativo: true },
    { id: 'dc-barb', nome: 'Profa. Barbara Costa Beber',                email: 'barbaracb@ufcspa.edu.br',        ativo: true },
    { id: 'dc-dani', nome: 'Prof. Daniel Lucas Picanço Marchand',       email: 'daniellm@ufcspa.edu.br',         ativo: true },
    { id: 'dc-robe', nome: 'Profa. Roberta Freitas Dias',               email: 'roberta.freitas@ufcspa.edu.br',  ativo: true },
  ];

  // ---- PRECEPTORES (permanentes, atravessam ciclos) ------------------------
  //  Fonoaudiólogas(os) de campo — responsáveis pelo local, NÃO são da UFCSPA
  //  e não têm login institucional: a conta é gerada a partir do e-mail.
  //  Um preceptor pode responder por N locais (1 preceptor ↔ N locais).
  //  Regra de cobertura: um local só é prejudicado numa data se TODOS os seus
  //  responsáveis (docente + preceptor) estiverem afastados ao mesmo tempo.
  const preceptores = [
    { id: 'pc-atys', nome: 'Fga. Andrea G .Tyska',                   email: 'agtyska@gmail.com',                    ativo: true },
    { id: 'pc-mero', nome: "Fga. Mérope Bortolotto Dall'ago",        email: 'merope@portoalegre.rs.gov.br',         ativo: true },
    { id: 'pc-msan', nome: 'Fga. Marina Santos',                     email: 'marina.santos@portoalegre.rs.gov.br',  ativo: true },
    { id: 'pc-mich', nome: 'Fga. Michelle Dourado Ramos',            email: 'michelle.ramos@portoalegre.rs.gov.br', ativo: true },
    { id: 'pc-cmar', nome: 'Fga. Camila de Oliveira Lucas Marques',  email: 'camila.marques@portoalegre.rs.gov.br', ativo: true },
    { id: 'pc-fabz', nome: 'Fga. Fabiane Zanini',                    email: 'fabiane.zanini@hotmail.com',           ativo: true },
    { id: 'pc-kmay', nome: 'Fga. Karini Cunha',                      email: 'karinicunha@gmail.com',                ativo: true },
    { id: 'pc-alin', nome: 'Fga. Aline Juliane Romann',              email: 'jaline@ghc.com.br',                    ativo: true },
    { id: 'pc-greg', nome: 'Fga. Lisiane Gregis',                    email: 'lisi_gregis@hotmail.com',              ativo: true },
    { id: 'pc-marf', nome: 'Fga. Mariana Feller Gonçalves da Silva', email: 'mariana.feller@yahoo.com.br',          ativo: true },
    { id: 'pc-carc', nome: 'Fga. Carla Castelli',                    email: 'castellictr@gmail.com',                ativo: true },
    { id: 'pc-dori', nome: 'Fga. Doris',                             email: 'dorisfono@hotmail.com',                ativo: true },
  ];

  // ============================================================================
  //  seedCicloData(cicloId) — devolve as coleções de um ciclo novo.
  // ============================================================================
  function seedCicloData(cicloId) {
    _s = 20260705; // reseta o PRNG para reprodutibilidade

    // ---- LOCAIS (SLOTS: 1 por campo+dia+turno) -----------------------------
    // MODELO NOVO: cada (campo + dia + turno) é um SLOT próprio = 1 grupo que roda
    // EM PARALELO com os outros dias do mesmo campo/área (ex.: Audiologia I terça,
    // quinta e sexta = 3 grupos simultâneos). O aluno faz a área inteira num slot
    // (1×/semana). numero_encontros do slot = teto(CH da área ÷ horas da sessão).
    // L(id, area, unidade, campo, docente, prec, dia, turno, hi, hf, horasSessao, cap)
    //  prec: "<tipo>:<id>" com tipo 'externo' (preceptores) ou 'docente' (docentes),
    //   ou null quando só o docente do local responde.
    function L(id, area_id, unidade, campo, docente_id, prec, dia, turno, hi, hf, horasSessao, cap) {
      let preceptor_id = null, preceptor_tipo = null;
      if (prec) { const p = prec.split(':'); preceptor_tipo = p[0]; preceptor_id = p[1]; }
      const area = areas.find((a) => a.id === area_id);
      const carga = area ? area.carga_exigida : 0;
      return { id, ciclo_id: cicloId, area_id, unidade, campo, docente_id, preceptor_id, preceptor_tipo,
        dia_semana: dia, dias: [dia], turno, hora_inicio: hi, hora_fim: hf, horas_sessao: horasSessao,
        capacidade: cap, carga_horaria: carga, numero_encontros: Math.max(1, Math.ceil(carga / horasSessao)),
        passagem_grupo: false, ativo: true };
    }
    const locais = [
      // Audiologia I (7º) — 3 slots paralelos (terça manhã, quinta tarde, sexta tarde)
      L('lc-a1t', 'ar-aud1',     'Santa Casa (HSCL)',   'Ambulatório - ORL',                 'dc-cris', null, 'terca',  'manha', '08:00', '12:30', 4.5, 4),
      L('lc-a1q', 'ar-aud1',     'Santa Casa (HSCL)',   'Ambulatório - ORL',                 'dc-cris', null, 'quinta', 'tarde', '13:30', '18:00', 4.5, 4),
      L('lc-a1s', 'ar-aud1',     'Santa Casa (HSCL)',   'Ambulatório - ORL',                 'dc-cris', null, 'sexta',  'tarde', '13:30', '18:00', 4.5, 4),
      // Motricidade Orofacial
      L('lc-mo1', 'ar-mo',       'SMS',                 'AMB. IAPI',                         'dc-alle', null,              'segunda', 'tarde', '13:30', '17:30', 4, 4),
      L('lc-mo2', 'ar-mo',       'Santa Casa (HCSA)',   'Ambulatório de Especialidades',     'dc-cris', null,              'terca',   'manha', '08:00', '12:00', 4, 4),
      L('lc-mo3', 'ar-mo',       'Santa Casa (HSCL)',   'Ambulatório ORL — Reab. Orofacial', 'dc-mama', null,              'segunda', 'manha', '08:00', '12:00', 4, 2),
      // Linguagem Infantil
      L('lc-li1', 'ar-ling-inf', 'Frei Pacífico',       'Clínica',                           'dc-deis', null, 'sexta',   'tarde', '13:30', '17:30', 4, 4),
      L('lc-li2', 'ar-ling-inf', 'Frei Pacífico/LIBRAS','Clínica',                           'dc-deis', 'externo:pc-fabz', 'terca',   'tarde', '13:30', '17:30', 4, 4),
      L('lc-li3', 'ar-ling-inf', 'Santa Casa (HCSA)',   'Ambulatório de Especialidades',     'dc-leti', null,              'quarta',  'manha', '08:00', '12:00', 4, 4),
      // Saúde Coletiva
      L('lc-sc1', 'ar-sc',       'SMS',                 'AMB. IAPI',                         'dc-rafa', 'externo:pc-atys', 'terca',   'tarde', '13:30', '17:30', 4, 2),
      L('lc-sc2', 'ar-sc',       'SMS',                 'AMB. IAPI',                         'dc-andb', null,              'quarta',  'manha', '08:00', '12:00', 4, 2),
      L('lc-sc3', 'ar-sc',       'SMS',                 'US Nova Brasília',                  'dc-fabi', null,              'quarta',  'tarde', '13:30', '17:30', 4, 2),
      L('lc-sc4', 'ar-sc',       'SMS',                 'EESCA NEB',                         'dc-rafa', null, 'quarta',  'manha', '08:00', '12:30', 4.5, 2),
      L('lc-sc5', 'ar-sc',       'SMS',                 'EESCA NEB',                         'dc-rafa', null, 'quarta',  'tarde', '13:30', '17:30', 4, 2),
      L('lc-sc6', 'ar-sc',       'SMS',                 'EESCA Vila Comerciários',           'dc-rafa', 'externo:pc-mero', 'quinta',  'manha', '08:00', '12:00', 4, 1),
      L('lc-sc7', 'ar-sc',       'SMS',                 'EESCA Camaquã',                     'dc-rafa', 'externo:pc-msan', 'quinta',  'manha', '08:00', '12:00', 4, 1),
      L('lc-sc8', 'ar-sc',       'SMS',                 'EESCA Santa Marta',                 'dc-rafa', 'externo:pc-mich', 'terca',   'tarde', '13:30', '17:30', 4, 1),
      // Audiologia II — SADT (sub-área, 40h)
      L('lc-sadt1', 'ar-aud2-sadt', 'Santa Casa (HCSA)', 'SADT (SA)',                        'dc-mmac', null,              'segunda', 'manha', '08:00', '12:00', 4, 4),
      L('lc-sadt2', 'ar-aud2-sadt', 'Santa Casa (HCSA)', 'SADT (SA)',                        'dc-mmac', null,              'sexta',   'manha', '08:00', '12:00', 4, 4),
      // Audiologia II — Ambulatório ORL/TAN (sub-área, 10h)
      L('lc-tan1',  'ar-aud2-tan',  'Santa Casa (HSCL)', 'Ambulatório ORL — TAN',            'dc-mmac', null,              'terca',   'tarde', '13:00', '16:00', 3, 2),
      // Audiologia II — Santa Marta (sub-área, 60h) — 2 slots integrais
      L('lc-sm1',   'ar-aud2-sm',   'SMS',               'AMB. Santa Marta (SM)',            'dc-isab', 'externo:pc-cmar', 'segunda', 'integral', '08:00', '17:00', 8, 4),
      L('lc-sm2',   'ar-aud2-sm',   'SMS',               'AMB. Santa Marta (SM)',            'dc-isab', 'externo:pc-cmar', 'terca',   'integral', '08:00', '17:00', 8, 4),
      // LAD
      L('lc-lad1', 'ar-lad',      'Santa Casa (HSCL)',   'Ambulatório - C',                   'dc-gabr', null,              'sexta',   'tarde', '13:00', '17:00', 4, 4),
      L('lc-lad2', 'ar-lad',      'UFCSPA',              'Fisioterapia',                      'dc-barb', null,              'quarta',  'manha', '08:00', '12:00', 4, 4),
      // Voz
      L('lc-voz1', 'ar-voz',      'Santa Casa (HSCL)',   'Ambulatório - ORL',                 'dc-maur', null,              'sexta',   'tarde', '13:30', '17:30', 4, 4),
      L('lc-voz2', 'ar-voz',      'UFCSPA',              'Coral',                             'dc-dani', null,              'terca',   'manha', '08:00', '12:00', 4, 4),
      L('lc-voz3', 'ar-voz',      'Rádio Guaíba',        'Rádio',                             'dc-maur', null,              'quinta',  'tarde', '14:00', '18:00', 4, 2),
      // Hospitalar - Pediatria
      L('lc-hp1', 'ar-hosp-ped', 'Santa Casa (HCSA)',   'U.I - SUS',                         'dc-lisi', null,              'terca',   'manha', '08:00', '12:00', 4, 4),
      L('lc-hp2', 'ar-hosp-ped', 'Santa Casa (HCSA)',   'U.I - SUS',                         'dc-lisi', null,              'quarta',  'manha', '08:00', '12:00', 4, 4),
      // Hospitalar - Adulto
      L('lc-ha1', 'ar-hosp-adu', 'Santa Casa (HSCL)',   '2º Andar - AVC',                    'dc-evel', null,              'segunda', 'manha', '08:00', '12:00', 4, 4),
      L('lc-ha2', 'ar-hosp-adu', 'Santa Casa (HSCL)',   '2º Andar - AVC',                    'dc-evel', null,              'quarta',  'manha', '08:00', '12:00', 4, 4),
      L('lc-ha3', 'ar-hosp-adu', 'GHC',                 'Medicina Interna',                  'dc-shei', 'externo:pc-kmay', 'terca',   'manha', '08:00', '12:00', 4, 2),
      L('lc-ha4', 'ar-hosp-adu', 'GHC',                 'Medicina Interna',                  'dc-shei', 'externo:pc-kmay', 'quinta',  'manha', '08:00', '12:00', 4, 2),
      L('lc-ha5', 'ar-hosp-adu', 'GHC',                 'Emergência',                        'dc-shei', null, 'quinta',  'tarde', '13:00', '16:00', 3, 2),
      L('lc-ha6', 'ar-hosp-adu', 'GHC',                 'Neurologia',                        'dc-shei', 'externo:pc-alin', 'quinta',  'manha', '08:00', '12:00', 4, 2),
      // Hospitalar - Neonatologia
      L('lc-hn1', 'ar-hosp-neo', 'Santa Casa (HSCL)',   'UTI Neonatal',                      'dc-shei', null,              'terca',   'tarde', '13:00', '16:00', 3, 4),
      L('lc-hn2', 'ar-hosp-neo', 'Santa Casa (HSCL)',   'UTI Neonatal',                      'dc-shei', null,              'quinta',  'tarde', '13:00', '16:00', 3, 4),
    ];
    // Locais com PASSAGEM DE GRUPO (último encontro de um grupo = 1º do próximo).
    ['lc-mo1', 'lc-li1', 'lc-sm1'].forEach((id) => { const l = locais.find((x) => x.id === id); if (l) l.passagem_grupo = true; });

    // ---- AFASTAMENTOS (previstos no bootstrap) -----------------------------
    //  Cada afastamento referencia UMA pessoa: docente_id OU preceptor_id
    //  (a outra fica null). O motor só prejudica um local numa data quando
    //  TODOS os responsáveis daquele local (docente + preceptor) estão fora.
    const afastamentos = [
      { id: 'af-1', ciclo_id: cicloId, docente_id: 'dc-mama', preceptor_id: null,      tipo: 'ferias',  motivo: 'Férias regulamentares',       data_inicio: '2026-07-13', data_retorno: '2026-07-27', criado_em: '2026-02-10' },
      { id: 'af-2', ciclo_id: cicloId, docente_id: 'dc-shei', preceptor_id: null,      tipo: 'licenca', motivo: 'Licença capacitação',          data_inicio: '2026-09-07', data_retorno: '2026-09-18', criado_em: '2026-02-10' },
      { id: 'af-3', ciclo_id: cicloId, docente_id: 'dc-maur', preceptor_id: null,      tipo: 'outro',   motivo: 'Congresso Brasileiro de Fono', data_inicio: '2026-10-14', data_retorno: '2026-10-17', criado_em: '2026-02-10' },
      { id: 'af-4', ciclo_id: cicloId, docente_id: null,      preceptor_id: 'pc-kmay', tipo: 'ferias',  motivo: 'Férias da preceptora',         data_inicio: '2026-08-03', data_retorno: '2026-08-14', criado_em: '2026-02-10' },
    ];

    // ---- INDISPONIBILIDADES DE LOCAL (só na operação; vazio no bootstrap) --
    const indisponibilidades_local = [];

    // ---- EVENTOS (acadêmicos manuais + feriados simulados) -----------------
    const eventos = [
      { id: 'ev-1', ciclo_id: cicloId, nome: 'Semana Acadêmica de Fonoaudiologia', tipo: 'academico', origem: 'manual',       data_inicio: '2026-05-18', data_fim: '2026-05-22', bloqueia_estagio: true },
      { id: 'ev-2', ciclo_id: cicloId, nome: 'Jornada de Linguagem',                tipo: 'academico', origem: 'manual',       data_inicio: '2026-08-10', data_fim: '2026-08-10', bloqueia_estagio: false }, // Linguagem não bloqueia
      { id: 'ev-3', ciclo_id: cicloId, nome: 'Reunião da Comissão de Estágios',      tipo: 'reuniao',   origem: 'manual',       data_inicio: '2026-06-24', data_fim: '2026-06-24', bloqueia_estagio: true },
      { id: 'ev-4', ciclo_id: cicloId, nome: 'Tiradentes',                           tipo: 'feriado',   origem: 'api_feriados', data_inicio: '2026-04-21', data_fim: '2026-04-21', bloqueia_estagio: true },
      { id: 'ev-5', ciclo_id: cicloId, nome: 'Dia do Trabalho',                      tipo: 'feriado',   origem: 'api_feriados', data_inicio: '2026-05-01', data_fim: '2026-05-01', bloqueia_estagio: true },
      { id: 'ev-6', ciclo_id: cicloId, nome: 'Independência do Brasil',              tipo: 'feriado',   origem: 'api_feriados', data_inicio: '2026-09-07', data_fim: '2026-09-07', bloqueia_estagio: true },
      { id: 'ev-7', ciclo_id: cicloId, nome: 'Revolução Farroupilha (RS)',           tipo: 'feriado',   origem: 'api_feriados', data_inicio: '2026-09-20', data_fim: '2026-09-20', bloqueia_estagio: true },
    ];

    // ---- ALUNOS + MATRÍCULAS ------------------------------------------------
    //  7º semestre = mini-ciclo: cursam SOMENTE Audiologia I.
    //  9º/10º semestre = já começam com Audiologia I CONCLUÍDA (pré-requisito)
    //  e cursam as demais áreas (incluindo as sub-áreas de Aud II e Hospitalar);
    //  alguns já trazem áreas concluídas de antes — o ciclo aloca só o que falta.
    // só áreas LEAF (exclui containers compostos — o aluno cursa as sub-áreas)
    const areas910 = areas.filter((a) => a.fase === '9_10' && !a.composta).map((a) => a.id);
    // "unidades" matriculáveis = áreas simples + compostas (a composta é escolhida
    // como um todo e expande nas suas sub-áreas leaf). O professor escolhe o que cada
    // aluno faz no ciclo — não é mais "todos em tudo".
    const unidades910 = areas.filter((a) => a.fase === '9_10' && a.area_mae == null).map((a) => a.id);
    const leavesDe = (uid) => { const u = areas.find((a) => a.id === uid); return u && u.composta ? areas.filter((a) => a.area_mae === uid).map((a) => a.id) : [uid]; };

    // 12 alunos no 7º → Audiologia I tem 3 SLOTS paralelos (terça/quinta/sexta, cap. 4)
    // = 3 grupos simultâneos que cobrem os 12 numa única leva.
    const nomes5 = [
      'Alícia Bertoldo', 'Breno Sampaio', 'Carolina Vidal', 'Diego Antunes',
      'Elisa Moura', 'Fernando Kühn', 'Gabriela Reis', 'Heitor Cardozo',
      'Igor Nunes', 'Júlia Prado', 'Kevin Rocha', 'Lara Menezes',
    ];
    const nomes67 = [
      'Amanda Ribeiro', 'Bruno Carvalho', 'Camila Fontes', 'Daniel Azevedo', 'Eduarda Pires',
      'Felipe Antunes', 'Gabriela Souza', 'Henrique Dias', 'Isabela Correa', 'João Pedro Matos',
      'Karina Lopes', 'Lucas Ferreira', 'Mariana Teixeira', 'Natália Gomes', 'Otávio Barros',
      'Patrícia Vasques', 'Quésia Andrade', 'Rodrigo Peixoto', 'Sofia Cardoso', 'Thiago Ramos',
    ];

    const alunos = [];
    const matriculas = [];
    let ord = 0;
    let mi = 1;

    // 7º semestre — Audiologia I em andamento
    nomes5.forEach((nome, i) => {
      const alunoId = 'al-5-' + (i + 1);
      ord++;
      const mat5 = '2026' + String(2001 + i);
      alunos.push({ id: alunoId, ciclo_id: cicloId, nome, matricula: mat5,
        email: mat5 + '@aluno.ufcspa.edu.br', semestre: 7, ordenamento: ord,
        locais_bloqueados: [], criado_em: '2026-02-15' });
      matriculas.push({ id: 'mt-' + mi++, aluno_id: alunoId, area_id: 'ar-aud1', data_matricula: '2026-03-02',
        status: 'em_andamento', data_conclusao_prevista: null, data_conclusao: null });
    });

    // 9º/10º semestre — Audiologia I concluída + demais áreas
    nomes67.forEach((nome, i) => {
      const alunoId = 'al-67-' + (i + 1);
      ord++;
      const mat67 = '2026' + String(1001 + i);
      // exemplo de restrição: o 1º aluno de 9/10 não pode ir a 2 campos de Saúde Coletiva
      // (condição especial) — o motor o aloca em outro local da área.
      alunos.push({ id: alunoId, ciclo_id: cicloId, nome, matricula: mat67,
        email: mat67 + '@aluno.ufcspa.edu.br', semestre: 9 + (i % 2), ordenamento: ord,
        locais_bloqueados: i === 0 ? ['lc-sc6', 'lc-sc7'] : [], criado_em: '2026-02-15' });
      // pré-requisito: Audiologia I já concluída (cursada no 7º semestre anterior)
      matriculas.push({ id: 'mt-' + mi++, aluno_id: alunoId, area_id: 'ar-aud1', data_matricula: '2025-03-03',
        status: 'concluida', data_conclusao_prevista: '2025-11-28', data_conclusao: '2025-11-28' });
      // algumas áreas de 9/10 já concluídas de antes (0 a 2)
      const nConcl = Math.floor(rnd() * 3);
      const concl = pickN(areas910, nConcl);
      concl.forEach((arId) => {
        matriculas.push({ id: 'mt-' + mi++, aluno_id: alunoId, area_id: arId, data_matricula: '2025-08-01',
          status: 'concluida', data_conclusao_prevista: '2025-12-05', data_conclusao: '2025-12-05' });
      });
      // O aluno faz um SUBCONJUNTO de áreas neste ciclo (o professor define o que é
      // obrigatório para ele) — não é mais "todos em tudo". O seed sorteia 2-3 unidades
      // e expande as compostas nas sub-áreas. As demais áreas simplesmente NÃO entram
      // neste ciclo (não viram pendência); se faltar, o professor matricula e o motor recalcula.
      const nUnid = 2 + Math.floor(rnd() * 2); // 2 ou 3 unidades por aluno
      const doAluno = [];
      pickN(unidades910, nUnid).forEach((u) => leavesDe(u).forEach((lf) => { if (doAluno.indexOf(lf) < 0) doAluno.push(lf); }));
      doAluno.filter((arId) => concl.indexOf(arId) < 0).forEach((arId) => {
        matriculas.push({ id: 'mt-' + mi++, aluno_id: alunoId, area_id: arId, data_matricula: '2026-03-02',
          status: 'em_andamento', data_conclusao_prevista: null, data_conclusao: null });
      });
    });

    return { locais, afastamentos, indisponibilidades_local, eventos, alunos, matriculas };
  }

  // ============================================================================
  //  HISTÓRICO — um ano encerrado (2025) para a tela de Histórico.
  //  Egressos de 9º/10º: retrato das áreas de estágio da fase.
  // ============================================================================
  function areasSnapshot(areaObjs, concluidas) {
    return areaObjs.map((ar, idx) => {
      const done = idx < concluidas;
      return {
        nome: ar.nome,
        carga_exigida: ar.carga_exigida,
        horas_cumpridas: done ? ar.carga_exigida : Math.round(ar.carga_exigida * (0.2 + rnd() * 0.5)),
        data_conclusao: done ? '2025-1' + (idx < 3 ? '1' : '2') + '-' + String(5 + idx).padStart(2, '0') : null,
      };
    });
  }

  const historico = (function () {
    _s = 12345678;
    const areas67 = areas.filter((a) => a.fase === '9_10' && !a.composta);
    const total67 = areas67.length;
    const nomes2025 = [
      'Alice Bezerra', 'Bernardo Klein', 'Clara Menezes', 'Davi Oliveira', 'Elisa Tavares',
      'Fábio Guerra', 'Giovana Pinto', 'Hugo Martins', 'Ingrid Salles', 'Júlio Camargo',
      'Larissa Duarte', 'Miguel Farias', 'Nina Rezende', 'Otto Wagner', 'Priscila Amaral',
      'Renan Vidal', 'Sabrina Leão', 'Tomás Brito', 'Vera Lúcia Campos', 'Yasmin Faro',
    ];
    return nomes2025.map((nome, i) => {
      const concluidas = i < 13 ? total67 : (total67 - 1 - (i % 3)); // maioria completa
      const snap = areasSnapshot(areas67, concluidas);
      const total = snap.reduce((a, s) => a + s.horas_cumpridas, 0);
      return {
        id: 'hs-' + (i + 1),
        ano: 2025,
        ciclo_id: 'cl-2025',
        aluno_nome: nome,
        matricula: '2025' + String(1001 + i),
        areas: snap,
        carga_horaria_total: total,
        situacao: concluidas === total67 ? 'ciclo_completo' : 'pendente',
        encerramento: '2025-12-19',
        criado_em: '2025-12-19',
      };
    });
  })();

  // ---- CICLOS — na carga inicial só existe o 2025 (encerrado) --------------
  const ciclos = [
    {
      id: 'cl-2025',
      data_inicio: '2025-03-03',
      data_fim: '2025-12-12',
      status: 'encerrado',
      passo_bootstrap: null,
      escala_desatualizada: false,
      criado_em: '2025-02-14',
      encerrado_em: '2025-12-19',
    },
  ];

  // ---- Estado inicial completo ---------------------------------------------
  window.MOCK = {
    versao: 13,
    areas,
    docentes,
    preceptores,
    ciclos,
    historico,
    // coleções do ciclo ativo (vazias até "Abrir novo ciclo")
    locais: [],
    afastamentos: [],
    indisponibilidades_local: [],
    eventos: [],
    alunos: [],
    matriculas: [],
    alocacoes: [],
    sessoes: [],
    grupos: [],
    // fila de gatilhos de remanejo acumulados na operação
    fila_remanejo: [],
    // registro de atividade recente (feed do painel)
    atividade: [],
  };

  window.MOCK_HELPERS = { seedCicloData };
})();
