/* preceptores.js — Lista de preceptores (responsáveis de campo, externos à UFCSPA). */
(function () {
  'use strict';
  const { icon, esc } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  window.Views.preceptores = function () {
    const st = S.get();
    const lista = st.preceptores || [];
    const rows = lista.map((p) => {
      const nLocais = st.locais.filter((l) => l.preceptor_id === p.id && l.ativo).length;
      const nAfast = st.afastamentos.filter((a) => a.preceptor_id === p.id).length;
      return '<tr>' +
        '<td><b>' + esc(p.nome) + '</b></td>' +
        '<td>' + (p.email ? esc(p.email) : '<span class="dim">—</span>') + '</td>' +
        '<td>' + (p.ativo ? '<span class="badge b-concluida"><span class="dt"></span>ativo</span>' : '<span class="badge b-neutral">desligado</span>') + '</td>' +
        '<td>' + nLocais + ' local(is)</td><td>' + nAfast + ' afastamento(s)</td>' +
        '<td><div class="row-actions"><button class="icon-btn btn-sm" data-edit="' + p.id + '">' + icon('edit') + '</button></div></td></tr>';
    }).join('');
    return '<div class="page-head"><div class="row"><div><h1>Preceptores</h1><p>' + lista.length + ' preceptor(es) · responsáveis de campo (externos) — a conta é o e-mail; atravessa ciclos</p></div>' +
      '<button class="btn btn-primary" data-add>' + icon('plus') + ' Novo preceptor</button></div></div>' +
      '<div class="flex flex-wrap mb" style="gap:.8rem">' + window.UI.searchBox('busca-preceptores', 'Buscar preceptor por nome ou e-mail…') + '</div>' +
      '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr><th>Nome</th><th>E-mail</th><th>Status</th><th>Locais</th><th>Afastamentos</th><th></th></tr></thead><tbody>' +
      (rows || '<tr data-nofilter><td colspan="6"><div class="empty">Nenhum preceptor.</div></td></tr>') +
      '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="6"><div class="empty">Nenhum preceptor encontrado.</div></td></tr></tbody></table></div>';
  };

  window.Views.preceptores_mount = function () {
    document.querySelector('[data-add]').addEventListener('click', () => window.Forms.preceptor(null, () => window.rerender()));
    document.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => window.Forms.preceptor(b.getAttribute('data-edit'), () => window.rerender())));
    const tb = document.querySelector('.tbl-wrap tbody');
    window.UI.wireSearch(document.getElementById('busca-preceptores'), tb, (n, q) => {
      const vazio = tb.querySelector('.sem-resultado'); if (vazio) vazio.style.display = (n === 0 && q) ? '' : 'none';
    });
  };
})();
