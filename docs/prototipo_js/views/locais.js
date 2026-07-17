/* locais.js — Lista de locais + indisponibilidade temporária (só na operação). */
(function () {
  'use strict';
  const { icon, esc, fmtData } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};
  const DIA = { segunda: 'Seg', terca: 'Ter', quarta: 'Qua', quinta: 'Qui', sexta: 'Sex', sabado: 'Sáb' };

  window.Views.locais = function () {
    const st = S.get();
    const rows = st.locais.map((l) => {
      const ar = st.areas.find((a) => a.id === l.area_id);
      const doc = st.docentes.find((d) => d.id === l.docente_id);
      const prec = S.preceptorDoLocal(l);
      const uso = st.alocacoes.filter((a) => a.local_id === l.id && a.status === 'ativa').length;
      const indisp = st.indisponibilidades_local.filter((i) => i.local_id === l.id);
      const indispBadge = indisp.length ? '<span class="badge b-risco"><span class="dt"></span>' + indisp.length + ' indisp.</span>' : '';
      return '<tr>' +
        '<td><span class="area-pill" style="background:' + ar.cor + '22;color:' + ar.cor + '"><span class="dt" style="background:' + ar.cor + '"></span>' + esc(ar.nome) + '</span></td>' +
        '<td><b>' + esc(l.campo) + '</b><div class="hint">' + esc(doc ? doc.nome : '') + (prec ? ' · <span class="dim">preceptor:</span> ' + esc(prec.nome) + (prec.tipo === 'docente' ? ' <span class="dim">(docente)</span>' : '') : '') + '</div></td>' +
        '<td>' + window.UI.diasLabel(l) + ' · ' + window.UI.turnoLabel(l.turno) + ' · ' + l.hora_inicio + '–' + l.hora_fim + '</td>' +
        '<td>' + uso + '/' + l.capacidade + ' vagas</td>' +
        '<td>' + (l.ativo ? '<span class="badge b-concluida"><span class="dt"></span>ativo</span>' : '<span class="badge b-neutral">inativo</span>') + ' ' + indispBadge + '</td>' +
        '<td><div class="row-actions">' +
          '<button class="icon-btn btn-sm" data-indisp="' + l.id + '" title="Indisponibilidade">' + icon('calendarOff') + '</button>' +
          '<button class="icon-btn btn-sm" data-edit="' + l.id + '">' + icon('edit') + '</button>' +
          '<button class="icon-btn btn-sm" data-del="' + l.id + '">' + icon('trash') + '</button></div></td></tr>';
    }).join('');
    return '<div class="page-head"><div class="row"><div><h1>Locais de estágio</h1><p>' + st.locais.length + ' cenário(s) de prática · a indisponibilidade temporária é exclusiva da operação</p></div>' +
      '<button class="btn btn-primary" data-add>' + icon('plus') + ' Novo local</button></div></div>' +
      '<div class="flex flex-wrap mb" style="gap:.8rem">' + window.UI.searchBox('busca-locais', 'Buscar por área, campo ou docente…') + '</div>' +
      '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr><th>Área</th><th>Campo / Docente</th><th>Quando</th><th>Ocupação</th><th>Status</th><th></th></tr></thead><tbody>' +
      (rows || '<tr data-nofilter><td colspan="6"><div class="empty">Nenhum local.</div></td></tr>') +
      '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="6"><div class="empty">Nenhum local encontrado.</div></td></tr></tbody></table></div>';
  };

  window.Views.locais_mount = function () {
    document.querySelector('[data-add]').addEventListener('click', () => window.Forms.local(null, () => window.rerender()));
    document.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => window.Forms.local(b.getAttribute('data-edit'), () => window.rerender())));
    document.querySelectorAll('[data-indisp]').forEach((b) => b.addEventListener('click', () => window.Forms.indisponibilidade(b.getAttribute('data-indisp'), () => window.rerender())));
    document.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => window.Forms.remover('locais', b.getAttribute('data-del'), 'Local', 'Local removido — realocar estágios')));
    const tb = document.querySelector('.tbl-wrap tbody');
    window.UI.wireSearch(document.getElementById('busca-locais'), tb, (n, q) => {
      const vazio = tb.querySelector('.sem-resultado'); if (vazio) vazio.style.display = (n === 0 && q) ? '' : 'none';
    });
  };
})();
