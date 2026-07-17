/* historico.js — Abas por ano; egressos com situação e carga total. */
(function () {
  'use strict';
  const { icon, esc, fmtData } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  let anoSel = null;
  let standalone = false;

  function anosDisponiveis() {
    const st = S.get();
    const anos = [...new Set(st.historico.map((h) => h.ano))];
    const c = S.cicloAtivo();
    if (c && c.status === 'em_andamento') anos.push(S.parse(c.data_inicio).getFullYear());
    return [...new Set(anos)].sort((a, b) => b - a);
  }

  function corpo() {
    const st = S.get();
    const anos = anosDisponiveis();
    if (!anoSel || anos.indexOf(anoSel) < 0) anoSel = anos[0];
    const c = S.cicloAtivo();
    const anoCorrente = c && c.status === 'em_andamento' ? S.parse(c.data_inicio).getFullYear() : null;

    const tabs = '<div class="tabs">' + anos.map((a) =>
      '<div class="tab ' + (a === anoSel ? 'active' : '') + '" data-ano="' + a + '">' + a + (a === anoCorrente ? ' · em andamento' : '') + '</div>').join('') + '</div>';

    let conteudo;
    if (anoSel === anoCorrente) {
      // ano corrente: progresso da turma (ainda não encerrado)
      S.atualizarConclusoes();
      const rows = st.alunos.slice().sort((a, b) => a.ordenamento - b.ordenamento).map((al) => {
        const p = S.progressoAluno(al.id);
        return '<tr><td><b>' + esc(al.nome) + '</b><div class="hint">' + esc(al.matricula) + '</div></td>' +
          '<td>' + p.concluidas + ' / ' + p.totalAreas + '</td>' +
          '<td><div style="min-width:120px">' + window.UI.bar(p.pctCarga, 'var(--brand-400)') + '<div class="hint">' + p.totalCump + ' h · ' + p.pctCarga + '%</div></div></td>' +
          '<td>' + (p.concluidas === p.totalAreas ? '<span class="badge b-concluida"><span class="dt"></span>completo</span>' :
            p.risco ? '<span class="badge b-risco"><span class="dt"></span>em risco</span>' : '<span class="badge b-andamento"><span class="dt"></span>em curso</span>') + '</td></tr>';
      }).join('');
      conteudo = '<div class="flex between mb" style="gap:.8rem;flex-wrap:wrap"><span class="badge b-andamento"><span class="dt"></span>Ciclo em andamento — os egressos migram ao concluir</span>' +
        window.UI.searchBox('busca-hist', 'Buscar aluno por nome…') + '</div>' +
        '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr><th>Aluno</th><th>Áreas</th><th>Carga</th><th>Situação</th></tr></thead><tbody>' + rows +
        '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="4"><div class="empty">Nenhum aluno encontrado.</div></td></tr></tbody></table></div>';
    } else {
      const egressos = st.historico.filter((h) => h.ano === anoSel);
      const completos = egressos.filter((e) => e.situacao === 'ciclo_completo').length;
      const rows = egressos.map((e) => {
        const conc = e.areas.filter((a) => a.data_conclusao).length;
        return '<tr data-hist="' + e.id + '" style="cursor:pointer"><td><b>' + esc(e.aluno_nome) + '</b><div class="hint">' + esc(e.matricula) + '</div></td>' +
          '<td>' + conc + ' / ' + e.areas.length + '</td>' +
          '<td>' + e.carga_horaria_total + ' h</td>' +
          '<td>' + (e.situacao === 'ciclo_completo' ? '<span class="badge b-concluida"><span class="dt"></span>ciclo completo</span>' : '<span class="badge b-risco"><span class="dt"></span>pendente</span>') + '</td>' +
          '<td>' + fmtData(e.encerramento) + '</td></tr>';
      }).join('');
      conteudo = '<div class="flex between mb" style="gap:.8rem;flex-wrap:wrap"><span class="dim">' + egressos.length + ' egressos · ' + completos + ' completos</span>' +
        window.UI.searchBox('busca-hist', 'Buscar egresso por nome…') +
        '<span class="badge b-neutral">somente leitura</span></div>' +
        '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr><th>Aluno</th><th>Áreas</th><th>Carga total</th><th>Situação</th><th>Encerramento</th></tr></thead><tbody>' + rows +
        '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="5"><div class="empty">Nenhum egresso encontrado.</div></td></tr></tbody></table></div>';
    }
    return tabs + conteudo;
  }

  window.Views.historico = function () {
    standalone = false;
    return '<div class="page-head"><h1>Histórico</h1><p>Retrato de cada ciclo por ano — o passado não muda</p></div>' + corpo();
  };
  window.Views.historico_mount = function () { wire(); };

  function wire() {
    document.querySelectorAll('.tab[data-ano]').forEach((t) => t.addEventListener('click', () => {
      anoSel = +t.getAttribute('data-ano');
      if (standalone) window.Views.historico_standalone(); else window.rerender();
    }));
    document.querySelectorAll('[data-hist]').forEach((r) => r.addEventListener('click', () => detalhe(r.getAttribute('data-hist'))));
    const tb = document.querySelector('.tbl-wrap tbody');
    window.UI.wireSearch(document.getElementById('busca-hist'), tb, (n, q) => {
      const vazio = tb && tb.querySelector('.sem-resultado'); if (vazio) vazio.style.display = (n === 0 && q) ? '' : 'none';
    });
  }

  function detalhe(id) {
    const e = S.get().historico.find((h) => h.id === id);
    if (!e) return;
    const linhas = e.areas.map((a) => {
      const pct = Math.min(100, Math.round((a.horas_cumpridas / a.carga_exigida) * 100));
      return '<tr><td>' + esc(a.nome) + '</td><td>' + a.horas_cumpridas + ' / ' + a.carga_exigida + ' h</td>' +
        '<td style="min-width:90px">' + window.UI.bar(pct, a.data_conclusao ? 'var(--st-concluida)' : 'var(--st-risco)') + '</td>' +
        '<td>' + (a.data_conclusao ? fmtData(a.data_conclusao) : '<span class="dim">não concluída</span>') + '</td></tr>';
    }).join('');
    window.UI.modal({
      titulo: e.aluno_nome + ' · ' + e.ano, wide: true,
      corpo: '<div class="flex between mb"><span class="dim">Matrícula ' + esc(e.matricula) + '</span>' +
        (e.situacao === 'ciclo_completo' ? '<span class="badge b-concluida"><span class="dt"></span>ciclo completo</span>' : '<span class="badge b-risco"><span class="dt"></span>pendente</span>') + '</div>' +
        '<div class="tbl-wrap scroll-x"><table class="tbl"><thead><tr><th>Área</th><th>Horas</th><th>Progresso</th><th>Conclusão</th></tr></thead><tbody>' + linhas + '</tbody></table></div>',
      rodape: '<button class="btn btn-primary" data-close>Fechar</button>',
    });
  }

  // versão full-screen acessada da tela de boas-vindas (sem ciclo ativo)
  window.Views.historico_standalone = function () {
    standalone = true;
    const app = document.getElementById('app');
    app.innerHTML = '<div class="content" style="max-width:1000px">' +
      '<div class="flex between mb"><a href="#/welcome" class="btn btn-ghost btn-sm">' + icon('chevronLeft') + ' Voltar</a></div>' +
      '<div class="page-head"><h1>Histórico</h1><p>Ciclos encerrados</p></div>' + corpo() + '</div>';
    wire();
    app.querySelector('a[href="#/welcome"]').addEventListener('click', (ev) => { ev.preventDefault(); window.rerender(); });
  };
})();
