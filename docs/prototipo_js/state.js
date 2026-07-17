/* ============================================================================
   state.js — Estado da aplicação, persistência em localStorage,
   máquina de estados do ciclo e o MOTOR SIMULADO (alocação + remanejo).
   ============================================================================ */
(function () {
  'use strict';

  const KEY = 'gestao-estagios-mock';

  // ---- utilidades de data (strings 'YYYY-MM-DD') ---------------------------
  function hoje() {
    // "hoje" = data real do navegador
    const d = new Date();
    return iso(d);
  }
  function iso(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  function parse(s) {
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d);
  }
  function addDays(s, n) { const d = parse(s); d.setDate(d.getDate() + n); return iso(d); }
  function diffDays(a, b) { return Math.round((parse(b) - parse(a)) / 86400000); }
  function dentro(dia, ini, fim) { return dia >= ini && dia <= fim; }
  const DIAS_IDX = { domingo: 0, segunda: 1, terca: 2, quarta: 3, quinta: 4, sexta: 5, sabado: 6 };

  // ---- Estado em memória ----------------------------------------------------
  let S = null;
  const listeners = [];

  function deepClone(o) { return JSON.parse(JSON.stringify(o)); }

  function load() {
    let raw = null;
    try { raw = localStorage.getItem(KEY); } catch (e) {}
    if (raw) {
      try { S = JSON.parse(raw); } catch (e) { S = null; }
    }
    if (!S || S.versao !== window.MOCK.versao) {
      reset(true);
    }
    return S;
  }

  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {}
  }

  function reset(silent) {
    S = deepClone(window.MOCK);
    persist();
    if (!silent) emit();
  }

  function emit() { listeners.forEach((fn) => fn(S)); }
  function onChange(fn) { listeners.push(fn); }

  function save() { persist(); emit(); }

  function uid(prefix) {
    return prefix + '-' + Date.now().toString(36) + '-' + Math.floor(Math.random() * 1e6).toString(36);
  }

  // ---- Máquina de estados do ciclo -----------------------------------------
  function cicloAtivo() {
    return S.ciclos.find((c) => c.status === 'rascunho' || c.status === 'em_andamento') || null;
  }
  function estadoInicial() {
    const c = cicloAtivo();
    if (!c) return { rota: '#/welcome', ciclo: null };
    if (c.status === 'rascunho') return { rota: '#/bootstrap', ciclo: c };
    return { rota: '#/painel', ciclo: c };
  }

  function abrirCiclo(data_inicio, data_fim) {
    const id = uid('cl');
    const ciclo = {
      id, data_inicio, data_fim, status: 'rascunho', passo_bootstrap: 1,
      escala_desatualizada: false, criado_em: hoje(), encerrado_em: null,
    };
    S.ciclos.push(ciclo);
    // popula as coleções do ciclo com o seed (para o bootstrap já vir preenchido)
    const seed = window.MOCK_HELPERS.seedCicloData(id);
    S.locais = seed.locais;
    S.afastamentos = seed.afastamentos;
    S.indisponibilidades_local = seed.indisponibilidades_local;
    S.eventos = seed.eventos;
    S.alunos = seed.alunos;
    S.matriculas = seed.matriculas;
    S.alocacoes = [];
    S.sessoes = [];
    S.grupos = [];
    S.grupo_travas = [];
    S.fila_remanejo = [];
    S.atividade = [{ id: uid('at'), quando: hoje(), texto: 'Ciclo aberto — bootstrap iniciado', tipo: 'ciclo' }];
    save();
    return ciclo;
  }

  function setPassoBootstrap(n) {
    const c = cicloAtivo();
    if (c && c.status === 'rascunho') { c.passo_bootstrap = n; save(); }
  }

  // ============================================================================
  //  MOTOR SIMULADO — geração da escala (alocacoes + sessoes)
  // ============================================================================
  function eventoBloqueiaEm(dia) {
    return S.eventos.some((e) => e.bloqueia_estagio && dentro(dia, e.data_inicio, e.data_fim));
  }
  function docenteAfastadoEm(docenteId, dia) {
    return S.afastamentos.some((a) => a.docente_id === docenteId && dentro(dia, a.data_inicio, a.data_retorno));
  }
  function preceptorAfastadoEm(preceptorId, dia) {
    return S.afastamentos.some((a) => a.preceptor_id === preceptorId && dentro(dia, a.data_inicio, a.data_retorno));
  }
  // Resolve o preceptor de campo de um local (referência polimórfica):
  // preceptor_tipo 'externo' → catálogo preceptores; 'docente' → catálogo
  // docentes; sem preceptor_id → null. Devolve { id, tipo, nome, afastadoEm }.
  function preceptorDoLocal(local) {
    if (!local || !local.preceptor_id) return null;
    const tipo = local.preceptor_tipo || 'externo';
    const pessoa = tipo === 'docente'
      ? S.docentes.find((d) => d.id === local.preceptor_id)
      : (S.preceptores || []).find((p) => p.id === local.preceptor_id);
    if (!pessoa) return null;
    return {
      id: local.preceptor_id, tipo, nome: pessoa.nome,
      afastadoEm: (dia) => tipo === 'docente' ? docenteAfastadoEm(local.preceptor_id, dia) : preceptorAfastadoEm(local.preceptor_id, dia),
    };
  }
  // Regra de cobertura: um encontro só cai (local sem cobertura) numa data se
  // TODOS os responsáveis do local estiverem afastados ao mesmo tempo. Os
  // responsáveis são o docente (sempre) + o preceptor de campo (se houver — que
  // pode ser um preceptor externo OU outro docente). Se qualquer um estiver
  // presente, o encontro acontece. Quando o preceptor é o próprio docente do
  // local, cai quando essa única pessoa faltar.
  function localSemCoberturaEm(local, dia) {
    if (!local) return false;
    const docenteFora = docenteAfastadoEm(local.docente_id, dia);
    const prec = preceptorDoLocal(local);
    if (!prec) return docenteFora;                    // só o docente responde
    return docenteFora && prec.afastadoEm(dia);       // ambos precisam faltar
  }
  function localIndisponivelEm(localId, dia) {
    return S.indisponibilidades_local.some((i) => i.local_id === localId && dentro(dia, i.data_inicio, i.data_fim));
  }
  // Restrição de local do aluno: por padrão o aluno está disponível em TODOS os
  // locais; `aluno.locais_bloqueados` guarda só as exceções (locais desmarcados,
  // ex.: condição especial). O motor não aloca o aluno num local bloqueado.
  function alunoBloqueadoNoLocal(alunoId, localId) {
    const al = S.alunos.find((a) => a.id === alunoId);
    return !!(al && al.locais_bloqueados && al.locais_bloqueados.indexOf(localId) >= 0);
  }
  function horasLocal(local) {
    // horas REAIS de cada encontro (desconta almoço no integral). Preferir horas_sessao
    // quando cadastrado; senão cair para (hora_fim − hora_inicio).
    if (typeof local.horas_sessao === 'number' && local.horas_sessao > 0) return local.horas_sessao;
    const [hi, mi] = local.hora_inicio.split(':').map(Number);
    const [hf, mf] = local.hora_fim.split(':').map(Number);
    return (hf * 60 + mf - hi * 60 - mi) / 60;
  }
  // Carga horária SEMANAL de um local = horas por encontro × nº de dias/semana.
  function horasLocalSemana(local) {
    const nDias = (local.dias && local.dias.length) || 1;
    return horasLocal(local) * nDias;
  }
  // Teto de carga horária semanal por aluno (regra do motor — constante fixa).
  const MAX_HORAS_SEMANAIS = 30;

  // gera os ENCONTROS (sessões) de uma alocação: exatamente `numero_encontros`
  // do local (vindo do espelho), semana a semana, pulando datas bloqueadas.
  // Projeta além do fim do ciclo — é isso que revela o risco de "não fechar".
  //  inicioMin (opcional): data mínima de início — usada na alocação manual para
  //  sentar a turma "a partir de agora" em vez de recomeçar do início do ciclo.
  function gerarSessoes(alocacaoId, local, area, ciclo, inicioMin) {
    const h = horasLocal(local);
    const alvo = local.numero_encontros || Math.max(1, Math.round((area.carga_exigida || 0) / (h || 1)));
    const sessoes = [];
    const partida = inicioMin && inicioMin > ciclo.data_inicio ? inicioMin : ciclo.data_inicio;
    let cursor = parse(partida);
    const alvoDow = DIAS_IDX[local.dia_semana];
    while (cursor.getDay() !== alvoDow) cursor.setDate(cursor.getDate() + 1);
    let dia = iso(cursor);
    let guard = 0;
    while (sessoes.length < alvo && guard < alvo * 4 + 30) {
      guard++;
      const bloqueado = eventoBloqueiaEm(dia) || localSemCoberturaEm(local, dia) || localIndisponivelEm(local.id, dia);
      if (!bloqueado) {
        const passado = dia < hoje();
        sessoes.push({
          id: uid('ss'), alocacao_id: alocacaoId, data: dia,
          hora_inicio: local.hora_inicio, hora_fim: local.hora_fim, horas: h,
          status: passado ? 'cumprida' : 'prevista',
        });
      }
      dia = addDays(dia, 7); // semanal
    }
    return sessoes;
  }

  // conflito de dia/turno: aluno não pode ter duas sessões no mesmo dia/turno
  function alunoOcupado(ocupacoes, dia_semana, turno) {
    return ocupacoes.some((o) => o.dia_semana === dia_semana && o.turno === turno);
  }

  // Geração completa (bootstrap). Retorna relatório.
  function gerarEscala() {
    const ciclo = cicloAtivo();
    S.alocacoes = [];
    S.sessoes = [];
    reindexPorPrioridade(); // ordenamento = prioridade + matrícula; a montagem manual (pins) é honrada abaixo
    const alunos = S.alunos.slice().sort((a, b) => a.ordenamento - b.ordenamento);
    const capUso = {}; // local_id -> nº alunos
    const relatorio = { alocados: 0, alunos_ok: 0, alunos_parcial: 0, sem_vaga: [], previsoes: [] };

    alunos.forEach((aluno) => {
      const ocup = [];
      let horasSem = 0; // carga horária semanal já alocada ao aluno (teto de 30h)
      const mats = S.matriculas.filter((m) => m.aluno_id === aluno.id && m.status === 'em_andamento');
      let colocadas = 0;
      mats.forEach((mat) => {
        const area = S.areas.find((a) => a.id === mat.area_id);
        // Pré-requisito Audiologia I (§4): responsabilidade COMPARTILHADA, não bloqueia.
        // A coordenação conhece o histórico real; o sistema só avisa para conferir (UI),
        // e o motor aloca normalmente mesmo sem registro de conclusão.
        // locais ativos da área, sem restrição do aluno, com vaga, sem conflito de dia/turno
        const daArea = S.locais.filter((l) => l.area_id === mat.area_id && l.ativo);
        const liberados = daArea.filter((l) => !alunoBloqueadoNoLocal(aluno.id, l.id));
        const semConflito = liberados.filter((l) =>
          (capUso[l.id] || 0) < l.capacidade && !alunoOcupado(ocup, l.dia_semana, l.turno));
        // teto de 30h semanais: não aloca se estourar a carga da semana
        const cand = semConflito.filter((l) => horasSem + horasLocalSemana(l) <= MAX_HORAS_SEMANAIS);
        if (!cand.length) {
          let motivo;
          if (daArea.length && !liberados.length) motivo = 'restrição de local (nenhum local liberado)';
          else if (semConflito.length) motivo = 'excederia ' + MAX_HORAS_SEMANAIS + 'h semanais';
          relatorio.sem_vaga.push({ aluno: aluno.nome, area: area.nome, motivo });
          return;
        }
        // honra a montagem manual: se o aluno foi pré-colocado (pin) num local desta
        // área e ele está disponível, usa ELE; senão, o primeiro candidato.
        const pin = (S.grupo_travas || []).find((t) => t.aluno_id === aluno.id && cand.some((l) => l.id === t.local_id));
        const local = pin ? cand.find((l) => l.id === pin.local_id) : cand[0];
        capUso[local.id] = (capUso[local.id] || 0) + 1;
        horasSem += horasLocalSemana(local);
        ocup.push({ dia_semana: local.dia_semana, turno: local.turno });
        const alocId = uid('ao');
        const sess = gerarSessoes(alocId, local, area, ciclo);
        const dataFim = sess.length ? sess[sess.length - 1].data : ciclo.data_inicio;
        S.alocacoes.push({
          id: alocId, aluno_id: aluno.id, local_id: local.id, matricula_id: mat.id,
          data_inicio: sess.length ? sess[0].data : ciclo.data_inicio,
          data_fim_prevista: dataFim, travada: false, status: 'ativa', ajuste_encontros: 0,
        });
        sess.forEach((s) => S.sessoes.push(s));
        mat.data_conclusao_prevista = dataFim;
        colocadas++;
        relatorio.alocados++;
        relatorio.previsoes.push({ aluno: aluno.nome, area: area.nome, previsao: dataFim, risco: dataFim > ciclo.data_fim });
      });
      if (colocadas === mats.length && mats.length) relatorio.alunos_ok++;
      else if (colocadas > 0) relatorio.alunos_parcial++;
    });

    atualizarConclusoes();
    gerarGrupos();
    relatorio.em_risco = relatorio.previsoes.filter((p) => p.risco).length;
    return relatorio;
  }

  // conclusão automática: encontros passados viram cumpridos; área conclui quando
  // os encontros FEITOS (presença assumida ± ajuste do professor) atingem o total.
  // Áreas sem alocação (carry-forward, concluídas de antes) não são tocadas.
  function atualizarConclusoes() {
    const h = hoje();
    S.sessoes.forEach((s) => { if (s.status === 'prevista' && s.data < h) s.status = 'cumprida'; });
    S.matriculas.forEach((mat) => {
      const alocs = S.alocacoes.filter((a) => a.matricula_id === mat.id && a.status === 'ativa');
      if (!alocs.length) return; // carry-forward / não alocada: preserva como está
      const enc = encontrosMatricula(mat);
      if (enc.total > 0 && enc.feitos >= enc.total) {
        if (mat.status !== 'concluida') { mat.status = 'concluida'; mat.data_conclusao = mat.data_conclusao_prevista || h; }
      } else if (mat.status === 'concluida') {
        mat.status = 'em_andamento';
        mat.data_conclusao = null;
      }
    });
  }

  // ============================================================================
  //  GRUPOS (ondas por local) — materializados em S.grupos, regenerados a cada
  //  geração/remanejo e ao abrir a tela. Onda 1 = quem está no local agora;
  //  ondas seguintes = fila da área (por ordenamento), em cascata, cada onda
  //  começando quando a anterior daquele local conclui. Respeita capacidade,
  //  restrições de local do aluno (AR-2) e sinaliza conflito de dia/turno.
  // ============================================================================
  function fmtBR(s) { const p = String(s).split('-'); return p.length === 3 ? p[2] + '/' + p[1] + '/' + p[0] : s; }
  function janelasSobrepoem(iniA, fimA, iniB, fimB) { return !(fimA < iniB || iniA > fimB); }
  function duracaoOndaDias(local) { return Math.max(1, (local.numero_encontros || 10)) * 7; }
  // Início da próxima onda no local: com PASSAGEM DE GRUPO, começa no ÚLTIMO dia
  // da onda anterior (1 dia de sobreposição — a passagem); sem, na semana seguinte.
  function proximoInicioOnda(local, fimAnterior) {
    return local.passagem_grupo ? fimAnterior : addDays(fimAnterior, 7);
  }

  // SIMULAÇÃO POR LINHA DO TEMPO (global, cronológica). Em vez de projetar área
  // por área, abre as ondas futuras em ORDEM DE DATA entre todos os slots e, em
  // cada abertura, puxa da fila (por prioridade) quem PODE entrar — respeitando
  // capacidade, restrição de local, conflito de dia/turno e teto de 30h. Assim
  // cada aluno pega a leva mais cedo viável somando TODAS as suas áreas (mínima
  // espera + paralelismo entre áreas), e o motivo de quem foi adiado fica gravado
  // no membro (transparência). Onda 1 = quem já está no local (alocações ativas).
  function gerarGrupos() {
    const ciclo = cicloAtivo();
    S.grupos = [];
    if (!ciclo) return S.grupos;
    const areaNomeDe = (id) => (S.areas.find((x) => x.id === id) || {}).nome || 'outra área';

    // commit: compromissos (dia/turno/janela/horas) de cada aluno. Semeado com as
    // alocações ativas (onda 1) e alimentado a cada colocação projetada.
    const commit = {};
    const addCommit = (alunoId, l, ini, fim) => (commit[alunoId] = commit[alunoId] || []).push({
      dia: l.dia_semana, turno: l.turno, ini, fim, horas: horasLocalSemana(l), areaNome: areaNomeDe(l.area_id),
    });
    S.alocacoes.filter((a) => a.status === 'ativa').forEach((a) => {
      const lc = S.locais.find((l) => l.id === a.local_id); if (lc) addCommit(a.aluno_id, lc, a.data_inicio, a.data_fim_prevista);
    });

    // estado por SLOT (local ativo): próxima abertura de onda, nº de ondas, controle de término
    const slots = {};
    S.locais.filter((l) => l.ativo).forEach((l) => {
      const alocs = S.alocacoes.filter((a) => a.local_id === l.id && a.status === 'ativa');
      let fim = ciclo.data_inicio;
      if (alocs.length) {
        const ini = alocs.reduce((m, a) => (a.data_inicio < m ? a.data_inicio : m), alocs[0].data_inicio);
        fim = alocs.reduce((m, a) => (a.data_fim_prevista > m ? a.data_fim_prevista : m), alocs[0].data_fim_prevista);
        S.grupos.push({
          id: uid('gp'), ciclo_id: ciclo.id, local_id: l.id, area_id: l.area_id, onda: 1,
          status: 'em_andamento', data_inicio: ini, data_fim: fim,
          membros: alocs.map((a) => ({ aluno_id: a.aluno_id, aviso: null })),
        });
      }
      slots[l.id] = { local: l, proxInicio: proximoInicioOnda(l, fim), ondaN: alocs.length ? 1 : 0, vazias: 0, off: false };
    });

    // pool: pares (aluno, área) sem alocação ativa — o que falta escalar. `rejeicao`
    // guarda o motivo do 1º adiamento (p/ o aviso quando o aluno finalmente entrar).
    const pool = [];
    S.matriculas
      .filter((m) => m.status === 'em_andamento' && !S.alocacoes.some((a) => a.matricula_id === m.id && a.status === 'ativa'))
      .forEach((m) => { const al = S.alunos.find((a) => a.id === m.aluno_id); if (al) pool.push({ aluno: al, areaId: m.area_id, rejeicao: null }); });

    const horasNaJanela = (alunoId, ini, fim) => (commit[alunoId] || [])
      .filter((cm) => janelasSobrepoem(cm.ini, cm.fim, ini, fim)).reduce((s, cm) => s + (cm.horas || 0), 0);
    const temDemanda = (s) => pool.some((p) => p.areaId === s.local.area_id && !alunoBloqueadoNoLocal(p.aluno.id, s.local.id));
    // O ciclo dura UM ano: uma onda só é criada se COUBER inteira dentro do ciclo
    // (data_fim ≤ fim do ciclo). Quem não couber fica sem grupo projetado — refaz no
    // próximo ciclo (aparece como "aguardando vaga"). Assim a escala nunca vaza p/ o
    // ano seguinte. NÃO afeta a onda 1 (em andamento), que vem das alocações reais.
    const limiteFim = ciclo.data_fim;
    const cabeNoCiclo = (s) => addDays(s.proxInicio, duracaoOndaDias(s.local)) <= limiteFim;

    let guarda = pool.length * 6 + 100; // trava anti-loop (término garantido)
    while (pool.length && guarda-- > 0) {
      // slots ainda ativos, com demanda e cuja próxima onda ainda cabe no ciclo;
      // escolhe o de ABERTURA mais cedo (empate: ordem do local)
      const ativos = Object.values(slots).filter((s) => !s.off && cabeNoCiclo(s) && temDemanda(s))
        .sort((a, b) => a.proxInicio.localeCompare(b.proxInicio));
      if (!ativos.length) break; // ninguém mais colocável dentro do ciclo
      const s = ativos[0], l = s.local;
      const ini = s.proxInicio, fim = addDays(ini, duracaoOndaDias(l));

      // preenche a onda até a capacidade, por prioridade, com quem PODE entrar nesta janela
      const elegiveis = pool.filter((p) => p.areaId === l.area_id && !alunoBloqueadoNoLocal(p.aluno.id, l.id))
        .sort((a, b) => a.aluno.ordenamento - b.aluno.ordenamento);
      const escolhidos = [];
      for (const p of elegiveis) {
        if (escolhidos.length >= l.capacidade) break;
        const conf = (commit[p.aluno.id] || []).find((cm) => cm.dia === l.dia_semana && cm.turno === l.turno && janelasSobrepoem(cm.ini, cm.fim, ini, fim));
        if (conf) { if (!p.rejeicao) p.rejeicao = { motivo: 'aguarda concluir ' + conf.areaNome + ' (até ' + fmtBR(conf.fim) + ')', quando: ini }; continue; }
        if (horasNaJanela(p.aluno.id, ini, fim) + horasLocalSemana(l) > MAX_HORAS_SEMANAIS) {
          if (!p.rejeicao) p.rejeicao = { motivo: 'evita passar de ' + MAX_HORAS_SEMANAIS + 'h na semana', quando: ini }; continue;
        }
        escolhidos.push(p);
      }

      s.proxInicio = proximoInicioOnda(l, fim); // avança sempre (a janela desta onda já passou)
      if (escolhidos.length) {
        s.ondaN += 1; s.vazias = 0;
        S.grupos.push({
          id: uid('gp'), ciclo_id: ciclo.id, local_id: l.id, area_id: l.area_id, onda: s.ondaN,
          status: 'previsto', data_inicio: ini, data_fim: fim,
          membros: escolhidos.map((p) => ({
            aluno_id: p.aluno.id,
            // avisa quando o aluno entrou numa leva POSTERIOR à que tentou (foi adiado)
            aviso: (p.rejeicao && ini > p.rejeicao.quando) ? p.rejeicao.motivo : null,
          })),
        });
        escolhidos.forEach((p) => { addCommit(p.aluno.id, l, ini, fim); pool.splice(pool.indexOf(p), 1); });
      } else if (++s.vazias >= 3) {
        s.off = true; // 3 ondas seguidas sem ninguém = bloqueio estrutural neste slot; desliga
      }
    }
    // pool remanescente = sem vaga viável no horizonte (restrição total ou conflito permanente) —
    // ficam sem grupo projetado; aparecem como "aguardando vaga" no detalhe do aluno.
    aplicarTravasGrupos();
    return S.grupos;
  }

  // §10.3 — reaplica os arranjos manuais de grupo sobre a projeção. Um pin
  // { aluno_id, local_id, onda } coloca o aluno na onda PREVISTA escolhida daquele
  // local. NÃO trava nada: é só a "ordem planejada" — o professor remaneja à vontade;
  // o grupo só se concretiza no dia 1 dos encontros (quando vira onda em andamento).
  function aplicarTravasGrupos() {
    const ciclo = cicloAtivo();
    (S.grupo_travas || []).forEach((t) => {
      const local = S.locais.find((l) => l.id === t.local_id);
      if (!local) return;
      // tira o aluno de qualquer grupo PREVISTO do mesmo local (onda 1 = alocação real, não mexe)
      S.grupos.forEach((g) => {
        if (g.local_id === t.local_id && g.status === 'previsto') g.membros = g.membros.filter((m) => m.aluno_id !== t.aluno_id);
      });
      // encontra/cria a onda alvo
      let alvo = S.grupos.find((g) => g.local_id === t.local_id && g.onda === t.onda);
      if (!alvo) {
        const irmaos = S.grupos.filter((g) => g.local_id === t.local_id).sort((a, b) => a.onda - b.onda);
        const base = irmaos.length ? irmaos[irmaos.length - 1] : null;
        const ini = base ? proximoInicioOnda(local, base.data_fim) : (ciclo ? ciclo.data_inicio : hoje());
        alvo = { id: uid('gp'), ciclo_id: ciclo ? ciclo.id : null, local_id: t.local_id, area_id: local.area_id,
          onda: t.onda, status: 'previsto', data_inicio: ini, data_fim: addDays(ini, duracaoOndaDias(local)), membros: [] };
        S.grupos.push(alvo);
      }
      if (alvo.status === 'previsto') {
        const m = alvo.membros.find((x) => x.aluno_id === t.aluno_id);
        if (!m) alvo.membros.push({ aluno_id: t.aluno_id, aviso: null });
      }
    });
    // descarta ondas previstas que ficaram vazias após os remanejamentos manuais
    S.grupos = S.grupos.filter((g) => g.status !== 'previsto' || g.membros.length > 0);
  }

  // grupo (onda) atual de um aluno num local, na projeção corrente
  function grupoDoAluno(alunoId, localId) {
    return (S.grupos || []).find((x) => x.local_id === localId && x.membros.some((m) => m.aluno_id === alunoId)) || null;
  }
  function _pinGrupo(alunoId, localId, onda) {
    S.grupo_travas = (S.grupo_travas || []).filter((t) => !(t.aluno_id === alunoId && t.local_id === localId));
    S.grupo_travas.push({ id: uid('gt'), aluno_id: alunoId, local_id: localId, onda });
  }
  // §10.3 — TROCA dois alunos de grupo (cada um vai para a onda do outro). Preserva o
  // tamanho de cada grupo (1-por-1). Só entre ondas PREVISTAS (grupos ainda não iniciados).
  // NÃO trava e NÃO exige remanejo: só atualiza a ordem planejada (grupos são regerados).
  function trocarAlunosGrupo(alunoA, alunoB, localId) {
    const ga = grupoDoAluno(alunoA, localId), gb = grupoDoAluno(alunoB, localId);
    if (!ga || !gb || ga.status !== 'previsto' || gb.status !== 'previsto' || ga.onda === gb.onda) return;
    _pinGrupo(alunoA, localId, gb.onda);
    _pinGrupo(alunoB, localId, ga.onda);
    const A = S.alunos.find((a) => a.id === alunoA), B = S.alunos.find((a) => a.id === alunoB);
    const lc = S.locais.find((l) => l.id === localId);
    registrarAtividade('Grupos reordenados: ' + (A ? A.nome : '?') + ' ⇄ ' + (B ? B.nome : '?') + ' em ' + (lc ? lc.campo : ''), 'edicao');
    gerarGrupos(); save();
  }
  // §10.3 — TROCA dois grupos inteiros de posição/onda (G3 ⇄ G2). Cada grupo mantém
  // seus membros; só a ordem (onda) troca. Só entre ondas PREVISTAS. Fluido, sem trava.
  function trocarGruposInteiros(localId, ondaX, ondaY) {
    const gx = S.grupos.find((x) => x.local_id === localId && x.onda === ondaX && x.status === 'previsto');
    const gy = S.grupos.find((x) => x.local_id === localId && x.onda === ondaY && x.status === 'previsto');
    if (!gx || !gy || ondaX === ondaY) return;
    gx.membros.map((m) => m.aluno_id).forEach((id) => _pinGrupo(id, localId, ondaY));
    gy.membros.map((m) => m.aluno_id).forEach((id) => _pinGrupo(id, localId, ondaX));
    const lc = S.locais.find((l) => l.id === localId);
    registrarAtividade('Grupos reordenados: Grupo ' + ondaX + ' ⇄ Grupo ' + ondaY + ' em ' + (lc ? lc.campo : ''), 'edicao');
    gerarGrupos(); save();
  }
  // Remove o arranjo manual de um aluno — volta a ser posicionado pela projeção automática.
  function destravarAlunoGrupo(alunoId, localId) {
    S.grupo_travas = (S.grupo_travas || []).filter((t) => !(t.aluno_id === alunoId && t.local_id === localId));
    gerarGrupos(); save();
  }

  // §10.3 — MOVER um aluno para OUTRO grupo (onda) do mesmo local. Diferente da troca
  // 1-por-1: é um movimento livre. Regra escolhida pela coordenação: "bloqueia tudo e
  // sugere" — o movimento SÓ acontece se a onda destino tem vaga, não gera conflito de
  // dia/turno e não estoura 30h; senão devolve os motivos + a onda mais cedo viável.
  // Avalia o encaixe do aluno na janela de um GRUPO (ignora o grupo de origem `ignorarId`,
  // de onde o aluno sairia). Devolve lista de motivos (vazia = encaixa).
  function motivosEncaixeGrupo(alunoId, local, g, ignorarId) {
    const motivos = [];
    const jaMembro = g.membros.some((m) => m.aluno_id === alunoId);
    if (g.membros.length - (jaMembro ? 1 : 0) >= local.capacidade) motivos.push('grupo cheio (' + g.membros.length + '/' + local.capacidade + ')');
    const outros = S.grupos.filter((og) => og.id !== g.id && og.id !== ignorarId && og.membros.some((m) => m.aluno_id === alunoId));
    const conf = outros.find((og) => {
      const ol = S.locais.find((x) => x.id === og.local_id);
      return ol && ol.dia_semana === local.dia_semana && ol.turno === local.turno && janelasSobrepoem(og.data_inicio, og.data_fim, g.data_inicio, g.data_fim);
    });
    if (conf) { const ca = S.areas.find((a) => a.id === conf.area_id); motivos.push('conflito de ' + local.dia_semana + '/' + local.turno + ' com ' + (ca ? ca.nome : 'outra área')); }
    const horas = outros.filter((og) => janelasSobrepoem(og.data_inicio, og.data_fim, g.data_inicio, g.data_fim))
      .reduce((s, og) => { const ol = S.locais.find((x) => x.id === og.local_id); return s + (ol ? horasLocalSemana(ol) : 0); }, 0);
    if (horas + horasLocalSemana(local) > MAX_HORAS_SEMANAIS) motivos.push('passaria de ' + MAX_HORAS_SEMANAIS + 'h na semana');
    return motivos;
  }
  // Onda PREVISTA mais cedo do local onde o aluno encaixa (p/ sugestão). Pode ser a
  // própria onda atual do aluno (= "já está no grupo mais cedo possível").
  function sugerirOndaGrupo(alunoId, local, ignorarId) {
    const ondas = S.grupos.filter((g) => g.local_id === local.id && g.status === 'previsto')
      .sort((a, b) => a.data_inicio.localeCompare(b.data_inicio));
    for (const g of ondas) { if (!motivosEncaixeGrupo(alunoId, local, g, ignorarId).length) return g.onda; }
    return null;
  }
  // Avalia mover o aluno p/ a onda `ondaDestino` do local. { ok, motivos, sugestaoOnda }.
  function avaliarMoverGrupo(alunoId, localId, ondaDestino) {
    const local = S.locais.find((l) => l.id === localId);
    if (!local) return { ok: false, motivos: ['Local não encontrado.'], sugestaoOnda: null };
    const destino = S.grupos.find((g) => g.local_id === localId && g.onda === ondaDestino);
    if (!destino) return { ok: false, motivos: ['Grupo destino não encontrado.'], sugestaoOnda: null };
    if (destino.status !== 'previsto') return { ok: false, motivos: ['Só dá para mover para grupos na fila (ainda não iniciados).'], sugestaoOnda: null };
    const atual = grupoDoAluno(alunoId, localId);
    if (atual && atual.status !== 'previsto') return { ok: false, motivos: ['O aluno já iniciou este grupo — não dá para mover.'], sugestaoOnda: null };
    if (atual && atual.onda === ondaDestino) return { ok: false, motivos: ['O aluno já está neste grupo.'], sugestaoOnda: null };
    const motivos = motivosEncaixeGrupo(alunoId, local, destino, atual ? atual.id : null);
    if (!motivos.length) return { ok: true, motivos: [], sugestaoOnda: null };
    return { ok: false, motivos, sugestaoOnda: sugerirOndaGrupo(alunoId, local, atual ? atual.id : null) };
  }
  // Executa o movimento se válido; senão devolve a avaliação (a UI alerta + sugere).
  function moverAlunoGrupo(alunoId, localId, ondaDestino) {
    const av = avaliarMoverGrupo(alunoId, localId, ondaDestino);
    if (!av.ok) return av;
    _pinGrupo(alunoId, localId, ondaDestino);
    const al = S.alunos.find((a) => a.id === alunoId), lc = S.locais.find((l) => l.id === localId);
    registrarAtividade('Aluno movido de grupo: ' + (al ? al.nome : '?') + ' → Grupo ' + ondaDestino + ' em ' + (lc ? lc.campo : ''), 'edicao');
    gerarGrupos(); save();
    return { ok: true };
  }

  // CH semanal de PICO do aluno na PROJEÇÃO de grupos (caixas): entre todos os
  // grupos em que o aluno aparece, a MAIOR soma de horas/semana dos que se
  // sobrepõem no tempo. É o número que dá sentido ao teto de 30h no bootstrap.
  function chSemanaAlunoGrupos(alunoId) {
    const meus = (S.grupos || [])
      .filter((g) => g.membros.some((m) => m.aluno_id === alunoId))
      .map((g) => ({ g, l: S.locais.find((x) => x.id === g.local_id) }))
      .filter((x) => x.l);
    let pico = 0;
    meus.forEach((base) => {
      const soma = meus
        .filter((o) => janelasSobrepoem(o.g.data_inicio, o.g.data_fim, base.g.data_inicio, base.g.data_fim))
        .reduce((s, o) => s + horasLocalSemana(o.l), 0);
      if (soma > pico) pico = soma;
    });
    return pico;
  }

  function horasCumpridasMatricula(mat) {
    const alocs = S.alocacoes.filter((a) => a.matricula_id === mat.id);
    let h = 0;
    alocs.forEach((a) => {
      S.sessoes.filter((s) => s.alocacao_id === a.id && s.status === 'cumprida').forEach((s) => h += s.horas);
    });
    return h;
  }

  // Contagem de encontros de uma matrícula: total (fixo, do espelho = local.numero_encontros)
  // e feitos (encontros já decorridos = presença assumida ± ajuste manual do professor).
  function encontrosMatricula(mat) {
    const alocs = S.alocacoes.filter((a) => a.matricula_id === mat.id && a.status !== 'cancelada');
    let total = 0, feitos = 0;
    alocs.forEach((a) => {
      const lc = S.locais.find((l) => l.id === a.local_id);
      const num = lc && lc.numero_encontros ? lc.numero_encontros : 0;
      const cumpridas = S.sessoes.filter((s) => s.alocacao_id === a.id && s.status === 'cumprida').length;
      let f = cumpridas + (a.ajuste_encontros || 0);
      if (f < 0) f = 0;
      if (f > num) f = num;
      total += num;
      feitos += f;
    });
    return { total, feitos };
  }

  // Ajuste manual do professor (cadastro): +1 = reforço, -1 = falta.
  // Mexe apenas no contador de encontros feitos, limitado a [0, total do espelho].
  function ajustarEncontros(alocacaoId, delta) {
    const aloc = S.alocacoes.find((a) => a.id === alocacaoId);
    if (!aloc) return;
    const lc = S.locais.find((l) => l.id === aloc.local_id);
    const total = lc && lc.numero_encontros ? lc.numero_encontros : 0;
    const cumpridas = S.sessoes.filter((s) => s.alocacao_id === aloc.id && s.status === 'cumprida').length;
    let feitos = cumpridas + (aloc.ajuste_encontros || 0) + delta;
    if (feitos < 0) feitos = 0;
    if (feitos > total) feitos = total;
    aloc.ajuste_encontros = feitos - cumpridas;
    atualizarConclusoes();
    registrarAtividade(delta > 0 ? 'Reforço: +1 encontro concedido' : 'Falta: -1 encontro registrado', 'edicao');
    save();
  }

  // ============================================================================
  //  AJUSTE MANUAL DA ESCALA (a saída do motor é uma sugestão editável).
  //  Não muda a modelagem: usa alocacoes + sessoes + `travada` (que já existem).
  //  Regra "avisa e deixa decidir": as funções aplicam; a UI mostra os avisos e
  //  confirma antes de chamar. Alocação manual nasce TRAVADA (o motor respeita).
  // ============================================================================
  function matConcluidaDaAloc(aloc) {
    const m = S.matriculas.find((mm) => mm.id === aloc.matricula_id);
    return !!(m && m.status === 'concluida');
  }
  // carga horária semanal já ocupada pelo aluno (só alocações ativas não concluídas)
  function horasSemanaAluno(alunoId) {
    let h = 0;
    S.alocacoes.filter((a) => a.aluno_id === alunoId && a.status === 'ativa' && !matConcluidaDaAloc(a)).forEach((a) => {
      const l = S.locais.find((x) => x.id === a.local_id); if (l) h += horasLocalSemana(l);
    });
    return h;
  }
  // Avalia um encaixe manual do aluno num local; devolve { ok, erro, avisos, mat }.
  // avisos = violações "brandas" (vaga/30h/horário/restrição) — não impedem.
  function avaliarAlocacaoManual(alunoId, localId) {
    const local = S.locais.find((l) => l.id === localId);
    if (!local) return { ok: false, erro: 'Local não encontrado.', avisos: [] };
    const mat = S.matriculas.find((m) => m.aluno_id === alunoId && m.area_id === local.area_id && m.status === 'em_andamento');
    if (!mat) return { ok: false, erro: 'O aluno não tem matrícula em andamento nesta área.', avisos: [] };
    if (S.alocacoes.some((a) => a.aluno_id === alunoId && a.local_id === localId && a.status === 'ativa')) {
      return { ok: false, erro: 'O aluno já está alocado neste local.', avisos: [] };
    }
    const avisos = [];
    const ocup = S.alocacoes.filter((a) => a.local_id === localId && a.status === 'ativa' && !matConcluidaDaAloc(a)).length;
    if (ocup >= local.capacidade) avisos.push('Vaga cheia (' + ocup + '/' + local.capacidade + ')');
    const h = horasSemanaAluno(alunoId) + horasLocalSemana(local);
    if (h > MAX_HORAS_SEMANAIS) avisos.push('Passa de ' + MAX_HORAS_SEMANAIS + 'h semanais (ficaria com ' + h + 'h)');
    const conflito = S.alocacoes.some((a) => a.aluno_id === alunoId && a.status === 'ativa' && (() => {
      const l = S.locais.find((x) => x.id === a.local_id); return l && l.dia_semana === local.dia_semana && l.turno === local.turno;
    })());
    if (conflito) avisos.push('Choque de horário no mesmo dia/turno');
    if (alunoBloqueadoNoLocal(alunoId, localId)) avisos.push('Local restrito para este aluno (condição especial)');
    return { ok: true, erro: null, avisos, mat };
  }
  // cria a alocação (uso interno) — sessões a partir de inicioMin (default: hoje)
  function criarAlocacao(alunoId, local, mat, inicioMin, travada) {
    const ciclo = cicloAtivo();
    const area = S.areas.find((a) => a.id === local.area_id);
    const ini = inicioMin || (hoje() > ciclo.data_inicio ? hoje() : ciclo.data_inicio);
    const alocId = uid('ao');
    const sess = gerarSessoes(alocId, local, area, ciclo, ini);
    const dataFim = sess.length ? sess[sess.length - 1].data : ini;
    S.alocacoes.push({
      id: alocId, aluno_id: alunoId, local_id: local.id, matricula_id: mat.id,
      data_inicio: sess.length ? sess[0].data : ini, data_fim_prevista: dataFim,
      travada: !!travada, status: 'ativa', ajuste_encontros: 0,
    });
    sess.forEach((s) => S.sessoes.push(s));
    mat.data_conclusao_prevista = dataFim;
    return alocId;
  }
  // Encaixe manual: cria a alocação TRAVADA, começando de agora. Não bloqueia por
  // regras (a UI já avisou/confirmou). Recalcula conclusões e grupos.
  function alocarManual(alunoId, localId) {
    const local = S.locais.find((l) => l.id === localId);
    const av = avaliarAlocacaoManual(alunoId, localId);
    if (!local || !av.ok) return null;
    const id = criarAlocacao(alunoId, local, av.mat, null, true);
    const al = S.alunos.find((a) => a.id === alunoId);
    atualizarConclusoes(); gerarGrupos();
    registrarAtividade('Alocação manual: ' + (al ? al.nome : '') + ' em ' + local.campo, 'edicao');
    save();
    return id;
  }
  // Remove o aluno de um local (cancela a alocação e as sessões futuras). A
  // matrícula continua em_andamento → o aluno volta à fila; a vaga é liberada.
  function removerAlocacao(alocacaoId) {
    const a = S.alocacoes.find((x) => x.id === alocacaoId);
    if (!a || a.status !== 'ativa') return;
    a.status = 'cancelada';
    S.sessoes.filter((s) => s.alocacao_id === a.id && s.status === 'prevista').forEach((s) => { s.status = 'cancelada'; });
    const al = S.alunos.find((x) => x.id === a.aluno_id);
    const l = S.locais.find((x) => x.id === a.local_id);
    atualizarConclusoes(); gerarGrupos();
    registrarAtividade('Aluno removido do local (manual): ' + (al ? al.nome : '') + ' / ' + (l ? l.campo : ''), 'edicao');
    save();
  }
  // Move um aluno para outro local da mesma área (cancela a atual e recria).
  // Mantém, quando possível, a data de início original (mesma "janela").
  function moverAlocacao(alocacaoId, novoLocalId) {
    const a = S.alocacoes.find((x) => x.id === alocacaoId);
    const novo = S.locais.find((l) => l.id === novoLocalId);
    if (!a || a.status !== 'ativa' || !novo) return null;
    const mat = S.matriculas.find((m) => m.id === a.matricula_id);
    if (!mat || mat.area_id !== novo.area_id) return null; // só dentro da mesma área
    const iniOrig = a.data_inicio;
    a.status = 'cancelada';
    S.sessoes.filter((s) => s.alocacao_id === a.id && s.status === 'prevista').forEach((s) => { s.status = 'cancelada'; });
    const inicioMin = iniOrig && iniOrig > hoje() ? iniOrig : hoje();
    const id = criarAlocacao(a.aluno_id, novo, mat, inicioMin, true);
    const al = S.alunos.find((x) => x.id === a.aluno_id);
    atualizarConclusoes(); gerarGrupos();
    registrarAtividade('Aluno movido (manual): ' + (al ? al.nome : '') + ' → ' + novo.campo, 'edicao');
    save();
    return id;
  }
  // Atalho "concluir grupo": completa os encontros de toda a leva atual de um local
  // (feitos = total) → conclui as áreas e libera as vagas para a próxima turma.
  function concluirGrupoLocal(localId) {
    const local = S.locais.find((l) => l.id === localId);
    if (!local) return;
    const total = local.numero_encontros || 0;
    S.alocacoes.filter((a) => a.local_id === localId && a.status === 'ativa').forEach((a) => {
      const m = S.matriculas.find((mm) => mm.id === a.matricula_id);
      if (!m || m.status !== 'em_andamento') return;
      const cumpridas = S.sessoes.filter((s) => s.alocacao_id === a.id && s.status === 'cumprida').length;
      a.ajuste_encontros = Math.max(0, total - cumpridas); // feitos = total → conclui
    });
    atualizarConclusoes(); gerarGrupos();
    registrarAtividade('Grupo concluído (manual): ' + local.campo, 'edicao');
    save();
  }

  // ---- Desmatrícula (interrupção do estágio) --------------------------------
  // Ação do dia a dia: o aluno para o estágio de uma área por motivo
  // extraordinário (ex.: saúde). NÃO apaga a matrícula (preserva histórico):
  //   • matrícula vira 'interrompida' (com motivo + data);
  //   • a alocação ativa é cancelada e as sessões FUTURAS também
  //     (as já cumpridas ficam como registro);
  //   • a vaga é liberada (deixa de ocupar) → a fila anda ao regenerar a escala;
  //   • marca a escala como desatualizada e registra na atividade.
  // No encerramento a área fica 'pendente'; no próximo ciclo volta como
  // 'em_andamento' (carry-forward) para ser refeita.
  function desmatricular(alunoId, areaId, motivo) {
    const mat = S.matriculas.find((m) => m.aluno_id === alunoId && m.area_id === areaId && m.status === 'em_andamento');
    if (!mat) return false;
    mat.status = 'interrompida';
    mat.motivo_interrupcao = motivo || null;
    mat.data_interrupcao = hoje();
    mat.data_conclusao_prevista = null;
    S.alocacoes.filter((a) => a.matricula_id === mat.id && a.status === 'ativa').forEach((a) => {
      a.status = 'cancelada';
      S.sessoes.filter((s) => s.alocacao_id === a.id && s.status === 'prevista').forEach((s) => { s.status = 'cancelada'; });
    });
    const aluno = S.alunos.find((a) => a.id === alunoId);
    const area = S.areas.find((a) => a.id === areaId);
    const nomeAluno = aluno ? aluno.nome : '?';
    const nomeArea = area ? area.nome : '?';
    marcarDesatualizada('Vaga liberada em ' + nomeArea + ' — ' + nomeAluno + ' interrompeu' + (motivo ? ' (' + motivo + ')' : ''));
    registrarAtividade('Estágio interrompido: ' + nomeAluno + ' — ' + nomeArea + (motivo ? ' · ' + motivo : ''), 'edicao');
    save();
    return true;
  }

  // Horas a exibir/creditar: área concluída conta a carga cheia — inclusive as
  // carregadas de ciclos/semestres anteriores (sem sessões neste ciclo).
  function horasCreditadas(mat, area) {
    if (mat.status === 'concluida') return area ? area.carga_exigida : horasCumpridasMatricula(mat);
    return horasCumpridasMatricula(mat);
  }

  // Áreas aplicáveis à fase do aluno (7º = pré-requisito/Audiologia I; 9º/10º = as demais).
  // Sempre áreas LEAF — o container composto (ex.: Audiologia II) não é matriculável.
  function areasDaFase(aluno) {
    const fase5 = aluno && +aluno.semestre <= 7;
    return S.areas.filter((a) => !a.composta && (fase5 ? a.pre_requisito : !a.pre_requisito));
  }
  function preRequisitoConcluido(alunoId) {
    const pre = S.areas.find((a) => a.pre_requisito);
    if (!pre) return true;
    return S.matriculas.some((m) => m.aluno_id === alunoId && m.area_id === pre.id && m.status === 'concluida');
  }

  // ============================================================================
  //  OPERAÇÃO — flag de desatualização + fila de remanejo
  // ============================================================================
  function marcarDesatualizada(gatilho) {
    const c = cicloAtivo();
    if (!c || c.status !== 'em_andamento') return;
    c.escala_desatualizada = true;
    S.fila_remanejo.push({ id: uid('gt'), quando: hoje(), texto: gatilho });
  }
  function registrarAtividade(texto, tipo) {
    S.atividade.unshift({ id: uid('at'), quando: hoje(), texto, tipo: tipo || 'edicao' });
    if (S.atividade.length > 40) S.atividade.pop();
  }

  // §13.1 — áreas com VAGA LIVRE e FILA esperando (tipicamente conclusão liberou vaga).
  // O painel usa para alertar; o remanejo materializa a fila (aguardando → em andamento).
  function vagasLivresComFila() {
    return ofertaDemandaAreas()
      .filter((d) => d.vagasLivres > 0 && d.fila.length > 0)
      .map((d) => ({ area: d.area, vagasLivres: d.vagasLivres, fila: d.fila.length }));
  }
  // Registra o gatilho de remanejamento por vaga-livre-com-fila (§13.1), sem duplicar.
  function sinalizarVagasLivres() {
    let n = 0;
    vagasLivresComFila().forEach((v) => {
      const marca = 'Vaga livre com fila em ' + v.area.nome;
      if (!S.fila_remanejo.some((g) => g.texto.indexOf(marca) === 0)) {
        marcarDesatualizada(marca + ' (' + v.fila + ' aguardando · conclusão liberou vaga)');
        n++;
      }
    });
    if (n) save();
    return n;
  }
  // Plano (sem persistir) de quem da fila entra em vaga livre, por prioridade, respeitando
  // capacidade, conflito de dia/turno, restrição de local (§6.2) e teto de 30h (§7.4).
  function _planejarMaterializacao() {
    const plano = [];
    const capUso = {}, commit = {}, horas = {};
    S.alocacoes.filter((a) => a.status === 'ativa').forEach((a) => {
      const l = S.locais.find((x) => x.id === a.local_id); if (!l) return;
      if (!matConcluidaDaAloc(a)) capUso[l.id] = (capUso[l.id] || 0) + 1;
      (commit[a.aluno_id] = commit[a.aluno_id] || []).push({ dia: l.dia_semana, turno: l.turno });
      horas[a.aluno_id] = (horas[a.aluno_id] || 0) + horasLocalSemana(l);
    });
    S.alunos.slice().sort((a, b) => a.ordenamento - b.ordenamento).forEach((al) => {
      S.matriculas.filter((m) => m.aluno_id === al.id && m.status === 'em_andamento' &&
          !S.alocacoes.some((a) => a.matricula_id === m.id && a.status === 'ativa')).forEach((mat) => {
        const alvo = S.locais.filter((l) => l.area_id === mat.area_id && l.ativo && !alunoBloqueadoNoLocal(al.id, l.id))
          .find((l) => (capUso[l.id] || 0) < l.capacidade &&
            !(commit[al.id] || []).some((cm) => cm.dia === l.dia_semana && cm.turno === l.turno) &&
            (horas[al.id] || 0) + horasLocalSemana(l) <= MAX_HORAS_SEMANAIS);
        if (alvo) {
          plano.push({ alunoId: al.id, mat, local: alvo });
          capUso[alvo.id] = (capUso[alvo.id] || 0) + 1;
          (commit[al.id] = commit[al.id] || []).push({ dia: alvo.dia_semana, turno: alvo.turno });
          horas[al.id] = (horas[al.id] || 0) + horasLocalSemana(alvo);
        }
      });
    });
    return plano;
  }

  // Pré-visualização do remanejo (números derivados dos gatilhos e das sessões futuras)
  function previewRemanejo() {
    const h = hoje();
    const futuras = S.sessoes.filter((s) => s.status === 'prevista' && s.data >= h);
    // sessões afetadas: as que caem em datas de evento bloqueante, afastamento ou local indisponível
    const afetadas = futuras.filter((s) => {
      const aloc = S.alocacoes.find((a) => a.id === s.alocacao_id);
      if (!aloc || aloc.travada) return false;
      const local = S.locais.find((l) => l.id === aloc.local_id);
      if (!local) return false;
      return eventoBloqueiaEm(s.data) || localSemCoberturaEm(local, s.data) || localIndisponivelEm(local.id, s.data) || !local.ativo;
    });
    // realocações de cenário: alocações cujo local ficou inativo
    const realoc = S.alocacoes.filter((a) => !a.travada && a.status === 'ativa' && (() => {
      const l = S.locais.find((x) => x.id === a.local_id); return l && !l.ativo;
    })());
    // fila que ENTRA em vaga livre (§13.1) e a que SEGUE sem vaga (conflito/restrição/30h)
    const plano = _planejarMaterializacao();
    const planoMatIds = new Set(plano.map((p) => p.mat.id));
    const semVaga = S.matriculas.filter((m) => m.status === 'em_andamento' &&
      !S.alocacoes.some((a) => a.matricula_id === m.id && a.status === 'ativa') && !planoMatIds.has(m.id));
    const alunosAfetados = new Set();
    afetadas.forEach((s) => { const a = S.alocacoes.find((x) => x.id === s.alocacao_id); if (a) alunosAfetados.add(a.aluno_id); });
    realoc.forEach((a) => alunosAfetados.add(a.aluno_id));
    plano.forEach((p) => alunosAfetados.add(p.alunoId));

    return {
      gatilhos: S.fila_remanejo.slice(),
      sessoes_movidas: afetadas.length,
      realocadas: realoc.length,
      fila_materializavel: plano.length,
      sem_vaga: semVaga.map((m) => {
        const al = S.alunos.find((a) => a.id === m.aluno_id);
        const ar = S.areas.find((a) => a.id === m.area_id);
        return { aluno: al ? al.nome : '?', area: ar ? ar.nome : '?' };
      }),
      alunos_afetados: alunosAfetados.size,
      afetadasIds: afetadas.map((s) => s.id),
    };
  }

  // aplica: empurra sessões afetadas para a próxima semana livre; limpa a flag
  function aplicarRemanejo() {
    const prev = previewRemanejo();
    const c = cicloAtivo();
    prev.afetadasIds.forEach((sid) => {
      const s = S.sessoes.find((x) => x.id === sid);
      if (!s) return;
      const aloc = S.alocacoes.find((a) => a.id === s.alocacao_id);
      const local = aloc ? S.locais.find((l) => l.id === aloc.local_id) : null;
      let novaData = addDays(s.data, 7);
      let guard = 0;
      while (guard < 20 && novaData <= c.data_fim &&
             (eventoBloqueiaEm(novaData) || (local && (localSemCoberturaEm(local, novaData) || localIndisponivelEm(local.id, novaData))))) {
        novaData = addDays(novaData, 7); guard++;
      }
      s.status = 'remanejada';
      // cria uma nova sessão na data livre
      S.sessoes.push({ id: uid('ss'), alocacao_id: s.alocacao_id, data: novaData,
        hora_inicio: s.hora_inicio, hora_fim: s.hora_fim, horas: s.horas, status: 'prevista' });
      if (aloc) { aloc.data_fim_prevista = novaData > aloc.data_fim_prevista ? novaData : aloc.data_fim_prevista; }
    });
    // §13.1 — materializa a fila em vagas livres (aguardando → em andamento), por prioridade
    const plano = _planejarMaterializacao();
    plano.forEach((p) => criarAlocacao(p.alunoId, p.local, p.mat, null, false));
    // recalcula previsão das matrículas
    S.matriculas.forEach((m) => {
      const alocs = S.alocacoes.filter((a) => a.matricula_id === m.id);
      let max = null;
      alocs.forEach((a) => { if (!max || a.data_fim_prevista > max) max = a.data_fim_prevista; });
      if (max) m.data_conclusao_prevista = max;
    });
    c.escala_desatualizada = false;
    S.fila_remanejo = [];
    registrarAtividade('Remanejamento aplicado: ' + prev.sessoes_movidas + ' sessões movidas' +
      (plano.length ? ' · ' + plano.length + ' da fila em andamento' : ''), 'remanejo');
    atualizarConclusoes();
    gerarGrupos();
    save();
    return prev;
  }

  // ---- Encerramento de ciclo -----------------------------------------------
  function encerrarCiclo() {
    const c = cicloAtivo();
    if (!c) return;
    const ano = parse(c.data_inicio).getFullYear();
    S.alunos.forEach((al) => {
      const mats = S.matriculas.filter((m) => m.aluno_id === al.id);
      // o retrato guarda apenas as áreas do PLANO do aluno (as que ele foi matriculado
      // neste ciclo). Áreas não selecionadas ("não faz neste ciclo") NÃO entram e não
      // viram pendência no histórico.
      const areasFase = areasDaFase(al).filter((ar) => mats.some((m) => m.area_id === ar.id));
      const snap = areasFase.map((ar) => {
        const mat = mats.find((m) => m.area_id === ar.id);
        const horas = mat ? horasCreditadas(mat, ar) : 0;
        return { nome: ar.nome, carga_exigida: ar.carga_exigida, horas_cumpridas: Math.round(horas),
          data_conclusao: mat && mat.status === 'concluida' ? mat.data_conclusao : null };
      });
      const concluidas = snap.filter((s) => s.data_conclusao).length;
      // completo = concluiu TODAS as áreas do plano (snap já é só o plano)
      S.historico.push({
        id: uid('hs'), ano, ciclo_id: c.id, aluno_nome: al.nome, matricula: al.matricula,
        areas: snap, carga_horaria_total: snap.reduce((a, s) => a + s.horas_cumpridas, 0),
        situacao: concluidas === snap.length ? 'ciclo_completo' : 'pendente',
        encerramento: hoje(), criado_em: hoje(),
      });
    });
    c.status = 'encerrado';
    c.encerrado_em = hoje();
    c.escala_desatualizada = false;
    save();
    return ano;
  }

  // ---- Estatísticas de progresso do aluno (para detalhe e painel) ----------
  function progressoAluno(alunoId) {
    const ciclo = cicloAtivo();
    const h = hoje();
    const aluno = S.alunos.find((a) => a.id === alunoId);
    const mats = S.matriculas.filter((m) => m.aluno_id === alunoId);
    // apenas as áreas da fase do aluno entram no progresso (5º = Audiologia I; 6/7 = as demais)
    const areasFase = areasDaFase(aluno);
    const areasInfo = areasFase.map((ar) => {
      const mat = mats.find((m) => m.area_id === ar.id);
      if (!mat) return { area: ar, estado: 'iniciar', horas: 0, prevista: null, encontros: { total: 0, feitos: 0 }, pct: 0, alocado: false };
      const horas = horasCreditadas(mat, ar);
      // alocado = matrícula em andamento COM vaga ativa; em andamento SEM vaga = aguardando (na fila da área)
      const alocado = mat.status === 'em_andamento' && S.alocacoes.some((a) => a.matricula_id === mat.id && a.status === 'ativa');
      let estado;
      if (mat.status === 'concluida') estado = 'concluida';
      else if (mat.status === 'interrompida') estado = 'interrompida';
      else if (!alocado) estado = 'aguardando';
      else if (mat.data_conclusao_prevista && ciclo && mat.data_conclusao_prevista > ciclo.data_fim) estado = 'risco';
      else estado = 'andamento';
      const enc = encontrosMatricula(mat);
      // progresso por ENCONTROS (feitos/total); área concluída = 100%
      const pct = estado === 'concluida' ? 100 : (enc.total ? Math.round((enc.feitos / enc.total) * 100) : 0);
      return { area: ar, estado, horas: Math.round(horas), prevista: mat.data_conclusao_prevista, mat, encontros: enc, pct, alocado };
    });
    const totalExig = areasInfo.filter((a) => a.estado !== 'iniciar').reduce((s, a) => s + a.area.carga_exigida, 0);
    const totalCump = areasInfo.reduce((s, a) => s + a.horas, 0);
    const concl = areasInfo.filter((a) => a.estado === 'concluida').length;
    // distribuição por estado de alocação (para a lista de matriculados)
    const emAndamento = areasInfo.filter((a) => a.estado === 'andamento' || a.estado === 'risco').length;
    const aguardando = areasInfo.filter((a) => a.estado === 'aguardando').length;
    const risco = areasInfo.some((a) => a.estado === 'risco');
    const diasRest = ciclo ? Math.max(0, diffDays(h, ciclo.data_fim)) : 0;
    // progresso geral por encontros: média das áreas que o aluno cursa (com matrícula)
    const comMat = areasInfo.filter((a) => a.estado !== 'iniciar');
    const pctCarga = comMat.length ? Math.round(comMat.reduce((s, a) => s + a.pct, 0) / comMat.length) : 0;
    // encontros somados (para exibição de total da turma / aluno)
    const encTotais = areasInfo.reduce((acc, a) => { acc.total += a.encontros.total; acc.feitos += a.encontros.feitos; return acc; }, { total: 0, feitos: 0 });
    // pré-requisito (Audiologia I): relevante só para 9º/10º
    const preReqArea = S.areas.find((a) => a.pre_requisito);
    const fase5 = aluno && +aluno.semestre <= 7;
    const preReqConcluido = preRequisitoConcluido(alunoId);
    // total do PLANO do aluno = só as áreas matriculadas (as não selecionadas não são
    // pendência — ficam "não faz neste ciclo"). Completo = concluiu tudo do plano.
    const noPlano = areasInfo.filter((a) => a.estado !== 'iniciar').length;
    return { areasInfo, totalExig, totalCump, concluidas: concl, totalAreas: noPlano, totalAreasFase: areasFase.length,
      emAndamento, aguardando, risco, diasRest, fase5, preReqArea, preReqConcluido, encontros: encTotais, pctCarga };
  }

  function alunosEmRisco() {
    return S.alunos.filter((a) => progressoAluno(a.id).risco).length;
  }

  // A prioridade (ordenamento) é POR FASE: cada fase (7º = Audiologia I · 9/10 =
  // demais) tem sua própria sequência 1..k. As duas fases nunca disputam o mesmo
  // local, então numerá-las de forma independente é seguro e mais intuitivo p/ a
  // coordenação ("nesta fase, fulano é o 3º").
  function faseDoAluno(al) { return +al.semestre <= 7 ? '7' : '9_10'; }
  // Reindexa cada fase para 1..k preservando a ordem relativa (chamado após remover).
  function reindexarOrdenamento() {
    ['7', '9_10'].forEach((f) => {
      S.alunos.filter((a) => faseDoAluno(a) === f).sort((a, b) => a.ordenamento - b.ordenamento)
        .forEach((al, i) => { al.ordenamento = i + 1; });
    });
  }
  // Define a ordem de uma fase a partir da lista de ids na ordem desejada (drag-and-drop
  // no passo Alunos). Atribui 1..k; quem ficar de fora entra no fim.
  function reordenarAlunosFase(orderedIds) {
    let i = 1;
    orderedIds.forEach((id) => { const al = S.alunos.find((a) => a.id === id); if (al) al.ordenamento = i++; });
    save();
  }
  // Move um aluno para a posição `pos` (1..k) DENTRO da sua fase — usado pelo campo
  // numérico do passo Alunos (alternativa ao arrastar, p/ quem prefere digitar).
  function definirPosicaoAluno(alunoId, pos) {
    const al = S.alunos.find((a) => a.id === alunoId); if (!al) return;
    const f = faseDoAluno(al);
    const ids = S.alunos.filter((a) => faseDoAluno(a) === f).sort((a, b) => a.ordenamento - b.ordenamento)
      .map((a) => a.id).filter((id) => id !== alunoId);
    const p = Math.max(1, Math.min((parseInt(pos, 10) || 1), ids.length + 1)); // clamp 1..k
    ids.splice(p - 1, 0, alunoId);
    ids.forEach((id, i) => { const x = S.alunos.find((a) => a.id === id); if (x) x.ordenamento = i + 1; });
    save();
  }

  // ---- Oferta × demanda por área (fila de espera + vagas sobrando) ----------
  // Tudo DERIVADO: capacidade vem de locais, ocupação de alocações ativas,
  // fila = matrículas em_andamento sem alocação ativa (ordenada por prioridade).
  function ofertaDemandaAreas() {
    const ciclo = cicloAtivo();
    return S.areas.filter((ar) => !ar.composta).map((ar) => {
      const locaisArea = S.locais.filter((l) => l.area_id === ar.id && l.ativo && (!ciclo || l.ciclo_id === ciclo.id));
      const localIds = new Set(locaisArea.map((l) => l.id));
      const capacidade = locaisArea.reduce((s, l) => s + l.capacidade, 0);
      // área concluída pelo aluno LIBERA a vaga (não ocupa mais) → a fila anda
      const ocupadas = S.alocacoes.filter((a) => {
        if (a.status !== 'ativa' || !localIds.has(a.local_id)) return false;
        const m = S.matriculas.find((mm) => mm.id === a.matricula_id);
        return !m || m.status !== 'concluida';
      }).length;
      const vagasLivres = Math.max(0, capacidade - ocupadas);
      const fila = S.matriculas
        .filter((m) => m.area_id === ar.id && m.status === 'em_andamento' &&
          !S.alocacoes.some((a) => a.matricula_id === m.id && a.status === 'ativa'))
        .map((m) => {
          const al = S.alunos.find((a) => a.id === m.aluno_id);
          return { nome: al ? al.nome : '?', ordenamento: al ? al.ordenamento : 999, desde: m.data_matricula || null };
        })
        .sort((a, b) => a.ordenamento - b.ordenamento);
      let situacao;
      if (vagasLivres === 0 && fila.length === 0) situacao = 'equilibrio';
      else if (vagasLivres === 0) situacao = 'reprimida';       // fila > 0, sem vaga
      else if (fila.length === 0) situacao = 'sobrando';        // vaga livre, ninguém na fila
      else situacao = 'ociosa_fila';                            // vaga E fila → conflito de horário
      return { area: ar, capacidade, ocupadas, vagasLivres, fila, situacao };
    });
  }

  // Previsão de INÍCIO por área (para o card da aba Ofertas).
  // Regra de negócio: o professor matricula o aluno nas áreas (todas de uma vez ou
  // só algumas, a critério dele); quem não cabe numa vaga fica na FILA. À medida
  // que os alocados concluem, a vaga LIBERA e o próximo da fila entra (isso é um
  // remanejamento). Aqui simulamos essa cascata: cada vaga carrega a data em que
  // libera; a fila (por prioridade) toma a que abrir primeiro, ocupa pelo tempo do
  // estágio (numero_encontros semanais) e assim libera para o seguinte.
  // É ESTIMATIVA — não é a saída do motor de escala.
  function previsaoInicioArea(areaId) {
    const ciclo = cicloAtivo();
    const h = hoje();
    const base = ciclo && ciclo.data_inicio > h ? ciclo.data_inicio : h; // início possível mais cedo
    const area = S.areas.find((a) => a.id === areaId);
    const locaisArea = S.locais.filter((l) => l.area_id === areaId && l.ativo && (!ciclo || l.ciclo_id === ciclo.id));
    const localIds = new Set(locaisArea.map((l) => l.id));
    const naoConcluida = (aloc) => {
      const m = S.matriculas.find((mm) => mm.id === aloc.matricula_id);
      return !m || m.status !== 'concluida';
    };

    // alocados atuais nesta área (área concluída ainda aparece, marcada como tal)
    const alocados = S.alocacoes
      .filter((a) => a.status === 'ativa' && localIds.has(a.local_id))
      .map((a) => {
        const al = S.alunos.find((x) => x.id === a.aluno_id);
        const m = S.matriculas.find((mm) => mm.id === a.matricula_id);
        const local = S.locais.find((l) => l.id === a.local_id);
        return {
          nome: al ? al.nome : '?', ordenamento: al ? al.ordenamento : 999,
          data_inicio: a.data_inicio, data_fim_prevista: a.data_fim_prevista,
          concluida: !!(m && m.status === 'concluida'),
          data_conclusao: m ? m.data_conclusao : null, local: local || null,
        };
      })
      .sort((x, y) => x.ordenamento - y.ordenamento);

    const capacidade = locaisArea.reduce((s, l) => s + l.capacidade, 0);
    const ocupadas = S.alocacoes.filter((a) => a.status === 'ativa' && localIds.has(a.local_id) && naoConcluida(a)).length;
    const vagasLivres = Math.max(0, capacidade - ocupadas);

    // vagas como "slots" com data de liberação: ocupada libera na conclusão prevista;
    // livre está disponível já. Cada slot guarda o tamanho do estágio do seu local.
    const slots = [];
    locaisArea.forEach((l) => {
      const ocupAtivos = S.alocacoes.filter((a) => a.status === 'ativa' && a.local_id === l.id && naoConcluida(a));
      ocupAtivos.forEach((a) => slots.push({ livreEm: a.data_fim_prevista || base, semanas: l.numero_encontros || 0, porConclusao: true }));
      const livres = Math.max(0, l.capacidade - ocupAtivos.length);
      for (let i = 0; i < livres; i++) slots.push({ livreEm: base, semanas: l.numero_encontros || 0, porConclusao: false });
    });

    const fimCiclo = ciclo ? ciclo.data_fim : null;
    const fila = S.matriculas
      .filter((m) => m.area_id === areaId && m.status === 'em_andamento' &&
        !S.alocacoes.some((a) => a.matricula_id === m.id && a.status === 'ativa'))
      .map((m) => {
        const al = S.alunos.find((a) => a.id === m.aluno_id);
        return { aluno_id: m.aluno_id, nome: al ? al.nome : '?', ordenamento: al ? al.ordenamento : 999 };
      })
      .sort((a, b) => a.ordenamento - b.ordenamento)
      .map((f) => {
        if (!slots.length) return { aluno_id: f.aluno_id, nome: f.nome, ordenamento: f.ordenamento, previsao: null, remanejamento: false, motivo: 'sem oferta ativa' };
        // slot que abre primeiro
        slots.sort((a, b) => (a.livreEm < b.livreEm ? -1 : a.livreEm > b.livreEm ? 1 : 0));
        const slot = slots[0];
        const entrada = slot.livreEm < base ? base : slot.livreEm;
        if (fimCiclo && entrada > fimCiclo) return { aluno_id: f.aluno_id, nome: f.nome, ordenamento: f.ordenamento, previsao: null, remanejamento: false, motivo: 'sem previsão neste ciclo' };
        const remanejamento = slot.porConclusao;               // entra porque alguém concluiu
        slot.livreEm = addDays(entrada, (slot.semanas || 1) * 7); // ocupa o slot → libera de novo depois
        slot.porConclusao = true;                                // próximo a pegar este slot também será remanejo
        return { aluno_id: f.aluno_id, nome: f.nome, ordenamento: f.ordenamento, previsao: entrada, remanejamento, motivo: null };
      });

    return { area, capacidade, ocupadas, vagasLivres, alocados, fila };
  }

  // ---- API pública ----------------------------------------------------------
  // ============================================================================
  //  PRIORIDADE + MONTAGEM MANUAL DO MOLDE (pré-montagem dos grupos no bootstrap)
  // ============================================================================
  // Em vez de ordenar todo mundo à mão, o professor MARCA quem tem prioridade
  // (aluno.prioridade). O `ordenamento` que o motor usa é DERIVADO: por fase,
  // primeiro os prioritários, depois o resto — ambos por ordem de matrícula. Assim
  // todos os sorts por ordenamento (fila/remanejo/geração) seguem valendo.
  function reindexPorPrioridade() {
    ['7', '9_10'].forEach((f) => {
      S.alunos.filter((a) => faseDoAluno(a) === f)
        .sort((a, b) => (Number(!!b.prioridade) - Number(!!a.prioridade)) || String(a.matricula || '').localeCompare(String(b.matricula || '')))
        .forEach((al, i) => { al.ordenamento = i + 1; });
    });
  }
  function togglePrioridade(alunoId, valor) {
    const al = S.alunos.find((a) => a.id === alunoId);
    if (!al) return;
    al.prioridade = valor === undefined ? !al.prioridade : !!valor;
    reindexPorPrioridade();
    save();
  }

  // Molde do ciclo SEM preencher: só as ondas (caixas) de cada slot ativo, com
  // datas e capacidade — para o professor montar à mão na tela de Montagem. Onde
  // houver pin (montagem manual), o aluno aparece na onda. NÃO toca alocações.
  function materializarMoldeVazio() {
    const ciclo = cicloAtivo();
    S.grupos = [];
    if (!ciclo) return S.grupos;
    S.locais.filter((l) => l.ativo).forEach((l) => {
      let ini = ciclo.data_inicio, onda = 0, guard = 0;
      while (guard++ < 60) {
        const fim = addDays(ini, duracaoOndaDias(l));
        if (fim > ciclo.data_fim) break;
        S.grupos.push({ id: uid('gp'), ciclo_id: ciclo.id, local_id: l.id, area_id: l.area_id,
          onda: ++onda, status: 'previsto', data_inicio: ini, data_fim: fim, membros: [] });
        ini = proximoInicioOnda(l, fim);
      }
    });
    // aplica os pins (montagem manual) SEM descartar as caixas vazias (o inverso do
    // aplicarTravasGrupos, que só serve quando o molde já veio preenchido pelo motor).
    (S.grupo_travas || []).forEach((t) => {
      const irmaos = S.grupos.filter((x) => x.local_id === t.local_id).sort((a, b) => a.onda - b.onda);
      const g = irmaos.find((x) => x.onda === t.onda) || irmaos[0];
      if (g && !g.membros.some((m) => m.aluno_id === t.aluno_id)) g.membros.push({ aluno_id: t.aluno_id, aviso: null });
    });
    return S.grupos;
  }

  // CH somada de um aluno = soma da carga_horaria das áreas dos grupos onde está.
  function chSomadaAluno(alunoId) {
    return (S.grupos || []).filter((g) => g.membros.some((m) => m.aluno_id === alunoId))
      .reduce((s, g) => { const l = S.locais.find((x) => x.id === g.local_id); return s + (l ? (l.carga_horaria || 0) : 0); }, 0);
  }
  // prioritários com ao menos UMA matrícula (área) ainda não colocada num grupo.
  function bancoPrioridade() {
    return S.alunos.filter((a) => {
      if (!a.prioridade) return false;
      const mats = S.matriculas.filter((m) => m.aluno_id === a.id && m.status === 'em_andamento');
      return mats.some((m) => !(S.grupo_travas || []).some((t) => {
        const l = S.locais.find((x) => x.id === t.local_id);
        return t.aluno_id === a.id && l && l.area_id === m.area_id;
      }));
    });
  }
  // coloca um aluno numa onda (grupo) do molde: 1 colocação por ÁREA (troca se já
  // havia noutro local da mesma área). Retorna motivo de recusa, ou null se ok.
  function colocarAlunoNoGrupo(alunoId, grupoId) {
    const g = (S.grupos || []).find((x) => x.id === grupoId); if (!g) return 'grupo inexistente';
    const local = S.locais.find((l) => l.id === g.local_id); if (!local) return 'local inexistente';
    if (g.membros.some((m) => m.aluno_id === alunoId)) return null; // já está aqui
    // só pode entrar numa área em que está MATRICULADO (cobre o mini-ciclo 7º: só Audiologia I)
    if (!S.matriculas.some((m) => m.aluno_id === alunoId && m.area_id === g.area_id && m.status === 'em_andamento'))
      return 'aluno não cursa esta área';
    if (g.membros.length >= local.capacidade) return 'caixa cheia';
    if (alunoBloqueadoNoLocal(alunoId, local.id)) return 'aluno restrito neste local';
    const locaisDaArea = S.locais.filter((l) => l.area_id === g.area_id).map((l) => l.id);
    // teto de 30h/semana: soma as horas semanais das colocações do aluno em OUTRAS áreas
    // cujas janelas se SOBREPÕEM à desta onda (área que já terminou libera a CH e não conta).
    const horasJanela = (S.grupos || []).filter((x) => !locaisDaArea.includes(x.local_id) &&
        x.membros.some((m) => m.aluno_id === alunoId) && janelasSobrepoem(x.data_inicio, x.data_fim, g.data_inicio, g.data_fim))
      .reduce((s, x) => { const lx = S.locais.find((y) => y.id === x.local_id); return s + (lx ? horasLocalSemana(lx) : 0); }, 0);
    if (horasJanela + horasLocalSemana(local) > MAX_HORAS_SEMANAIS) return 'passaria de ' + MAX_HORAS_SEMANAIS + 'h/semana (tire de outra caixa no × p/ liberar)';
    S.grupo_travas = (S.grupo_travas || []).filter((t) => !(t.aluno_id === alunoId && locaisDaArea.includes(t.local_id)));
    _pinGrupo(alunoId, g.local_id, g.onda);
    materializarMoldeVazio(); save();
    return null;
  }
  function removerAlunoDoGrupo(alunoId, grupoId) {
    const g = (S.grupos || []).find((x) => x.id === grupoId); if (!g) return;
    S.grupo_travas = (S.grupo_travas || []).filter((t) => !(t.aluno_id === alunoId && t.local_id === g.local_id));
    materializarMoldeVazio(); save();
  }

  window.State = {
    KEY, get: () => S, save, reset, onChange, uid,
    materializarMoldeVazio, chSomadaAluno, bancoPrioridade, colocarAlunoNoGrupo, removerAlunoDoGrupo, togglePrioridade, reindexPorPrioridade,
    hoje, iso, parse, addDays, diffDays, dentro,
    cicloAtivo, estadoInicial, abrirCiclo, setPassoBootstrap,
    gerarEscala, atualizarConclusoes, horasCumpridasMatricula, horasCreditadas,
    encontrosMatricula, ajustarEncontros, desmatricular,
    avaliarAlocacaoManual, alocarManual, removerAlocacao, moverAlocacao, concluirGrupoLocal,
    marcarDesatualizada, registrarAtividade, previewRemanejo, aplicarRemanejo,
    vagasLivresComFila, sinalizarVagasLivres,
    encerrarCiclo, progressoAluno, alunosEmRisco, ofertaDemandaAreas, previsaoInicioArea, reindexarOrdenamento, reordenarAlunosFase, definirPosicaoAluno,
    eventoBloqueiaEm, areasDaFase, preRequisitoConcluido, preceptorDoLocal, alunoBloqueadoNoLocal, gerarGrupos,
    grupoDoAluno, trocarAlunosGrupo, trocarGruposInteiros, destravarAlunoGrupo,
    avaliarMoverGrupo, moverAlunoGrupo, chSemanaAlunoGrupos,
  };

  load();
})();
