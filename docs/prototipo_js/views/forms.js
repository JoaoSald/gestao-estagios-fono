/* ============================================================================
   forms.js — Formulários compartilhados (bootstrap + operação).
   Cada "salvar" com o ciclo em andamento seta escala_desatualizada e enfileira
   o gatilho de remanejo; no bootstrap apenas grava.
   ============================================================================ */
(function () {
  'use strict';
  const { icon, esc } = window.UI;
  const S = window.State;
  window.Forms = {};

  function emOperacao() { const c = S.cicloAtivo(); return c && c.status === 'em_andamento'; }
  // TODA alteração no ciclo em andamento é um GATILHO de remanejo: seta escala_desatualizada
  // e enfileira o gatilho. A escala só é recalculada quando o usuário APLICA o remanejo
  // (revisão deliberada). No bootstrap (rascunho) apenas grava.
  function afterSave(gatilho, atividade) {
    if (emOperacao()) { S.marcarDesatualizada(gatilho); S.registrarAtividade(atividade || gatilho); }
    S.save();
    if (window.rerender) window.rerender();
  }

  function opt(v, label, sel) { return '<option value="' + v + '"' + (sel === v ? ' selected' : '') + '>' + esc(label) + '</option>'; }

  // Valor atual do select de preceptor de um local: "<tipo>:<id>" ou ''.
  function valorPreceptor(local) {
    return local && local.preceptor_id ? (local.preceptor_tipo || 'externo') + ':' + local.preceptor_id : '';
  }
  // Monta as <option>/<optgroup> do select de "preceptor de campo" de um local.
  // Agrupa preceptores externos (catálogo) e docentes (docente-como-preceptor).
  // incluirNovo: adiciona a opção "+ Novo preceptor externo…" (só no bootstrap).
  window.Forms.opcoesPreceptor = function (local, incluirNovo) {
    const st = S.get();
    const cur = valorPreceptor(local);
    const ehExt = local && local.preceptor_tipo !== 'docente';
    const ext = (st.preceptores || []).filter((p) => p.ativo || (ehExt && local && p.id === local.preceptor_id))
      .map((p) => opt('externo:' + p.id, p.nome, cur)).join('');
    const docs = st.docentes.filter((d) => d.ativo || (local && local.preceptor_tipo === 'docente' && d.id === local.preceptor_id))
      .map((d) => opt('docente:' + d.id, d.nome + ' (docente)', cur)).join('');
    return '<option value=""' + (cur ? '' : ' selected') + '>— nenhum (só o docente responde) —</option>' +
      '<optgroup label="Preceptores externos">' + (ext || '<option disabled>nenhum externo cadastrado</option>') + '</optgroup>' +
      '<optgroup label="Docentes (como preceptor)">' + docs + '</optgroup>' +
      (incluirNovo ? '<option value="__novo__">+ Novo preceptor externo…</option>' : '');
  };
  // Aplica o valor escolhido ao objeto local (não persiste — quem chama salva).
  window.Forms.aplicarPreceptor = function (local, value) {
    if (!value) { local.preceptor_id = null; local.preceptor_tipo = null; return; }
    const parts = value.split(':');
    local.preceptor_tipo = parts[0];
    local.preceptor_id = parts[1];
  };

  // ---------------------------------------------------------------- ALUNO ----
  //  Monta a lista de matrículas conforme a fase do semestre:
  //   • 7º semestre  → cursa só Audiologia I (pré-requisito).
  //   • 9º/10º       → cursa as demais; Audiologia I é responsabilidade compartilhada
  //                    (não bloqueia — só avisa para conferir).
  function checksMatriculas(semestre, mats, novoAluno) {
    const st = S.get();
    const fase5 = +semestre <= 7;
    const preReqArea = st.areas.find((a) => a.pre_requisito);
    const preReqMat = preReqArea ? mats.find((m) => m.area_id === preReqArea.id) : null;
    const preReqConcluida = !!(preReqMat && preReqMat.status === 'concluida');
    // só áreas MATRICULÁVEIS (leaf + simples) — o container composto não é matriculável;
    // o aluno cursa as sub-áreas dele (marcadas individualmente, com o nome da mãe).
    const areasFase = st.areas.filter((a) => (fase5 ? a.pre_requisito : !a.pre_requisito) && !a.composta);

    function pill(ar) {
      const mae = ar.area_mae ? ((st.areas.find((x) => x.id === ar.area_mae) || {}).nome || '') + ' - ' : '';
      return '<span class="area-pill" style="background:' + ar.cor + '22;color:' + ar.cor + '"><span class="dt" style="background:' + ar.cor + '"></span>' + esc(mae + ar.nome) + '</span>';
    }

    // §4: pré-requisito Audiologia I é responsabilidade COMPARTILHADA, não bloqueia.
    // Se não há registro de conclusão, apenas avisa para conferir — não trava a matrícula.
    let banner = '';
    if (!fase5 && preReqArea) {
      banner = '<div class="flex" style="gap:.6rem;align-items:center;margin-bottom:.7rem">' +
        (preReqConcluida
          ? '<span class="badge b-concluida"><span class="dt"></span>Pré-requisito ' + esc(preReqArea.nome) + ' concluído</span>'
          : '<span class="badge b-aguardando" title="Responsabilidade compartilhada: confira o histórico do aluno. Não bloqueia a matrícula."><span class="dt"></span>Sem registro de ' + esc(preReqArea.nome) + ' — conferir (não bloqueia)</span>') +
        '</div>';
    }

    const rows = areasFase.map((ar) => {
      const mat = mats.find((m) => m.area_id === ar.id);
      const concl = mat && mat.status === 'concluida';
      // aluno NOVO: 9/10 começa DESMARCADO — o professor escolhe o que o aluno faz neste
      // ciclo (não é "todos em tudo"). 7º pré-marca Audiologia I (única área da fase).
      // Ao editar, reflete as matrículas existentes. Esqueceu uma? matricula depois e o motor recalcula.
      const on = mat ? true : (!!novoAluno && fase5);
      // só a área já concluída trava o check; o pré-requisito não bloqueia (§4)
      const disabled = concl;
      return '<label class="check ' + (on ? 'on' : '') + '" data-area="' + ar.id + '">' +
        '<input type="checkbox" ' + (on ? 'checked' : '') + (disabled ? ' disabled' : '') + '>' + pill(ar) +
        (concl ? '<span class="badge b-concluida pull-right"><span class="dt"></span>concluída</span>' : '') +
      '</label>';
    }).join('');

    const dica = fase5
      ? 'Aluno do 7º semestre: mini-ciclo que cursa apenas o estágio de Audiologia I.'
      : 'Marque só os estágios que este aluno vai fazer NESTE ciclo. As demais não entram (não viram pendência) — se faltar, é só matricular depois e o motor recalcula.';
    return banner + '<div class="hint mb">' + dica + '</div><div class="checks">' + rows + '</div>';
  }

  //  Árvore de DISPONIBILIDADE POR LOCAL (restrições). Por padrão o aluno pode ir
  //  a todos os locais; desmarcar um local = restrição (o motor não o aloca lá).
  //  Agrupada por área; o checkbox da área liga/desliga todos os seus locais.
  function checksRestricoes(semestre, al) {
    const st = S.get();
    const fase5 = +semestre <= 7;
    const areasFase = st.areas.filter((a) => (fase5 ? a.pre_requisito : !a.pre_requisito));
    const bloq = (al && al.locais_bloqueados) || [];
    function pill(ar) {
      return '<span class="area-pill" style="background:' + ar.cor + '22;color:' + ar.cor + '"><span class="dt" style="background:' + ar.cor + '"></span>' + esc(ar.nome) + '</span>';
    }
    const secoes = areasFase.map((ar) => {
      const locais = st.locais.filter((l) => l.area_id === ar.id && l.ativo);
      if (!locais.length) return '';
      const allOn = locais.every((l) => bloq.indexOf(l.id) < 0);
      const items = locais.map((l) => {
        const disp = bloq.indexOf(l.id) < 0;
        return '<label class="check ' + (disp ? 'on' : '') + '" data-rl-loc-area="' + ar.id + '" data-rl-loc="' + l.id + '">' +
          '<input type="checkbox" class="rl-loc"' + (disp ? ' checked' : '') + '>' +
          '<span>' + esc(l.campo) + ' <span class="dim">· ' + window.UI.diasLabel(l) + ' · ' + window.UI.turnoLabel(l.turno) + '</span></span></label>';
      }).join('');
      return '<div class="rl-area" style="margin:.2rem 0 .7rem">' +
        '<label class="check ' + (allOn ? 'on' : '') + '" data-rl-area-all="' + ar.id + '" style="font-weight:600">' +
          '<input type="checkbox" class="rl-all"' + (allOn ? ' checked' : '') + '>' + pill(ar) + '</label>' +
        '<div class="checks" style="margin-left:1.1rem;margin-top:.35rem">' + items + '</div></div>';
    }).join('');
    return '<div class="hint mb">Por padrão o aluno pode ir a <b>todos</b> os locais. <b>Desmarque</b> os que ele NÃO pode frequentar (condição especial) — o motor não vai alocá-lo neles. Deixe ao menos um local por área matriculada.</div>' +
      (secoes || '<div class="dim">Nenhum local cadastrado ainda para a fase deste aluno.</div>');
  }

  window.Forms.aluno = function (id, done, defaults) {
    const st = S.get();
    const al = id ? st.alunos.find((a) => a.id === id) : null;
    const mats = al ? st.matriculas.filter((m) => m.aluno_id === al.id) : [];
    const semInicial = al ? al.semestre : ((defaults && defaults.semestre) || 9);
    // Encontros só aparecem ao editar um aluno já alocado (falta/reforço do professor).
    const temAloc = al && st.alocacoes.some((a) => a.aluno_id === al.id && a.status !== 'cancelada');

    window.UI.modal({
      titulo: al ? 'Editar aluno' : 'Novo aluno',
      wide: true,
      corpo:
        '<div class="form-grid">' +
          '<div class="field"><label>Nome</label><input class="input" id="f-nome" value="' + esc(al ? al.nome : '') + '"></div>' +
          '<div class="field"><label>Matrícula</label><input class="input" id="f-mat" value="' + esc(al ? al.matricula : '') + '"></div>' +
          '<div class="field"><label>E-mail</label><input class="input" type="email" id="f-email" value="' + esc(al && al.email ? al.email : '') + '" placeholder="matricula@aluno.ufcspa.edu.br"><div class="hint">Usado para as notificações do sistema.</div></div>' +
          '<div class="field"><label>Semestre</label><input class="input" type="number" min="1" id="f-sem" value="' + semInicial + '"><div class="hint">7º = mini-ciclo (Audiologia I) · 9º/10º = demais estágios</div></div>' +
        '</div>' +
        (al ? '' : '<p class="hint" style="margin:-.2rem 0 .6rem">A <b>prioridade</b> é marcada no passo Alunos (checkbox) — quem for prioridade você posiciona à mão na Montagem dos grupos; o resto o sistema aloca.</p>') +
        '<div class="field"><label>Matrículas iniciais por área</label>' +
          '<div id="area-checks">' + checksMatriculas(semInicial, mats, !al) + '</div></div>' +
        '<div class="field" style="border-top:1px solid var(--border);padding-top:1rem;margin-top:.4rem"><label>Disponibilidade por local (restrições)</label>' +
          '<div id="rl-checks">' + checksRestricoes(semInicial, al) + '</div></div>' +
        (temAloc
          ? '<div class="field" style="border-top:1px solid var(--border);padding-top:1rem;margin-top:.4rem">' +
              '<label>Encontros (faltas / reforços)</label>' +
              '<div id="enc-mng"></div></div>'
          : '') +
        '<div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="ok">' + icon('check') + ' Salvar</button>',
      onMount(el, close) {
        function bindChecks() {
          el.querySelectorAll('#area-checks .check[data-area]').forEach((c) => {
            const cb = c.querySelector('input');
            if (cb.disabled) return;
            cb.addEventListener('change', () => c.classList.toggle('on', cb.checked));
          });
        }
        bindChecks();
        // binding da árvore de disponibilidade por local (restrições)
        function syncAreaAll(arId) {
          const all = el.querySelector('[data-rl-area-all="' + arId + '"]');
          if (!all) return;
          const locs = el.querySelectorAll('[data-rl-loc-area="' + arId + '"] input.rl-loc');
          let todos = locs.length > 0;
          locs.forEach((cb) => { if (!cb.checked) todos = false; });
          const acb = all.querySelector('input'); acb.checked = todos; all.classList.toggle('on', todos);
        }
        function bindRestricoes() {
          el.querySelectorAll('#rl-checks .check[data-rl-loc]').forEach((lb) => {
            const cb = lb.querySelector('input');
            cb.addEventListener('change', () => { lb.classList.toggle('on', cb.checked); syncAreaAll(lb.getAttribute('data-rl-loc-area')); });
          });
          el.querySelectorAll('#rl-checks .check[data-rl-area-all]').forEach((lb) => {
            const cb = lb.querySelector('input');
            cb.addEventListener('change', () => {
              const arId = lb.getAttribute('data-rl-area-all');
              lb.classList.toggle('on', cb.checked);
              el.querySelectorAll('[data-rl-loc-area="' + arId + '"]').forEach((loc) => {
                const lcb = loc.querySelector('input'); lcb.checked = cb.checked; loc.classList.toggle('on', cb.checked);
              });
            });
          });
        }
        bindRestricoes();
        // seção de encontros (só quando o aluno já tem alocação): +/− ajustam na hora
        if (temAloc) renderEncontrosInto(el.querySelector('#enc-mng'), al.id);
        // re-renderiza a lista de áreas e de locais quando o semestre muda de fase
        el.querySelector('#f-sem').addEventListener('input', () => {
          const sem = +el.querySelector('#f-sem').value || 0;
          el.querySelector('#area-checks').innerHTML = checksMatriculas(sem, mats, !al);
          bindChecks();
          el.querySelector('#rl-checks').innerHTML = checksRestricoes(sem, al);
          bindRestricoes();
        });
        el.querySelector('#ok').addEventListener('click', () => {
          const nome = el.querySelector('#f-nome').value.trim();
          const matr = el.querySelector('#f-mat').value.trim();
          const email = el.querySelector('#f-email').value.trim();
          const err = el.querySelector('#err');
          if (!nome || !matr) { err.textContent = 'Nome e matrícula são obrigatórios.'; err.style.display = 'block'; return; }
          const dup = st.alunos.find((a) => a.matricula === matr && (!al || a.id !== al.id));
          if (dup) { err.textContent = 'Matrícula já usada por ' + dup.nome + '.'; err.style.display = 'block'; return; }
          // lê matrículas marcadas e locais bloqueados (desmarcados) ANTES de persistir
          const marcadas = new Set();
          el.querySelectorAll('.check[data-area]').forEach((c) => { if (c.querySelector('input').checked) marcadas.add(c.getAttribute('data-area')); });
          const bloqueados = [];
          el.querySelectorAll('#rl-checks .check[data-rl-loc]').forEach((lb) => { if (!lb.querySelector('input').checked) bloqueados.push(lb.getAttribute('data-rl-loc')); });
          // validação: cada área matriculada EM ANDAMENTO precisa de ≥1 local liberado
          const concluidas = mats.filter((m) => m.status === 'concluida').map((m) => m.area_id);
          const semLocal = [];
          marcadas.forEach((arId) => {
            if (concluidas.indexOf(arId) >= 0) return; // concluída não precisa de local
            const labels = el.querySelectorAll('#rl-checks .check[data-rl-loc-area="' + arId + '"]');
            if (!labels.length) return; // área sem local ofertado — não é problema de restrição
            let disp = 0; labels.forEach((lb) => { if (lb.querySelector('input').checked) disp++; });
            if (disp === 0) { const ar = st.areas.find((a) => a.id === arId); semLocal.push(ar ? ar.nome : arId); }
          });
          if (semLocal.length) {
            err.innerHTML = 'Sem local liberado em: <b>' + semLocal.map(esc).join(', ') + '</b>. Deixe ao menos um local disponível nessas áreas ou remova a matrícula.';
            err.style.display = 'block'; return;
          }
          const cid = S.cicloAtivo().id;
          let alunoId;
          const sem = +el.querySelector('#f-sem').value;
          if (al) {
            al.nome = nome; al.matricula = matr; al.email = email;
            al.semestre = sem; // ordenamento é controlado pela lista arrastável do passo Alunos
            al.locais_bloqueados = bloqueados;
            alunoId = al.id;
          } else {
            // aluno novo entra no FIM da fila da fase dele (7º vs 9/10)
            const mesmaFase = st.alunos.filter((a) => (sem <= 7) === (+a.semestre <= 7));
            const ord = mesmaFase.reduce((m, a) => Math.max(m, a.ordenamento || 0), 0) + 1;
            alunoId = S.uid('al');
            st.alunos.push({ id: alunoId, ciclo_id: cid, nome, matricula: matr, email,
              semestre: sem, ordenamento: ord, prioridade: false, locais_bloqueados: bloqueados, criado_em: S.hoje() });
          }
          // adiciona novas
          marcadas.forEach((arId) => {
            if (!st.matriculas.some((m) => m.aluno_id === alunoId && m.area_id === arId)) {
              st.matriculas.push({ id: S.uid('mt'), aluno_id: alunoId, area_id: arId, data_matricula: S.hoje(),
                status: 'em_andamento', data_conclusao_prevista: null, data_conclusao: null });
            }
          });
          // remove desmarcadas que não estão concluídas
          st.matriculas = st.matriculas.filter((m) => {
            if (m.aluno_id !== alunoId) return true;
            if (m.status === 'concluida') return true;
            return marcadas.has(m.area_id);
          });
          close();
          window.UI.toast(al ? 'Aluno atualizado — remanejo pendente' : 'Aluno cadastrado — remanejo pendente', 'success');
          // matrícula é um GATILHO: enfileira no Remanejo; a escala reflete ao APLICAR o remanejo.
          afterSave('Aluno ' + nome + ' alterado — alocação pendente', 'Aluno ' + (al ? 'editado' : 'cadastrado') + ': ' + nome);
          if (done) done(alunoId);
        });
      },
    });
  };

  // -------------------------------------------------------------- DOCENTE ----
  window.Forms.docente = function (id, done) {
    const st = S.get();
    const dc = id ? st.docentes.find((d) => d.id === id) : null;
    window.UI.modal({
      titulo: dc ? 'Editar docente' : 'Novo docente',
      corpo:
        '<div class="field"><label>Nome</label><input class="input" id="f-nome" value="' + esc(dc ? dc.nome : '') + '"></div>' +
        '<div class="field"><label>E-mail</label><input class="input" type="email" id="f-email" value="' + esc(dc && dc.email ? dc.email : '') + '" placeholder="nome@ufcspa.edu.br"><div class="hint">Usado para as notificações do sistema.</div></div>' +
        '<label class="check ' + (!dc || dc.ativo ? 'on' : '') + '" id="f-ativo-w"><input type="checkbox" id="f-ativo" ' + (!dc || dc.ativo ? 'checked' : '') + '><span>Docente ativo no ciclo</span></label>' +
        '<div class="hint mt-sm">Desligar um docente (desmarcar) com o ciclo em andamento marca a escala como desatualizada — as sessões futuras dele vão para a fila de remanejo.</div>' +
        '<div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="ok">' + icon('check') + ' Salvar</button>',
      onMount(el, close) {
        const w = el.querySelector('#f-ativo-w'); const cb = el.querySelector('#f-ativo');
        cb.addEventListener('change', () => w.classList.toggle('on', cb.checked));
        el.querySelector('#ok').addEventListener('click', () => {
          const nome = el.querySelector('#f-nome').value.trim();
          const email = el.querySelector('#f-email').value.trim();
          const err = el.querySelector('#err');
          if (!nome) { err.textContent = 'Informe o nome.'; err.style.display = 'block'; return; }
          const ativo = cb.checked;
          let desligado = false;
          if (dc) { desligado = dc.ativo && !ativo; dc.nome = nome; dc.email = email; dc.ativo = ativo; }
          else st.docentes.push({ id: S.uid('dc'), nome, email, ativo });
          close();
          window.UI.toast(dc ? 'Docente atualizado' : 'Docente cadastrado', 'success');
          afterSave(desligado ? 'Docente desligado: ' + nome + ' — realocar sessões futuras' : 'Docente ' + nome + ' alterado',
                    'Docente ' + (dc ? (desligado ? 'desligado' : 'editado') : 'cadastrado') + ': ' + nome);
          if (done) done();
        });
      },
    });
  };

  // ---------------------------------------------------------- AFASTAMENTO ----
  window.Forms.afastamento = function (id, done) {
    const st = S.get();
    const af = id ? st.afastamentos.find((a) => a.id === id) : null;
    const tipoPessoa = af && af.preceptor_id ? 'preceptor' : 'docente';
    const docsOpt = st.docentes.filter((d) => d.ativo || (af && d.id === af.docente_id))
      .map((d) => opt(d.id, d.nome, af && af.docente_id ? af.docente_id : '')).join('');
    const precsOpt = (st.preceptores || []).filter((p) => p.ativo || (af && p.id === af.preceptor_id))
      .map((p) => opt(p.id, p.nome, af && af.preceptor_id ? af.preceptor_id : '')).join('');
    window.UI.modal({
      titulo: af ? 'Editar afastamento' : 'Novo afastamento',
      corpo:
        '<div class="field"><label>Tipo de pessoa</label><select class="select" id="f-tp">' +
          opt('docente', 'Docente (UFCSPA)', tipoPessoa) + opt('preceptor', 'Preceptor (campo)', tipoPessoa) + '</select></div>' +
        '<div class="field" id="w-doc"' + (tipoPessoa === 'docente' ? '' : ' style="display:none"') + '><label>Docente</label><select class="select" id="f-doc">' + docsOpt + '</select></div>' +
        '<div class="field" id="w-prec"' + (tipoPessoa === 'preceptor' ? '' : ' style="display:none"') + '><label>Preceptor</label><select class="select" id="f-prec">' + precsOpt + '</select></div>' +
        '<div class="form-grid">' +
          '<div class="field"><label>Tipo</label><select class="select" id="f-tipo">' +
            opt('ferias', 'Férias', af ? af.tipo : '') + opt('licenca', 'Licença', af ? af.tipo : '') + opt('outro', 'Outro', af ? af.tipo : '') + '</select></div>' +
          '<div class="field"><label>Motivo</label><input class="input" id="f-mot" value="' + esc(af ? af.motivo : '') + '" placeholder="ex.: congresso, atestado…"></div>' +
          '<div class="field"><label>Início</label><input class="input" type="date" id="f-ini" value="' + (af ? af.data_inicio : '') + '"></div>' +
          '<div class="field"><label>Retorno</label><input class="input" type="date" id="f-ret" value="' + (af ? af.data_retorno : '') + '"></div>' +
        '</div><div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="ok">' + icon('check') + ' Salvar</button>',
      onMount(el, close) {
        const tp = el.querySelector('#f-tp');
        tp.addEventListener('change', () => {
          const ehDoc = tp.value === 'docente';
          el.querySelector('#w-doc').style.display = ehDoc ? '' : 'none';
          el.querySelector('#w-prec').style.display = ehDoc ? 'none' : '';
        });
        el.querySelector('#ok').addEventListener('click', () => {
          const ehDoc = tp.value === 'docente';
          const pessoa = ehDoc ? el.querySelector('#f-doc').value : el.querySelector('#f-prec').value;
          const ini = el.querySelector('#f-ini').value, ret = el.querySelector('#f-ret').value;
          const err = el.querySelector('#err');
          if (!pessoa || !ini || !ret) { err.textContent = (ehDoc ? 'Docente' : 'Preceptor') + ', início e retorno são obrigatórios.'; err.style.display = 'block'; return; }
          if (ret < ini) { err.textContent = 'O retorno deve ser igual ou posterior ao início.'; err.style.display = 'block'; return; }
          const tipo = el.querySelector('#f-tipo').value, mot = el.querySelector('#f-mot').value.trim();
          const alvo = { docente_id: ehDoc ? pessoa : null, preceptor_id: ehDoc ? null : pessoa, tipo, motivo: mot, data_inicio: ini, data_retorno: ret };
          if (af) Object.assign(af, alvo);
          else st.afastamentos.push(Object.assign({ id: S.uid('af'), ciclo_id: S.cicloAtivo().id, criado_em: S.hoje() }, alvo));
          const pnome = ehDoc
            ? ((st.docentes.find((d) => d.id === pessoa) || {}).nome || '')
            : (((st.preceptores || []).find((p) => p.id === pessoa) || {}).nome || '');
          close();
          window.UI.toast(af ? 'Afastamento atualizado' : 'Afastamento cadastrado', 'success');
          afterSave('Afastamento de ' + pnome + ' (' + ini + '→' + ret + ')', 'Afastamento ' + (af ? 'editado' : 'cadastrado') + ': ' + pnome);
          if (done) done();
        });
      },
    });
  };

  // ------------------------------------------------------------- PRECEPTOR ----
  //  Responsável de campo, externo à UFCSPA. Sem login institucional: a conta
  //  é gerada a partir do e-mail (por isso o e-mail é obrigatório).
  window.Forms.preceptor = function (id, done) {
    const st = S.get();
    const pc = id ? (st.preceptores || []).find((p) => p.id === id) : null;
    window.UI.modal({
      titulo: pc ? 'Editar preceptor' : 'Novo preceptor',
      corpo:
        '<div class="field"><label>Nome</label><input class="input" id="f-nome" value="' + esc(pc ? pc.nome : '') + '" placeholder="Fga. Nome Sobrenome"></div>' +
        '<div class="field"><label>E-mail</label><input class="input" type="email" id="f-email" value="' + esc(pc && pc.email ? pc.email : '') + '" placeholder="nome@email.com"><div class="hint">Obrigatório — é a conta do preceptor (sem login institucional) e o destino das notificações.</div></div>' +
        '<label class="check ' + (!pc || pc.ativo ? 'on' : '') + '" id="f-ativo-w"><input type="checkbox" id="f-ativo" ' + (!pc || pc.ativo ? 'checked' : '') + '><span>Preceptor ativo</span></label>' +
        '<div class="hint mt-sm">Desligar um preceptor com o ciclo em andamento marca a escala como desatualizada — os locais em que ele é responsável entram na fila de remanejo.</div>' +
        '<div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="ok">' + icon('check') + ' Salvar</button>',
      onMount(el, close) {
        const w = el.querySelector('#f-ativo-w'); const cb = el.querySelector('#f-ativo');
        cb.addEventListener('change', () => w.classList.toggle('on', cb.checked));
        el.querySelector('#ok').addEventListener('click', () => {
          const nome = el.querySelector('#f-nome').value.trim();
          const email = el.querySelector('#f-email').value.trim();
          const err = el.querySelector('#err');
          if (!nome) { err.textContent = 'Informe o nome.'; err.style.display = 'block'; return; }
          if (!email) { err.textContent = 'O e-mail é obrigatório (é a conta do preceptor).'; err.style.display = 'block'; return; }
          const ativo = cb.checked;
          if (!st.preceptores) st.preceptores = [];
          let desligado = false;
          let pcId;
          if (pc) { desligado = pc.ativo && !ativo; pc.nome = nome; pc.email = email; pc.ativo = ativo; pcId = pc.id; }
          else { pcId = S.uid('pc'); st.preceptores.push({ id: pcId, nome, email, ativo }); }
          close();
          window.UI.toast(pc ? 'Preceptor atualizado' : 'Preceptor cadastrado', 'success');
          afterSave(desligado ? 'Preceptor desligado: ' + nome + ' — realocar sessões futuras' : 'Preceptor ' + nome + ' alterado',
                    'Preceptor ' + (pc ? (desligado ? 'desligado' : 'editado') : 'cadastrado') + ': ' + nome);
          if (done) done(pcId);
        });
      },
    });
  };

  // ------------------------------------------------------------------- ÁREA ----
  //  Cadastro de área com SUB-ÁREAS inline. Uma área com ≥1 sub-área vira COMPOSTA
  //  (container, não matriculável): a CH total é da mãe e as sub-áreas somam esse total.
  //  Sem sub-áreas = área simples (o aluno cumpre em qualquer local dela).
  window.Forms.area = function (id, done) {
    const st = S.get();
    const ar = id ? st.areas.find((a) => a.id === id) : null;
    const faseV = ar ? ar.fase : '9_10';
    // lista de sub-áreas em memória (commit no Salvar): {id?, nome, ch}
    const subs = ar ? st.areas.filter((a) => a.area_mae === ar.id).map((a) => ({ id: a.id, nome: a.nome, ch: a.carga_exigida })) : [];

    window.UI.modal({
      titulo: ar ? 'Editar área' : 'Nova área',
      wide: true,
      corpo:
        '<div class="form-grid">' +
          '<div class="field"><label>Nome</label><input class="input" id="f-anome" value="' + esc(ar ? ar.nome : '') + '" placeholder="ex.: Audiologia II ou Voz"></div>' +
          '<div class="field"><label>Carga horária total (h)</label><input class="input" type="number" min="1" id="f-ach" value="' + (ar ? ar.carga_exigida : 60) + '"></div>' +
          '<div class="field"><label>Fase</label><select class="select" id="f-afase">' + opt('7', '7º (Audiologia I)', faseV) + opt('9_10', '9º/10º (demais)', faseV) + '</select></div>' +
        '</div>' +
        '<label class="check ' + (ar && ar.pre_requisito ? 'on' : '') + '" id="f-apre-w"><input type="checkbox" id="f-apre" ' + (ar && ar.pre_requisito ? 'checked' : '') + '><span>É pré-requisito (Audiologia I) — não bloqueia, só avisa</span></label>' +
        '<div class="field" style="border-top:1px solid var(--border);padding-top:.9rem;margin-top:.6rem">' +
          '<div class="flex between" style="align-items:center;margin-bottom:.4rem"><label style="margin:0">Sub-áreas (opcional — obrigatórias, com CH que somam o total)</label>' +
            '<button class="btn btn-secondary btn-sm" id="add-sub">' + icon('plus') + ' Adicionar sub-área</button></div>' +
          '<div id="subs-list"></div>' +
          '<div class="hint" id="sub-sum" style="margin-top:.3rem"></div>' +
          '<div class="hint">Sem sub-áreas = área simples (cumpre em qualquer local). Com sub-áreas = composta (o aluno cumpre cada uma).</div>' +
        '</div>' +
        '<div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button><button class="btn btn-primary" id="ok">' + icon('check') + ' Salvar</button>',
      onMount(el, close) {
        const w = el.querySelector('#f-apre-w'), cb = el.querySelector('#f-apre');
        cb.addEventListener('change', () => w.classList.toggle('on', cb.checked));
        const lista = el.querySelector('#subs-list'), somaEl = el.querySelector('#sub-sum');
        function renderSubs() {
          lista.innerHTML = subs.map((s, i) =>
            '<div class="flex" style="gap:.5rem;align-items:center;margin-bottom:.4rem">' +
              '<input class="input sub-nome" data-i="' + i + '" value="' + esc(s.nome) + '" placeholder="nome da sub-área (ex.: SADT)" style="flex:1">' +
              '<input class="input sub-ch" data-i="' + i + '" type="number" min="1" value="' + s.ch + '" style="width:96px" title="CH (h)">' +
              '<button class="icon-btn btn-sm" data-sub-del="' + i + '" title="Remover">' + icon('trash') + '</button>' +
            '</div>').join('');
          lista.querySelectorAll('.sub-nome').forEach((inp) => inp.addEventListener('input', () => { subs[+inp.getAttribute('data-i')].nome = inp.value; }));
          lista.querySelectorAll('.sub-ch').forEach((inp) => inp.addEventListener('input', () => { subs[+inp.getAttribute('data-i')].ch = +inp.value || 0; atualizaSoma(); }));
          lista.querySelectorAll('[data-sub-del]').forEach((b) => b.addEventListener('click', () => { subs.splice(+b.getAttribute('data-sub-del'), 1); renderSubs(); atualizaSoma(); }));
          atualizaSoma();
        }
        function atualizaSoma() {
          if (!subs.length) { somaEl.textContent = ''; return; }
          const soma = subs.reduce((s, x) => s + (+x.ch || 0), 0);
          const total = +el.querySelector('#f-ach').value || 0;
          const ok = soma === total;
          somaEl.innerHTML = '<b>' + subs.length + ' sub-área(s)</b> · soma ' + soma + 'h ' + (ok ? '= total ✓' : '<span style="color:var(--st-risco)">≠ total ' + total + 'h</span>');
        }
        el.querySelector('#f-ach').addEventListener('input', atualizaSoma);
        el.querySelector('#add-sub').addEventListener('click', () => { subs.push({ nome: '', ch: 20 }); renderSubs(); });
        renderSubs();

        el.querySelector('#ok').addEventListener('click', () => {
          const nome = el.querySelector('#f-anome').value.trim();
          const err = el.querySelector('#err');
          if (!nome) { err.textContent = 'Informe o nome da área.'; err.style.display = 'block'; return; }
          const subsValidas = subs.filter((s) => s.nome.trim());
          const composta = subsValidas.length > 0;
          const fase = el.querySelector('#f-afase').value;
          const cor = ar ? ar.cor : '#64748b';
          const dados = { nome, carga_exigida: +el.querySelector('#f-ach').value || 1, fase, pre_requisito: cb.checked, area_mae: null, composta, cor };
          let maeId;
          if (ar) { Object.assign(ar, dados); maeId = ar.id; }
          else { maeId = S.uid('ar'); st.areas.push(Object.assign({ id: maeId }, dados)); }
          // reconcilia sub-áreas (filhos) — cria/atualiza/remove
          const idsMantidos = [];
          subsValidas.forEach((s) => {
            if (s.id) { const f = st.areas.find((a) => a.id === s.id); if (f) { f.nome = s.nome.trim(); f.carga_exigida = +s.ch || 1; f.fase = fase; f.area_mae = maeId; f.composta = false; f.cor = cor; } idsMantidos.push(s.id); }
            else { const nid = S.uid('ar'); st.areas.push({ id: nid, nome: s.nome.trim(), carga_exigida: +s.ch || 1, fase, pre_requisito: false, area_mae: maeId, composta: false, cor }); idsMantidos.push(nid); }
          });
          // remove filhos que saíram (e seus locais órfãos)
          st.areas.filter((a) => a.area_mae === maeId && idsMantidos.indexOf(a.id) < 0).forEach((f) => {
            st.locais = st.locais.filter((l) => l.area_id !== f.id);
            const ix = st.areas.indexOf(f); if (ix >= 0) st.areas.splice(ix, 1);
          });
          close();
          window.UI.toast(ar ? 'Área atualizada' : 'Área cadastrada', 'success');
          afterSave('Área ' + nome + ' cadastrada/alterada', 'Área ' + (ar ? 'editada' : 'cadastrada') + ': ' + nome);
          if (done) done();
        });
      },
    });
  };

  // ------------------------------------------------------------------ LOCAL ----
  window.Forms.local = function (id, done) {
    const st = S.get();
    const lc = id ? st.locais.find((l) => l.id === id) : null;
    // local aponta para uma área LEAF (não para container composto)
    const areasOpt = st.areas.filter((a) => !a.composta).map((a) => opt(a.id, (a.area_mae ? (st.areas.find((x) => x.id === a.area_mae) || {}).nome + ' · ' : '') + a.nome, lc ? lc.area_id : '')).join('');
    // docente/preceptor NÃO ficam neste form — são definidos no passo "Configurações de campo".
    const dias = [['segunda','Segunda'],['terca','Terça'],['quarta','Quarta'],['quinta','Quinta'],['sexta','Sexta'],['sabado','Sábado']];
    window.UI.modal({
      titulo: lc ? 'Editar local' : 'Novo local',
      wide: true,
      corpo:
        '<div class="form-grid">' +
          '<div class="field"><label>Área</label><select class="select" id="f-area">' + areasOpt + '</select></div>' +
          '<div class="field"><label>Campo (cenário)</label><input class="input" id="f-campo" value="' + esc(lc ? lc.campo : '') + '" placeholder="Hospital, UBS, Clínica-Escola…"></div>' +
          '<div class="field" style="grid-column:1/-1"><div class="hint">O <b>docente responsável</b> e o <b>preceptor de campo</b> deste local são definidos no passo <b>Configurações de campo</b>.</div></div>' +
          '<div class="field"><label>Dia da semana</label><select class="select" id="f-dia">' + dias.map((d) => opt(d[0], d[1], lc ? lc.dia_semana : '')).join('') + '</select></div>' +
          '<div class="field"><label>Turno</label><select class="select" id="f-turno">' + opt('manha','Manhã',lc?lc.turno:'') + opt('tarde','Tarde',lc?lc.turno:'') + opt('integral','Integral',lc?lc.turno:'') + opt('noite','Noite',lc?lc.turno:'') + '</select></div>' +
          '<div class="field"><label>Hora início</label><input class="input" type="time" id="f-hi" value="' + (lc ? lc.hora_inicio : '08:00') + '"></div>' +
          '<div class="field"><label>Hora fim</label><input class="input" type="time" id="f-hf" value="' + (lc ? lc.hora_fim : '12:00') + '"></div>' +
          '<div class="field"><label>Capacidade (vagas)</label><input class="input" type="number" min="1" id="f-cap" value="' + (lc ? lc.capacidade : 4) + '"></div>' +
          '<div class="field"><label>Carga horária da área (h)</label><input class="input" type="number" id="f-ch" value="' + (lc ? lc.carga_horaria : 60) + '"><div class="hint">Total que o grupo precisa cumprir neste local.</div></div>' +
          '<div class="field"><label>Horas por encontro</label><input class="input" type="number" step="0.5" min="0.5" id="f-hses" value="' + (lc ? (lc.horas_sessao || 4) : 4) + '"><div class="hint">Ex.: 08:00–12:00 = 4h. No integral, desconte o almoço (8h).</div></div>' +
        '</div>' +
        '<div class="hint mt-sm" id="enc-hint" style="font-weight:600;color:var(--brand-400)"></div>' +
        '<label class="check ' + (lc && lc.passagem_grupo ? 'on' : '') + '" id="f-pass-w"><input type="checkbox" id="f-pass" ' + (lc && lc.passagem_grupo ? 'checked' : '') + '><span>Passagem de grupo</span></label>' +
        '<div class="hint mt-sm">Marque se, neste local, o último encontro de um grupo é o primeiro do próximo (1 dia de sobreposição — quem sai orienta quem entra).</div>' +
        '<label class="check ' + (!lc || lc.ativo ? 'on' : '') + '" id="f-ativo-w"><input type="checkbox" id="f-ativo" ' + (!lc || lc.ativo ? 'checked' : '') + '><span>Local ativo</span></label>' +
        '<div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="ok">' + icon('check') + ' Salvar</button>',
      onMount(el, close) {
        const w = el.querySelector('#f-ativo-w'); const cb = el.querySelector('#f-ativo');
        cb.addEventListener('change', () => w.classList.toggle('on', cb.checked));
        const wp = el.querySelector('#f-pass-w'); const cbp = el.querySelector('#f-pass');
        cbp.addEventListener('change', () => wp.classList.toggle('on', cbp.checked));
        // nº de encontros calculado ao vivo = teto(CH ÷ horas por encontro)
        const areaSel = el.querySelector('#f-area'), chIn = el.querySelector('#f-ch'), hsIn = el.querySelector('#f-hses'), encH = el.querySelector('#enc-hint');
        function areaCarga(aid) { const a = st.areas.find((x) => x.id === aid); return a ? a.carga_exigida : 0; }
        function recalcEnc() {
          const ch = +chIn.value || 0, hs = +hsIn.value || 0;
          const enc = hs > 0 ? Math.max(1, Math.ceil(ch / hs)) : 0;
          encH.textContent = icon ? '' : '';
          encH.innerHTML = window.UI.icon('layers') + ' Este slot gera ' + enc + ' encontro(s) semanais (' + ch + 'h ÷ ' + hs + 'h) — 1 grupo de ' + (+el.querySelector('#f-cap').value || 0) + ' aluno(s) nesse dia.';
        }
        areaSel.addEventListener('change', () => { chIn.value = areaCarga(areaSel.value); recalcEnc(); });
        [chIn, hsIn, el.querySelector('#f-cap')].forEach((inp) => inp.addEventListener('input', recalcEnc));
        recalcEnc();
        el.querySelector('#ok').addEventListener('click', () => {
          const campo = el.querySelector('#f-campo').value.trim();
          const cap = +el.querySelector('#f-cap').value;
          const err = el.querySelector('#err');
          if (!campo) { err.textContent = 'Informe o campo.'; err.style.display = 'block'; return; }
          if (cap <= 0) { err.textContent = 'A capacidade deve ser maior que zero.'; err.style.display = 'block'; return; }
          const ativo = cb.checked;
          const dia = el.querySelector('#f-dia').value;
          const ch = +el.querySelector('#f-ch').value;
          const hses = +el.querySelector('#f-hses').value || 4;
          const dados = {
            area_id: el.querySelector('#f-area').value, campo, dia_semana: dia, dias: [dia],
            turno: el.querySelector('#f-turno').value, hora_inicio: el.querySelector('#f-hi').value, hora_fim: el.querySelector('#f-hf').value,
            horas_sessao: hses, capacidade: cap, carga_horaria: ch,
            numero_encontros: Math.max(1, Math.ceil(ch / hses)), passagem_grupo: cbp.checked, ativo,
          };
          let desativado = false;
          if (lc) { desativado = lc.ativo && !ativo; Object.assign(lc, dados); }
          else st.locais.push(Object.assign({ id: S.uid('lc'), ciclo_id: S.cicloAtivo().id, docente_id: null, preceptor_id: null, preceptor_tipo: null }, dados));
          close();
          window.UI.toast(lc ? 'Local atualizado' : 'Local cadastrado', 'success');
          afterSave(desativado ? 'Local desativado: ' + campo + ' — realocar estágios' : 'Local ' + campo + ' alterado',
                    'Local ' + (lc ? (desativado ? 'desativado' : 'editado') : 'cadastrado') + ': ' + campo);
          if (done) done();
        });
      },
    });
  };

  // ------------------------------------------------ INDISPONIBILIDADE LOCAL ----
  window.Forms.indisponibilidade = function (localId, done) {
    const st = S.get();
    const lc = st.locais.find((l) => l.id === localId);
    window.UI.modal({
      titulo: 'Indisponibilidade — ' + (lc ? lc.campo : ''),
      corpo:
        '<p class="muted mb">Período em que o local fica indisponível (imprevisto no campo, docente em congresso). Ao fim do período, o local volta a valer sozinho.</p>' +
        '<div class="field"><label>Motivo</label><input class="input" id="f-mot" placeholder="ex.: reforma, imprevisto no campo"></div>' +
        '<div class="form-grid">' +
          '<div class="field"><label>Início</label><input class="input" type="date" id="f-ini"></div>' +
          '<div class="field"><label>Fim</label><input class="input" type="date" id="f-fim"></div>' +
        '</div><div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="ok">' + icon('check') + ' Registrar</button>',
      onMount(el, close) {
        el.querySelector('#ok').addEventListener('click', () => {
          const ini = el.querySelector('#f-ini').value, fim = el.querySelector('#f-fim').value;
          const err = el.querySelector('#err');
          if (!ini || !fim) { err.textContent = 'Informe início e fim.'; err.style.display = 'block'; return; }
          if (fim < ini) { err.textContent = 'O fim deve ser posterior ao início.'; err.style.display = 'block'; return; }
          st.indisponibilidades_local.push({ id: S.uid('il'), local_id: localId, motivo: el.querySelector('#f-mot').value.trim(), data_inicio: ini, data_fim: fim });
          close();
          window.UI.toast('Indisponibilidade registrada', 'success');
          afterSave('Indisponibilidade do local ' + (lc ? lc.campo : '') + ' (' + ini + '→' + fim + ')', 'Indisponibilidade: ' + (lc ? lc.campo : ''));
          if (done) done();
        });
      },
    });
  };

  // ----------------------------------------------------------------- EVENTO ----
  window.Forms.evento = function (id, done) {
    const st = S.get();
    const ev = id ? st.eventos.find((e) => e.id === id) : null;
    window.UI.modal({
      titulo: ev ? 'Editar evento' : 'Novo evento',
      corpo:
        '<div class="field"><label>Nome</label><input class="input" id="f-nome" value="' + esc(ev ? ev.nome : '') + '"></div>' +
        '<div class="form-grid">' +
          '<div class="field"><label>Tipo</label><select class="select" id="f-tipo">' +
            opt('academico','Acadêmico',ev?ev.tipo:'') + opt('reuniao','Reunião',ev?ev.tipo:'') + opt('feriado','Feriado',ev?ev.tipo:'') + opt('outro','Outro',ev?ev.tipo:'') + '</select></div>' +
          '<div class="field"><label>Origem</label><select class="select" id="f-orig">' +
            opt('manual','Manual',ev?ev.origem:'') + opt('api_feriados','API de feriados',ev?ev.origem:'') + '</select></div>' +
          '<div class="field"><label>Início</label><input class="input" type="date" id="f-ini" value="' + (ev ? ev.data_inicio : '') + '"></div>' +
          '<div class="field"><label>Fim</label><input class="input" type="date" id="f-fim" value="' + (ev ? ev.data_fim : '') + '"></div>' +
        '</div>' +
        '<label class="check ' + (!ev || ev.bloqueia_estagio ? 'on' : '') + '" id="f-bloq-w"><input type="checkbox" id="f-bloq" ' + (!ev || ev.bloqueia_estagio ? 'checked' : '') + '><span>Bloqueia estágio</span></label>' +
        '<div class="hint mt-sm">Desmarque para eventos que não bloqueiam (ex.: atividades de Linguagem têm precedência e não suspendem a sessão).</div>' +
        '<div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="ok">' + icon('check') + ' Salvar</button>',
      onMount(el, close) {
        const w = el.querySelector('#f-bloq-w'); const cb = el.querySelector('#f-bloq');
        cb.addEventListener('change', () => w.classList.toggle('on', cb.checked));
        el.querySelector('#ok').addEventListener('click', () => {
          const nome = el.querySelector('#f-nome').value.trim();
          const ini = el.querySelector('#f-ini').value, fim = el.querySelector('#f-fim').value;
          const err = el.querySelector('#err');
          if (!nome || !ini) { err.textContent = 'Nome e início são obrigatórios.'; err.style.display = 'block'; return; }
          const dfim = fim || ini;
          if (dfim < ini) { err.textContent = 'O fim deve ser posterior ao início.'; err.style.display = 'block'; return; }
          const dados = { nome, tipo: el.querySelector('#f-tipo').value, origem: el.querySelector('#f-orig').value,
            data_inicio: ini, data_fim: dfim, bloqueia_estagio: cb.checked };
          if (ev) Object.assign(ev, dados);
          else st.eventos.push(Object.assign({ id: S.uid('ev'), ciclo_id: S.cicloAtivo().id }, dados));
          close();
          window.UI.toast(ev ? 'Evento atualizado' : 'Evento cadastrado', 'success');
          afterSave('Evento ' + nome + ' (' + ini + ') — sessões nas datas serão empurradas', 'Evento ' + (ev ? 'editado' : 'cadastrado') + ': ' + nome);
          if (done) done();
        });
      },
    });
  };

  // ------------------------------------------- ENCONTROS (ajuste manual +/−) ----
  //  Cadastro: a coordenação ajusta os encontros FEITOS de cada área do aluno.
  //  − = falta (o aluno não foi) · + = reforço (concede um encontro).
  //  O total é fixo (nº de encontros do espelho). Fechar o total conclui a área.

  //  Renderer compartilhado: pinta a lista de encontros do aluno dentro de `host`
  //  e fia os botões +/−. Usado tanto no modal dedicado (Forms.encontros) quanto
  //  na seção "Encontros" do modal de Editar aluno.
  function renderEncontrosInto(host, alunoId) {
    if (!host) return;
    S.atualizarConclusoes();
    const s2 = S.get();
    const linhas = s2.alocacoes.filter((a) => a.aluno_id === alunoId && a.status !== 'cancelada').map((a) => {
      const lc = s2.locais.find((l) => l.id === a.local_id);
      const ar = lc ? s2.areas.find((x) => x.id === lc.area_id) : null;
      const mat = s2.matriculas.find((m) => m.id === a.matricula_id);
      const enc = mat ? S.encontrosMatricula(mat) : { total: 0, feitos: 0 };
      const pct = enc.total ? Math.round((enc.feitos / enc.total) * 100) : 0;
      const concl = mat && mat.status === 'concluida';
      const cor = ar ? ar.cor : '#64748b';
      return '<div style="padding:.7rem 0;border-bottom:1px solid var(--border)">' +
        '<div class="flex between" style="align-items:center;gap:.6rem;margin-bottom:.35rem">' +
          '<div><b>' + esc(ar ? ar.nome : '—') + '</b> <span class="dim" style="font-size:.75rem">· ' + esc(lc ? lc.campo : '') + '</span>' +
            (concl ? ' <span class="badge b-concluida"><span class="dt"></span>concluída · vaga liberada</span>' : '') + '</div>' +
          '<div class="flex" style="align-items:center;gap:.45rem">' +
            '<button class="icon-btn btn-sm" data-menos="' + a.id + '" title="Registrar falta (−1)"><b>−</b></button>' +
            '<b style="min-width:60px;text-align:center">' + enc.feitos + ' / ' + enc.total + '</b>' +
            '<button class="icon-btn btn-sm" data-mais="' + a.id + '" title="Conceder reforço (+1)"><b>+</b></button>' +
          '</div>' +
        '</div>' + window.UI.bar(pct, cor) +
      '</div>';
    }).join('');
    host.innerHTML =
      '<p class="muted mb">Encontros <b>feitos</b> (presença assumida). <b>−</b> registra falta · <b>+</b> concede reforço. O total é fixo (espelho); ao fechar o total, a área <b>conclui e libera a vaga</b>.</p>' +
      (linhas || '<div class="empty">Aluno sem alocação — gere a escala para ajustar encontros.</div>');
    host.querySelectorAll('[data-menos]').forEach((b) => b.addEventListener('click', () => {
      S.ajustarEncontros(b.getAttribute('data-menos'), -1); renderEncontrosInto(host, alunoId); if (window.rerender) window.rerender();
    }));
    host.querySelectorAll('[data-mais]').forEach((b) => b.addEventListener('click', () => {
      S.ajustarEncontros(b.getAttribute('data-mais'), 1); renderEncontrosInto(host, alunoId); if (window.rerender) window.rerender();
    }));
  }

  window.Forms.encontros = function (alunoId) {
    const st = S.get();
    const al = st.alunos.find((a) => a.id === alunoId);
    const temAloc = st.alocacoes.some((a) => a.aluno_id === alunoId && a.status !== 'cancelada');
    if (!temAloc) { window.UI.toast('Aluno sem alocação — gere a escala primeiro.', 'error'); return; }

    window.UI.modal({
      titulo: 'Encontros — ' + esc(al.nome),
      wide: true,
      corpo: '<div id="enc-mng"></div>',
      rodape: '<button class="btn btn-primary" data-close>Fechar</button>',
      onMount(el) {
        renderEncontrosInto(el.querySelector('#enc-mng'), alunoId);
      },
    });
  };

  // remoção genérica
  window.Forms.remover = function (colecao, id, label, gatilho) {
    window.UI.confirmar('Remover', 'Remover "' + label + '"? Esta ação não pode ser desfeita.', () => {
      const st = S.get();
      st[colecao] = st[colecao].filter((x) => x.id !== id);
      if (colecao === 'alunos') {
        st.matriculas = st.matriculas.filter((m) => m.aluno_id !== id);
        S.reindexarOrdenamento();   // fecha o buraco: #3 vira #2, etc.
      }
      window.UI.toast('Removido', 'success');
      afterSave(gatilho || (label + ' removido'), label + ' removido');
    }, 'Remover');
  };

  // ---------------------------------------------- AJUSTE MANUAL DA ESCALA ----
  //  Caixa de avisos (regra "avisa e deixa decidir"): mostra violações brandas
  //  (vaga/30h/horário/restrição) sem impedir a ação.
  function avisosHtml(av) {
    if (!av || !av.ok) return '<div class="field-err" style="display:block">' + esc((av && av.erro) || 'Ação não possível.') + '</div>';
    if (!av.avisos.length) return '<div class="hint" style="display:flex;gap:.4rem;color:var(--st-concluida)">' + icon('checkCircle') + '<span>Sem conflitos.</span></div>';
    return '<div class="stack" style="gap:.35rem;margin-top:.4rem">' +
      '<div class="hint" style="font-weight:600;color:var(--st-risco)">Avisos (dá para confirmar mesmo assim):</div>' +
      av.avisos.map((a) => '<div class="flex" style="gap:.4rem">' + icon('alert') + '<span>' + esc(a) + '</span></div>').join('') +
    '</div>';
  }

  // Adicionar um aluno (da fila da área) a um local — encaixe manual.
  window.Forms.adicionarAloc = function (localId, done) {
    const st = S.get();
    const local = st.locais.find((l) => l.id === localId);
    if (!local) return;
    const area = st.areas.find((a) => a.id === local.area_id);
    const ocup = st.alocacoes.filter((a) => a.local_id === localId && a.status === 'ativa').length;
    const elegiveis = st.matriculas
      .filter((m) => m.area_id === local.area_id && m.status === 'em_andamento' &&
        !st.alocacoes.some((a) => a.matricula_id === m.id && a.status === 'ativa'))
      .map((m) => st.alunos.find((a) => a.id === m.aluno_id)).filter(Boolean)
      .sort((a, b) => a.ordenamento - b.ordenamento);
    const tem = elegiveis.length > 0;
    const opts = elegiveis.map((al) => opt(al.id, al.ordenamento + 'º · ' + al.nome, '')).join('');
    window.UI.modal({
      titulo: 'Adicionar aluno · ' + local.campo,
      corpo:
        '<div class="hint mb">Área <b>' + esc(area ? area.nome : '') + '</b> · ocupação ' + ocup + '/' + local.capacidade + '. O aluno entra a partir de hoje e a alocação fica travada.</div>' +
        (tem
          ? '<div class="field"><label>Aluno (fila da área, por prioridade)</label><select class="select" id="f-al">' + opts + '</select></div><div id="av"></div>'
          : '<div class="empty">Não há alunos elegíveis: os matriculados nesta área já estão alocados.</div>'),
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              (tem ? '<button class="btn btn-primary" id="ok">' + icon('check') + ' Adicionar</button>' : ''),
      onMount(el, close) {
        if (!tem) return;
        const sel = el.querySelector('#f-al'); const box = el.querySelector('#av'); const ok = el.querySelector('#ok');
        function render() { const av = S.avaliarAlocacaoManual(sel.value, localId); box.innerHTML = avisosHtml(av); ok.disabled = !av.ok; }
        sel.addEventListener('change', render); render();
        ok.addEventListener('click', () => {
          const id = S.alocarManual(sel.value, localId);
          close();
          window.UI.toast(id ? 'Aluno alocado (ajuste manual)' : 'Não foi possível alocar', id ? 'success' : 'error');
          if (done) done();
        });
      },
    });
  };

  // Mover um aluno já alocado para outro local da mesma área.
  window.Forms.moverAloc = function (alocId, done) {
    const st = S.get();
    const a = st.alocacoes.find((x) => x.id === alocId);
    if (!a) return;
    const al = st.alunos.find((x) => x.id === a.aluno_id);
    const atual = st.locais.find((l) => l.id === a.local_id);
    const area = st.areas.find((ar) => ar.id === atual.area_id);
    const destinos = st.locais.filter((l) => l.area_id === atual.area_id && l.ativo && l.id !== atual.id);
    const tem = destinos.length > 0;
    const opts = destinos.map((l) => opt(l.id, l.campo + ' (' + window.UI.diasLabel(l) + ' · ' + window.UI.turnoLabel(l.turno) + ')', '')).join('');
    window.UI.modal({
      titulo: 'Mover ' + (al ? al.nome : '') + ' · ' + (area ? area.nome : ''),
      corpo:
        '<div class="hint mb">De <b>' + esc(atual.campo) + '</b> para outro local da mesma área.</div>' +
        (tem
          ? '<div class="field"><label>Local destino</label><select class="select" id="f-lc">' + opts + '</select></div><div id="av"></div>'
          : '<div class="empty">Não há outro local ativo nesta área para onde mover.</div>'),
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              (tem ? '<button class="btn btn-primary" id="ok">' + icon('check') + ' Mover</button>' : ''),
      onMount(el, close) {
        if (!tem) return;
        const sel = el.querySelector('#f-lc'); const box = el.querySelector('#av'); const ok = el.querySelector('#ok');
        function render() { const av = S.avaliarAlocacaoManual(a.aluno_id, sel.value); box.innerHTML = avisosHtml(av); ok.disabled = !av.ok; }
        sel.addEventListener('change', render); render();
        ok.addEventListener('click', () => {
          const id = S.moverAlocacao(alocId, sel.value);
          close();
          window.UI.toast(id ? 'Aluno movido' : 'Não foi possível mover', id ? 'success' : 'error');
          if (done) done();
        });
      },
    });
  };
})();
