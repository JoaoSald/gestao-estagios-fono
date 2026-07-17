/* remanejo.js — Pré-visualização e aplicação do remanejamento cirúrgico. */
(function () {
  'use strict';
  const { icon, esc } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  // rota #/remanejar → painel com o modal aberto por cima
  window.Views.remanejar = function () { return window.Views.painel(); };
  window.Views.remanejar_mount = function () { window.Views.painel_mount(); window.Views.remanejar_open(); };

  window.Views.remanejar_open = function () {
    const c = S.cicloAtivo();
    if (!c || !c.escala_desatualizada) {
      window.UI.modal({
        titulo: 'Remanejamento',
        corpo: '<div class="flex" style="gap:.6rem;color:var(--st-concluida)">' + icon('checkCircle') +
          '<span style="color:var(--text)">Nenhuma alteração pendente. A escala está atualizada.</span></div>',
        rodape: '<button class="btn btn-primary" data-close>Fechar</button>',
      });
      return;
    }
    const p = S.previewRemanejo();
    const gatilhos = p.gatilhos.map((g) => '<div class="flex" style="gap:.6rem;padding:.35rem 0"><span class="tl-dot" style="position:static"></span><span>' + esc(g.texto) + '</span></div>').join('');
    const semVaga = p.sem_vaga.length ? p.sem_vaga.map((s) => '<li><b>' + esc(s.aluno) + '</b> segue sem vaga em ' + esc(s.area) + '</li>').join('') : '';

    const resumo = '<div class="grid g-3 mb">' +
      mini('Sessões movidas', p.sessoes_movidas) +
      mini('Fila → em andamento', p.fila_materializavel || 0) +
      mini('Realocadas de cenário', p.realocadas) +
      mini('Alunos afetados', p.alunos_afetados) + '</div>';

    window.UI.modal({
      titulo: 'Pré-visualização do remanejamento', wide: true,
      corpo:
        '<p class="muted mb">O motor identificou o que muda a partir dos gatilhos acumulados. Só o afetado é recalculado — ' +
        '<b>nada nas áreas concluídas, sessões cumpridas ou alocações travadas será tocado.</b></p>' +
        resumo +
        '<div class="card mb"><div class="card-head"><h3>Gatilhos na fila (' + p.gatilhos.length + ')</h3></div>' +
          '<div class="card-body">' + (gatilhos || '<span class="dim">—</span>') + '</div></div>' +
        (semVaga ? '<div class="banner-remanejo" style="margin:0"><div class="bico">' + icon('alert') + '</div><div class="btxt"><b>Atenção</b>' +
          '<ul style="margin:.3rem 0 0;padding-left:1.1rem">' + semVaga + '</ul></div></div>' : ''),
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="btn-aplicar">' + icon('shuffle') + ' Confirmar remanejamento</button>',
      onMount(el, close) {
        el.querySelector('#btn-aplicar').addEventListener('click', () => {
          const res = S.aplicarRemanejo();
          close();
          window.UI.toast('Remanejamento aplicado: ' + res.sessoes_movidas + ' sessões movidas' +
            (res.fila_materializavel ? ' · ' + res.fila_materializavel + ' da fila em andamento' : ''), 'success');
          if (location.hash.indexOf('remanejar') >= 0) location.hash = '#/painel';
          else window.rerender();
        });
      },
    });
  };

  function mini(k, v) {
    return '<div class="kpi"><div class="khead">' + esc(k) + '</div><div class="kval">' + v + '</div></div>';
  }
})();
