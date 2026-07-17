/* alunos.js — Alunos: alterna entre "Matriculados" (lista) e "Ofertas" (oferta × demanda). */
(function () {
  'use strict';
  const { icon, esc } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  // vista atual: 'matriculados' (lista) | 'ofertas' (oferta × demanda). Persiste entre rerenders.
  let vista = 'matriculados';
  // filtro por fase na lista: 'todos' | '7' | '9_10'
  let faseFiltro = 'todos';

  // Mapa de situação de oferta × demanda → rótulo + cor do badge
  const SIT = {
    equilibrio:  { cls: 'b-iniciar',   txt: function () { return '✓ equilíbrio'; } },
    reprimida:   { cls: 'b-risco',     txt: function (d) { return d.fila.length + ' aguardando · sem vaga'; } },
    sobrando:    { cls: 'b-andamento', txt: function (d) { return d.vagasLivres + ' vaga' + (d.vagasLivres > 1 ? 's' : '') + ' livre' + (d.vagasLivres > 1 ? 's' : '') + ' — pode matricular'; } },
    ociosa_fila: { cls: 'b-risco',     txt: function () { return 'vaga ociosa + fila · conflito de horário'; } },
  };

  // célula de contagem por estado: badge colorido quando há áreas; "0" apagado quando não há
  function contagem(n, cls, titulo) {
    return n > 0
      ? '<span class="badge ' + cls + '" title="' + titulo + '"><span class="dt"></span>' + n + '</span>'
      : '<span class="dim" style="opacity:.45">0</span>';
  }

  // ---- VISÃO "MATRICULADOS" (lista atual, com rolagem vertical) -------------
  function listaMatriculados(alunos) {
    const rows = alunos.map((al) => {
      const p = S.progressoAluno(al.id);
      return '<tr data-open="' + al.id + '" style="cursor:pointer">' +
        '<td><b>' + al.ordenamento + 'º</b></td>' +
        '<td><b>' + esc(al.nome) + '</b><div class="dim" style="font-size:.75rem">' + esc(al.matricula) + ' · sem. ' + al.semestre + (al.email ? ' · ' + esc(al.email) : '') + '</div></td>' +
        '<td><div style="min-width:130px">' + window.UI.bar(p.pctCarga, 'var(--brand-400)') + '<div class="hint">' + p.pctCarga + '% da carga · ' + p.concluidas + '/' + p.totalAreas + ' áreas</div></div></td>' +
        '<td style="text-align:center">' + contagem(p.emAndamento, 'b-andamento', 'Áreas matriculadas com vaga alocada') + '</td>' +
        '<td style="text-align:center">' + contagem(p.aguardando, 'b-aguardando', 'Áreas matriculadas na fila, aguardando vaga') + '</td>' +
        '<td style="text-align:center">' + contagem(p.concluidas, 'b-concluida', 'Áreas concluídas') + '</td>' +
        '<td>' + (p.risco ? '<span class="badge b-risco"><span class="dt"></span>risco</span>' : '<span class="badge b-andamento"><span class="dt"></span>ok</span>') + '</td>' +
        '<td><div class="row-actions">' +
          '<button class="icon-btn btn-sm" data-enc="' + al.id + '" title="Encontros (faltas / reforços)">' + icon('calendar') + '</button>' +
          '<button class="icon-btn btn-sm" data-edit="' + al.id + '">' + icon('edit') + '</button>' +
          '<button class="icon-btn btn-sm" data-del="' + al.id + '">' + icon('trash') + '</button></div></td></tr>';
    }).join('');

    return '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr>' +
      '<th>Prioridade</th><th>Aluno</th><th>Carga</th>' +
      '<th style="text-align:center" title="Áreas matriculadas com vaga alocada">Em andamento</th>' +
      '<th style="text-align:center" title="Áreas matriculadas na fila, aguardando vaga">Aguardando</th>' +
      '<th style="text-align:center" title="Áreas concluídas">Concluído</th>' +
      '<th>Situação</th><th></th></tr></thead>' +
      '<tbody>' + (rows || '<tr data-nofilter><td colspan="8"><div class="empty">Nenhum aluno.</div></td></tr>') +
      '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="8"><div class="empty">Nenhum aluno encontrado.</div></td></tr></tbody></table></div>';
  }

  // ---- VISÃO "OFERTAS" (fila de espera + vagas sobrando por área) -----------
  function ofertas() {
    const dados = S.ofertaDemandaAreas();
    const rows = dados.map(function (d) {
      const sit = SIT[d.situacao];
      const filaTxt = d.fila.length
        ? '<div class="hint" style="margin-top:.3rem">Fila: ' + d.fila.map(function (f, i) {
            return (i + 1) + 'º ' + esc(f.nome) + ' <span class="dim">(prio ' + f.ordenamento + ')</span>';
          }).join(' · ') + '</div>'
        : '';
      return '<tr data-oferta="' + d.area.id + '" style="cursor:pointer" title="Ver alunos e previsão de início">' +
        '<td><b>' + esc(d.area.nome) + '</b></td>' +
        '<td>' + d.capacidade + '</td>' +
        '<td>' + d.ocupadas + '</td>' +
        '<td>' + (d.vagasLivres > 0 ? '<b>' + d.vagasLivres + '</b>' : '0') + '</td>' +
        '<td>' + d.fila.length + '</td>' +
        '<td><span class="badge ' + sit.cls + '"><span class="dt"></span>' + sit.txt(d) + '</span>' + filaTxt + '</td>' +
        '</tr>';
    }).join('');

    return '<p class="dim" style="margin:0 0 .7rem">Fila e vagas são derivadas em tempo real (matrícula em andamento sem alocação = aguardando). ' +
      'Clique numa área para ver os alunos e a previsão de início. Vaga livre sem fila → pode matricular manualmente.</p>' +
      '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr>' +
      '<th>Área</th><th>Cap.</th><th>Ocup.</th><th>Livres</th><th>Fila</th><th>Situação</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }

  // ---- CARD (modal) de uma área: alocados + fila com previsão de início ------
  function cardOferta(areaId) {
    const { fmtData } = window.UI;
    const d = S.previsaoInicioArea(areaId);
    if (!d.area) return;

    const stat = (rot, val) => '<div style="flex:1;min-width:88px;padding:.6rem .8rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface-2)">' +
      '<div style="font-size:1.6rem;font-weight:800;letter-spacing:-.02em">' + val + '</div>' +
      '<div class="dim" style="font-size:.74rem">' + rot + '</div></div>';
    const stats = '<div class="flex flex-wrap mb" style="gap:.7rem">' +
      stat('Capacidade', d.capacidade) + stat('Ocupadas', d.ocupadas) +
      stat('Vagas livres', d.vagasLivres) + stat('Na fila', d.fila.length) + '</div>';

    // Alocados: nome · prioridade · local · início · conclusão prevista
    const localCel = (l) => l
      ? esc(l.campo) + (l.unidade ? ' <span class="dim" style="font-size:.75rem">· ' + esc(l.unidade) + '</span>' : '')
      : '<span class="dim">—</span>';
    const alocRows = d.alocados.length
      ? d.alocados.map((a) =>
          '<tr><td><b>' + a.ordenamento + 'º</b></td>' +
          '<td>' + esc(a.nome) + (a.concluida ? ' <span class="badge b-concluida"><span class="dt"></span>concluída</span>' : '') + '</td>' +
          '<td>' + localCel(a.local) + '</td>' +
          '<td>' + fmtData(a.data_inicio) + '</td>' +
          '<td>' + fmtData(a.concluida ? (a.data_conclusao || a.data_fim_prevista) : a.data_fim_prevista) + '</td></tr>').join('')
      : '<tr><td colspan="5"><div class="empty">Ninguém alocado nesta área.</div></td></tr>';
    const alocado = '<h4 style="margin:.2rem 0 .4rem">Alocados (' + d.alocados.length + ')</h4>' +
      '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Prio.</th><th>Aluno</th><th>Local</th><th>Início</th><th>Conclusão prev.</th></tr></thead>' +
      '<tbody>' + alocRows + '</tbody></table></div>';

    // Fila: nome · prioridade · previsão de início (com alerta de remanejamento)
    const filaRows = d.fila.length
      ? d.fila.map((f) => {
          const prev = f.previsao
            ? fmtData(f.previsao) + (f.remanejamento ? ' <span class="badge b-andamento"><span class="dt"></span>remanejamento</span>' : ' <span class="badge b-iniciar"><span class="dt"></span>vaga livre</span>')
            : '<span class="badge b-risco"><span class="dt"></span>' + esc(f.motivo || 'sem previsão') + '</span>';
          return '<tr><td><b>' + f.ordenamento + 'º</b></td><td>' + esc(f.nome) + '</td><td>' + prev + '</td></tr>';
        }).join('')
      : '<tr><td colspan="3"><div class="empty">Ninguém na fila de espera.</div></td></tr>';
    const fila = '<h4 style="margin:1rem 0 .4rem">Fila de espera (' + d.fila.length + ')</h4>' +
      '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Prio.</th><th>Aluno</th><th>Previsão de início</th></tr></thead>' +
      '<tbody>' + filaRows + '</tbody></table></div>';

    window.UI.modal({
      titulo: 'Ofertas · ' + d.area.nome,
      wide: true,
      corpo: stats + alocado + fila +
        '<p class="hint" style="margin-top:.8rem">' + icon('sparkles') + ' Previsão estimada: a fila entra por prioridade à medida que os alocados concluem e liberam vaga. Não é a saída definitiva do motor de escala.</p>',
      rodape: '<button class="btn btn-secondary" data-close>Fechar</button>',
    });
  }

  window.Views.alunos = function (arg) {
    if (arg === 'ofertas' || arg === 'matriculados') vista = arg;   // deep-link da sub-visão
    const st = S.get();
    const alunos = st.alunos.slice().sort((a, b) => a.ordenamento - b.ordenamento);
    const od = S.ofertaDemandaAreas();
    const totalFila = od.reduce((s, d) => s + d.fila.length, 0);
    const totalLivres = od.reduce((s, d) => s + d.vagasLivres, 0);

    const seg = (v, ic, label) =>
      '<button data-vista="' + v + '" class="' + (vista === v ? 'active' : '') + '">' + icon(ic) + label + '</button>';
    const segFase = (v, label) =>
      '<button data-fase="' + v + '" class="' + (faseFiltro === v ? 'active' : '') + '">' + label + '</button>';

    const listaAlunos = alunos.filter((a) => faseFiltro === 'todos' || (faseFiltro === '7' ? +a.semestre <= 7 : +a.semestre >= 8));

    const sub = vista === 'ofertas'
      ? totalLivres + ' vaga(s) livre(s) · ' + totalFila + ' na fila de espera'
      : listaAlunos.length + ' aluno(s) · ordenados por prioridade';

    return '<div class="page-head"><div class="row"><div><h1>Alunos</h1><p>' + sub + '</p></div>' +
        '<button class="btn btn-primary" data-add>' + icon('plus') + ' Novo aluno</button></div></div>' +
      '<div class="flex flex-wrap mb" style="gap:.8rem">' +
        '<div class="segmented">' + seg('matriculados', 'users', 'Matriculados') + seg('ofertas', 'building', 'Ofertas') + '</div>' +
        (vista === 'matriculados' ? '<div class="segmented">' + segFase('todos', 'Todos') + segFase('7', '7º semestre') + segFase('9_10', '9º/10º semestre') + '</div>' : '') +
        (vista === 'matriculados' ? window.UI.searchBox('busca-alunos', 'Buscar aluno por nome ou matrícula…') : '') +
      '</div>' +
      (vista === 'ofertas' ? ofertas() : listaMatriculados(listaAlunos));
  };

  window.Views.alunos_mount = function () {
    document.querySelector('[data-add]').addEventListener('click', () => window.Forms.aluno(null, () => window.rerender()));
    document.querySelectorAll('.segmented [data-vista]').forEach((b) => b.addEventListener('click', () => {
      vista = b.getAttribute('data-vista'); window.rerender();
    }));
    document.querySelectorAll('.segmented [data-fase]').forEach((b) => b.addEventListener('click', () => {
      faseFiltro = b.getAttribute('data-fase'); window.rerender();
    }));

    if (vista !== 'matriculados') {
      // aba Ofertas: clicar numa área abre o card com alocados + fila e previsão
      document.querySelectorAll('[data-oferta]').forEach((r) =>
        r.addEventListener('click', () => cardOferta(r.getAttribute('data-oferta'))));
      return;
    }

    const tb = document.querySelector('.tbl-wrap tbody');
    window.UI.wireSearch(document.getElementById('busca-alunos'), tb, (n, q) => {
      const vazio = tb && tb.querySelector('.sem-resultado'); if (vazio) vazio.style.display = (n === 0 && q) ? '' : 'none';
    });

    document.querySelectorAll('[data-enc]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); window.Forms.encontros(b.getAttribute('data-enc')); }));
    document.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); window.Forms.aluno(b.getAttribute('data-edit'), () => window.rerender()); }));
    document.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); window.Forms.remover('alunos', b.getAttribute('data-del'), 'Aluno', 'Aluno removido — vaga liberada'); }));
    document.querySelectorAll('[data-open]').forEach((r) => r.addEventListener('click', () => location.hash = '#/aluno/' + r.getAttribute('data-open')));
  };
})();
