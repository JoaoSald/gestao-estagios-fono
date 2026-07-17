/* eventos.js — Eventos do ciclo (feriados, acadêmicos, reuniões) em duas visões:
   • Lista       — tabela com CRUD (editar/remover).
   • Calendário  — grade mensal com eventos coloridos por tipo + legenda.
   ============================================================================ */
(function () {
  'use strict';
  const { icon, esc, fmtData } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  // Cores/rótulos por tipo de evento (base para chips e legenda).
  const EV_TIPO = {
    feriado:   { cor: '#f43f5e', label: 'Feriado' },
    academico: { cor: '#0ea5e9', label: 'Acadêmico' },
    reuniao:   { cor: '#8b5cf6', label: 'Reunião' },
    recesso:   { cor: '#f59e0b', label: 'Recesso' },
  };
  const EV_FALLBACK = { cor: '#64748b', label: 'Outro' };
  function tipoInfo(t) { return EV_TIPO[t] || Object.assign({}, EV_FALLBACK, { label: t || 'Outro' }); }

  let evVista = 'lista';   // 'lista' | 'calendario'

  window.Views.eventos = function (arg) {
    if (arg === 'calendario' || arg === 'lista') evVista = arg;   // deep-link da sub-visão
    const st = S.get();
    const eventos = st.eventos.slice().sort((a, b) => a.data_inicio.localeCompare(b.data_inicio));

    const seg = (v, ic, label) =>
      '<button data-evvista="' + v + '" class="' + (evVista === v ? 'active' : '') + '">' + icon(ic) + label + '</button>';

    const head = '<div class="page-head"><div class="row"><div><h1>Eventos</h1><p>Eventos acadêmicos e feriados do ciclo</p></div>' +
      '<div class="flex"><button class="btn btn-primary" data-add>' + icon('plus') + ' Novo evento</button></div></div></div>' +
      '<div class="flex flex-wrap mb" style="gap:.8rem">' +
        '<div class="segmented">' + seg('lista', 'grid', 'Lista') + seg('calendario', 'calendar', 'Calendário') + '</div>' +
      '</div>';

    return head + (evVista === 'calendario' ? calendarioView(eventos) : listaView(eventos));
  };

  function listaView(eventos) {
    const rows = eventos.map((e) => {
      const periodo = e.data_inicio === e.data_fim ? fmtData(e.data_inicio) : fmtData(e.data_inicio) + ' → ' + fmtData(e.data_fim);
      const ti = tipoInfo(e.tipo);
      return '<tr>' +
        '<td><b>' + esc(e.nome) + '</b></td>' +
        '<td><span class="leg-item"><span class="leg-dot" style="background:' + ti.cor + '"></span>' + esc(ti.label) + '</span></td>' +
        '<td><span class="dim">' + esc(e.origem) + '</span></td>' +
        '<td>' + periodo + '</td>' +
        '<td>' + (e.bloqueia_estagio ? '<span class="badge b-risco"><span class="dt"></span>bloqueia</span>' : '<span class="badge b-andamento"><span class="dt"></span>não bloqueia</span>') + '</td>' +
        '<td><div class="row-actions"><button class="icon-btn btn-sm" data-edit="' + e.id + '">' + icon('edit') + '</button>' +
          '<button class="icon-btn btn-sm" data-del="' + e.id + '">' + icon('trash') + '</button></div></td></tr>';
    }).join('');
    return '<div class="flex flex-wrap mb" style="gap:.8rem">' + window.UI.searchBox('busca-eventos', 'Buscar evento por nome, tipo ou origem…') + '</div>' +
      '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr><th>Nome</th><th>Tipo</th><th>Origem</th><th>Data</th><th>Estágio</th><th></th></tr></thead><tbody>' +
      (rows || '<tr data-nofilter><td colspan="6"><div class="empty">Nenhum evento.</div></td></tr>') +
      '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="6"><div class="empty">Nenhum evento encontrado.</div></td></tr></tbody></table></div>';
  }

  function legenda(eventos) {
    const tipos = [...new Set(eventos.map((e) => e.tipo))];
    return '<div class="cal-legend mb">' +
      '<span class="hint" style="margin-right:.2rem">Categorias:</span>' +
      tipos.map((t) => {
        const ti = tipoInfo(t);
        const n = eventos.filter((e) => e.tipo === t).length;
        return '<span class="leg-item"><span class="leg-dot" style="background:' + ti.cor + '"></span>' + esc(ti.label) + '<span class="leg-n">' + n + '</span></span>';
      }).join('') +
      '<span class="leg-item"><span class="leg-dot" style="background:transparent;box-shadow:inset 0 0 0 2px var(--st-risco)"></span>bloqueia estágio</span>' +
      '</div>';
  }

  function calendarioView(eventos) {
    if (!eventos.length) return '<div class="tbl-wrap"><div class="empty"><div class="ei">' + icon('calendar') + '</div>Nenhum evento cadastrado.</div></div>';
    return legenda(eventos) + '<div id="ev-cal"></div>';
  }

  window.Views.eventos_mount = function () {
    document.querySelectorAll('.segmented [data-evvista]').forEach((b) => b.addEventListener('click', () => {
      evVista = b.getAttribute('data-evvista'); window.rerender();
    }));
    document.querySelector('[data-add]').addEventListener('click', () => window.Forms.evento(null, () => window.rerender()));
    document.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => window.Forms.evento(b.getAttribute('data-edit'), () => window.rerender())));
    document.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => window.Forms.remover('eventos', b.getAttribute('data-del'), 'Evento', 'Evento removido')));

    if (evVista === 'calendario') {
      const host = document.getElementById('ev-cal');
      if (host) montarCalEventos(host);
    } else {
      const tb = document.querySelector('.tbl-wrap tbody');
      window.UI.wireSearch(document.getElementById('busca-eventos'), tb, (n, q) => {
        const vazio = tb && tb.querySelector('.sem-resultado'); if (vazio) vazio.style.display = (n === 0 && q) ? '' : 'none';
      });
    }
  };

  function montarCalEventos(host) {
    const st = S.get();
    const c = S.cicloAtivo();
    const eventos = st.eventos.slice();
    // limites de navegação: jan do ano de início até dez do ano de fim
    const anoIni = c.data_inicio.slice(0, 4);
    const anoFim = c.data_fim.slice(0, 4);
    const minMes = anoIni + '-01';
    const maxMes = anoFim + '-12';
    let mesRef = S.hoje().slice(0, 7);
    if (mesRef < minMes) mesRef = minMes;
    if (mesRef > maxMes) mesRef = c.data_inicio.slice(0, 7);
    renderCalEventos(host, mesRef, eventos, minMes, maxMes);
  }

  function renderCalEventos(host, mesRef, eventos, minMes, maxMes) {
    const [y, mo] = mesRef.split('-').map(Number);
    const startDow = new Date(y, mo - 1, 1).getDay();
    const daysInMonth = new Date(y, mo, 0).getDate();
    const hoje = S.hoje();
    const dows = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

    let cells = '';
    for (let i = 0; i < startDow; i++) cells += '<div class="cal-cell out"></div>';
    for (let d = 1; d <= daysInMonth; d++) {
      const dia = y + '-' + String(mo).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      const doDia = eventos.filter((e) => dia >= e.data_inicio && dia <= e.data_fim);
      let inner = '<div class="dn">' + d + '</div>';
      doDia.slice(0, 3).forEach((e) => {
        const ti = tipoInfo(e.tipo);
        const bloq = e.bloqueia_estagio ? ';box-shadow:inset 0 0 0 1.5px rgba(244,63,94,.9)' : '';
        inner += '<span class="cal-sess" data-edit="' + e.id + '" style="cursor:pointer;background:' + ti.cor + bloq + '" title="' + esc(e.nome) + ' · ' + esc(ti.label) + (e.bloqueia_estagio ? ' · bloqueia estágio' : '') + '">' + esc(e.nome) + '</span>';
      });
      if (doDia.length > 3) inner += '<span class="cal-more">+' + (doDia.length - 3) + '</span>';
      cells += '<div class="cal-cell ' + (dia === hoje ? 'today' : '') + '">' + inner + '</div>';
    }

    const podePrev = mesRef > minMes;
    const podeNext = mesRef < maxMes;
    host.innerHTML = '<div class="cal"><div class="cal-head">' +
      '<button class="icon-btn" id="ev-prev" ' + (podePrev ? '' : 'disabled') + '>' + icon('chevronLeft') + '</button>' +
      '<h3>' + window.UI.MESES_LONGO[mo - 1] + ' ' + y + '</h3>' +
      '<button class="icon-btn" id="ev-next" ' + (podeNext ? '' : 'disabled') + '>' + icon('chevronRight') + '</button></div>' +
      '<div class="cal-grid">' + dows.map((d) => '<div class="cal-dow">' + d + '</div>').join('') + cells + '</div></div>';

    const go = (dm) => renderCalEventos(host, dm, eventos, minMes, maxMes);
    const prev = host.querySelector('#ev-prev'); const next = host.querySelector('#ev-next');
    if (prev) prev.addEventListener('click', () => { const d = new Date(y, mo - 2, 1); go(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')); });
    if (next) next.addEventListener('click', () => { const d = new Date(y, mo, 1); go(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')); });
    // clique no chip abre edição do evento
    host.querySelectorAll('.cal-sess[data-edit]').forEach((el) => el.addEventListener('click', () => window.Forms.evento(el.getAttribute('data-edit'), () => window.rerender())));
  }
})();
