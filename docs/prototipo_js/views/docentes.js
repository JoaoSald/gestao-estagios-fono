/* docentes.js — Lista de docentes. */
(function () {
  'use strict';
  const { icon, esc } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  window.Views.docentes = function () {
    const st = S.get();
    const rows = st.docentes.map((d) => {
      const nLocais = st.locais.filter((l) => l.docente_id === d.id && l.ativo).length;
      const nAfast = st.afastamentos.filter((a) => a.docente_id === d.id).length;
      return '<tr>' +
        '<td><b>' + esc(d.nome) + '</b></td>' +
        '<td>' + (d.email ? esc(d.email) : '<span class="dim">—</span>') + '</td>' +
        '<td>' + (d.ativo ? '<span class="badge b-concluida"><span class="dt"></span>ativo</span>' : '<span class="badge b-neutral">desligado</span>') + '</td>' +
        '<td>' + nLocais + ' local(is)</td><td>' + nAfast + ' afastamento(s)</td>' +
        '<td><div class="row-actions"><button class="icon-btn btn-sm" data-edit="' + d.id + '">' + icon('edit') + '</button></div></td></tr>';
    }).join('');
    return '<div class="page-head"><div class="row"><div><h1>Docentes</h1><p>' + st.docentes.length + ' docente(s) · cadastro permanente — atravessa ciclos</p></div>' +
      '<button class="btn btn-primary" data-add>' + icon('plus') + ' Novo docente</button></div></div>' +
      '<div class="flex flex-wrap mb" style="gap:.8rem">' + window.UI.searchBox('busca-docentes', 'Buscar docente por nome ou e-mail…') + '</div>' +
      '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr><th>Nome</th><th>E-mail</th><th>Status</th><th>Locais</th><th>Afastamentos</th><th></th></tr></thead><tbody>' +
      (rows || '<tr data-nofilter><td colspan="6"><div class="empty">Nenhum docente.</div></td></tr>') +
      '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="6"><div class="empty">Nenhum docente encontrado.</div></td></tr></tbody></table></div>';
  };
  window.Views.docentes_mount = function () {
    document.querySelector('[data-add]').addEventListener('click', () => window.Forms.docente(null, () => window.rerender()));
    document.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => window.Forms.docente(b.getAttribute('data-edit'), () => window.rerender())));
    const tb = document.querySelector('.tbl-wrap tbody');
    window.UI.wireSearch(document.getElementById('busca-docentes'), tb, (n, q) => {
      const vazio = tb.querySelector('.sem-resultado'); if (vazio) vazio.style.display = (n === 0 && q) ? '' : 'none';
    });
  };
})();
