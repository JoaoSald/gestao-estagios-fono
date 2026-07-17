/* ============================================================================
   lib.js — Utilidades de UI: ícones SVG inline, toast, modal, formatação.
   Sem dependências externas.
   ============================================================================ */
(function () {
  'use strict';

  // ---- Ícones (SVG inline, stroke currentColor) ----------------------------
  const P = { fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' };
  function svg(paths) {
    return '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + paths + '</svg>';
  }
  const ICONS = {
    dashboard: svg('<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>'),
    users: svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    user: svg('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'),
    teacher: svg('<path d="M22 10 12 5 2 10l10 5 10-5Z"/><path d="M6 12v5c0 1 3 3 6 3s6-2 6-3v-5"/>'),
    calendarOff: svg('<path d="M8 2v4M16 2v4M3 10h18"/><rect x="3" y="4" width="18" height="18" rx="2"/><path d="m9 15 6 -6"/>'),
    building: svg('<rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M8 7h.01M12 7h.01M16 7h.01M8 11h.01M12 11h.01M16 11h.01M10 21v-4h4v4"/>'),
    calendar: svg('<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M8 2v4M16 2v4M3 10h18"/>'),
    grid: svg('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'),
    history: svg('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l3 2"/>'),
    shuffle: svg('<path d="M16 3h5v5"/><path d="M4 20 21 3"/><path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/>'),
    sync: svg('<path d="M21 12a9 9 0 0 1-9 9c-2.5 0-4.8-1-6.4-2.6L3 16"/><path d="M3 12a9 9 0 0 1 9-9c2.5 0 4.8 1 6.4 2.6L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/>'),
    power: svg('<path d="M18.4 6.6a9 9 0 1 1-12.8 0"/><path d="M12 2v10"/>'),
    plus: svg('<path d="M12 5v14M5 12h14"/>'),
    check: svg('<path d="M20 6 9 17l-5-5"/>'),
    checkCircle: svg('<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="m9 11 3 3L22 4"/>'),
    alert: svg('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>'),
    x: svg('<path d="M18 6 6 18M6 6l12 12"/>'),
    chevronRight: svg('<path d="m9 18 6-6-6-6"/>'),
    chevronLeft: svg('<path d="m15 18-6-6 6-6"/>'),
    edit: svg('<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4Z"/>'),
    trash: svg('<path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>'),
    search: svg('<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>'),
    clock: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    flag: svg('<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V4s-1 1-4 1-5-2-8-2-4 1-4 1Z"/><path d="M4 22v-7"/>'),
    layers: svg('<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/>'),
    sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    moon: svg('<path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z"/>'),
    sparkles: svg('<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8"/>'),
    reset: svg('<path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-6.4 2.6L3 8"/><path d="M3 3v5h5"/>'),
    logo: svg('<path d="M12 2a7 7 0 0 0-7 7c0 3 2 4 2 7a3 3 0 0 0 3 3h4a3 3 0 0 0 3-3c0-3 2-4 2-7a7 7 0 0 0-7-7Z"/><path d="M9 19h6"/>'),
    file: svg('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/>'),
    arrowRight: svg('<path d="M5 12h14M12 5l7 7-7 7"/>'),
    eye: svg('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>'),
    eyeOff: svg('<path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 8 10 8a18.5 18.5 0 0 1-2.16 3.19M6.6 6.6A18.5 18.5 0 0 0 2 12s3.5 7 10 7a9.1 9.1 0 0 0 5.4-1.6"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="M2 2l20 20"/>'),
    logout: svg('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>'),
    mail: svg('<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 7 10 6 10-6"/>'),
    lock: svg('<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'),
  };
  function icon(name, cls) {
    return '<span class="ic ' + (cls || '') + '" aria-hidden="true">' + (ICONS[name] || '') + '</span>';
  }

  // ---- HTML escaping --------------------------------------------------------
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // ---- Formatação de datas --------------------------------------------------
  const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  const MESES_LONGO = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
  function fmtData(s) {
    if (!s) return '—';
    const [y, m, d] = s.split('-');
    return d + ' ' + MESES[+m - 1] + ' ' + y;
  }
  function fmtDataCurta(s) {
    if (!s) return '—';
    const [, m, d] = s.split('-');
    return d + '/' + m;
  }

  // ---- Toast ----------------------------------------------------------------
  function toast(msg, tipo) {
    const cont = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = 'toast toast-' + (tipo || 'info');
    const ic = tipo === 'success' ? 'checkCircle' : tipo === 'error' ? 'alert' : 'sparkles';
    el.innerHTML = icon(ic) + '<span>' + esc(msg) + '</span>';
    cont.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(20px)'; setTimeout(() => el.remove(), 250); }, 3200);
  }

  // ---- Modal ----------------------------------------------------------------
  function modal(opts) {
    const root = document.getElementById('modal-root');
    const back = document.createElement('div');
    back.className = 'modal-backdrop';
    const wide = opts.wide ? ' modal-wide' : '';
    back.innerHTML =
      '<div class="modal' + wide + '" role="dialog" aria-modal="true">' +
        '<div class="modal-head"><h3>' + esc(opts.titulo) + '</h3>' +
          '<button class="icon-btn" data-close>' + icon('x') + '</button></div>' +
        '<div class="modal-body">' + (opts.corpo || '') + '</div>' +
        '<div class="modal-foot">' + (opts.rodape || '') + '</div>' +
      '</div>';
    root.appendChild(back);
    function close() { back.remove(); if (opts.onClose) opts.onClose(); }
    back.addEventListener('click', (e) => { if (e.target === back) close(); });
    back.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', close));
    if (opts.onMount) opts.onMount(back, close);
    return { el: back, close };
  }

  // ---- Confirmação simples --------------------------------------------------
  function confirmar(titulo, mensagem, onOk, okLabel) {
    modal({
      titulo,
      corpo: '<p class="muted">' + esc(mensagem) + '</p>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" data-ok>' + esc(okLabel || 'Confirmar') + '</button>',
      onMount(el, close) {
        el.querySelector('[data-ok]').addEventListener('click', () => { close(); onOk(); });
      },
    });
  }

  // ---- Barra de progresso simples ------------------------------------------
  function bar(pct, cor) {
    return '<div class="pbar"><span style="width:' + Math.min(100, pct) + '%;background:' + (cor || 'var(--brand-500)') + '"></span></div>';
  }

  // ---- Rótulos de dia/turno (compartilhados entre as telas) ----------------
  const DIA_CURTO = { segunda: 'Seg', terca: 'Ter', quarta: 'Qua', quinta: 'Qui', sexta: 'Sex', sabado: 'Sáb', domingo: 'Dom' };
  const DIA_LONGO = { segunda: 'Segunda', terca: 'Terça', quarta: 'Quarta', quinta: 'Quinta', sexta: 'Sexta', sabado: 'Sábado', domingo: 'Domingo' };
  const TURNO = { manha: 'manhã', tarde: 'tarde', noite: 'noite', integral: 'integral' };
  // Aceita um local (com `dias` array ou `dia_semana` único) ou uma string de dia.
  function diasLabel(local, longo) {
    const map = longo ? DIA_LONGO : DIA_CURTO;
    if (typeof local === 'string') return map[local] || local;
    const dias = local && local.dias && local.dias.length ? local.dias : [local ? local.dia_semana : ''];
    return dias.map((d) => map[d] || d).join(', ');
  }
  function turnoLabel(t) { return TURNO[t] || t; }

  // ---- Busca em tabelas (filtro ao vivo, sem re-render) --------------------
  function normalizar(s) {
    return (s == null ? '' : String(s)).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }
  // Campo de busca padrão (input type=search com ícone). id único por tela.
  function searchBox(id, placeholder) {
    return '<div class="search-box">' + icon('search') +
      '<input class="input" id="' + id + '" type="search" autocomplete="off" placeholder="' + esc(placeholder || 'Buscar…') + '"></div>';
  }
  // Liga o input a um <tbody>: filtra as linhas por texto (ignora acento/caixa).
  // Linhas com data-nofilter (ex.: "nenhum registro") nunca somem.
  // Retorna a função de filtragem (útil para reaplicar após um rerender).
  function wireSearch(input, tbody, onCount) {
    if (!input || !tbody) return function () {};
    function aplicar() {
      const q = normalizar(input.value.trim());
      let visiveis = 0;
      tbody.querySelectorAll('tr').forEach((tr) => {
        if (tr.hasAttribute('data-nofilter')) return;
        const ok = !q || normalizar(tr.textContent).indexOf(q) >= 0;
        tr.style.display = ok ? '' : 'none';
        if (ok) visiveis++;
      });
      if (onCount) onCount(visiveis, q);
    }
    input.addEventListener('input', aplicar);
    aplicar();
    return aplicar;
  }

  window.UI = { icon, esc, fmtData, fmtDataCurta, MESES, MESES_LONGO, toast, modal, confirmar, bar,
    DIA_CURTO, DIA_LONGO, TURNO, diasLabel, turnoLabel, normalizar, searchBox, wireSearch };
})();
