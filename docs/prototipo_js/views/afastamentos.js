/* afastamentos.js — Lista consolidada de afastamentos (docente × ausência). */
(function () {
  'use strict';
  const { icon, esc, fmtData } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  window.Views.afastamentos = function () {
    const st = S.get();
    const rows = st.afastamentos.slice().sort((a, b) => a.data_inicio.localeCompare(b.data_inicio)).map((a) => {
      const ehPrec = !!a.preceptor_id;
      const p = ehPrec ? (st.preceptores || []).find((x) => x.id === a.preceptor_id) : st.docentes.find((x) => x.id === a.docente_id);
      const papel = ehPrec ? '<span class="badge b-iniciar">preceptor</span>' : '<span class="badge b-andamento">docente</span>';
      const dias = S.diffDays(a.data_inicio, a.data_retorno) + 1;
      return '<tr>' +
        '<td><b>' + esc(p ? p.nome : '?') + '</b> ' + papel + '</td>' +
        '<td><span class="badge b-neutral">' + a.tipo + '</span></td>' +
        '<td class="muted">' + esc(a.motivo || '—') + '</td>' +
        '<td>' + fmtData(a.data_inicio) + ' → ' + fmtData(a.data_retorno) + '<div class="hint">' + dias + ' dia(s)</div></td>' +
        '<td><div class="row-actions"><button class="icon-btn btn-sm" data-edit="' + a.id + '">' + icon('edit') + '</button>' +
          '<button class="icon-btn btn-sm" data-del="' + a.id + '">' + icon('trash') + '</button></div></td></tr>';
    }).join('');
    return '<div class="page-head"><div class="row"><div><h1>Afastamentos</h1><p>Férias, licenças e ausências de docentes e preceptores</p></div>' +
      '<button class="btn btn-primary" data-add>' + icon('plus') + ' Novo afastamento</button></div></div>' +
      '<div class="flex flex-wrap mb" style="gap:.8rem">' + window.UI.searchBox('busca-afast', 'Buscar por pessoa, tipo ou motivo…') + '</div>' +
      '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr><th>Pessoa</th><th>Tipo</th><th>Motivo</th><th>Período</th><th></th></tr></thead><tbody>' +
      (rows || '<tr data-nofilter><td colspan="5"><div class="empty">Nenhum afastamento.</div></td></tr>') +
      '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="5"><div class="empty">Nenhum afastamento encontrado.</div></td></tr></tbody></table></div>';
  };
  window.Views.afastamentos_mount = function () {
    document.querySelector('[data-add]').addEventListener('click', () => window.Forms.afastamento(null, () => window.rerender()));
    document.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => window.Forms.afastamento(b.getAttribute('data-edit'), () => window.rerender())));
    document.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => window.Forms.remover('afastamentos', b.getAttribute('data-del'), 'Afastamento', 'Afastamento removido — realocar')));
    const tb = document.querySelector('.tbl-wrap tbody');
    window.UI.wireSearch(document.getElementById('busca-afast'), tb, (n, q) => {
      const vazio = tb.querySelector('.sem-resultado'); if (vazio) vazio.style.display = (n === 0 && q) ? '' : 'none';
    });
  };
})();
