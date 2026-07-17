/* painel.js — Painel de Operação (ciclo em andamento). */
(function () {
  'use strict';
  const { icon, esc, fmtData, fmtDataCurta } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  window.Views.painel = function () {
    const st = S.get();
    const c = S.cicloAtivo();
    S.atualizarConclusoes();
    const hoje = S.hoje();

    const proximos = st.eventos.filter((e) => e.data_fim >= hoje).sort((a, b) => a.data_inicio.localeCompare(b.data_inicio)).slice(0, 5);
    const risco = S.alunosEmRisco();
    const locaisAtivos = st.locais.filter((l) => l.ativo).length;

    const kpis = [
      ['Alunos', st.alunos.length, 'users', 'no ciclo', ''],
      ['Locais ativos', locaisAtivos, 'building', 'cenários de prática', ''],
      ['Estágios gerados', st.alocacoes.filter((a) => a.status === 'ativa').length, 'grid', 'alocações ativas', ''],
      ['Eventos próximos', proximos.length, 'calendar', 'nos próximos dias', ''],
      ['Alunos em risco', risco, 'alert', 'de não fechar no prazo', risco > 0 ? 'warn' : ''],
    ].map((k) => '<div class="kpi ' + k[4] + '"><div class="khead"><span class="kicon">' + icon(k[2]) + '</span>' + k[0] +
      '</div><div class="kval">' + k[1] + '</div><div class="kfoot">' + k[3] + '</div></div>').join('');

    const acoes = [
      ['user', 'Novo aluno', 'aluno'], ['building', 'Novo local', 'local'], ['calendar', 'Novo evento', 'evento'],
      ['calendarOff', 'Novo afastamento', 'afastamento'], ['shuffle', 'Remanejar', '_remanejar'],
    ].map((a) => '<button class="qa-btn" data-qa="' + a[2] + '"><span class="qi">' + icon(a[0]) + '</span><span>' + a[1] + '</span></button>').join('');

    const eventosHtml = proximos.length ? proximos.map((e) => {
      const [, m, d] = e.data_inicio.split('-');
      return '<div class="evrow"><div class="evdate"><div class="d">' + d + '</div><div class="m">' + window.UI.MESES[+m - 1] + '</div></div>' +
        '<div class="evinfo"><b>' + esc(e.nome) + '</b><span>' + e.tipo + ' · ' + (e.bloqueia_estagio ? 'bloqueia estágio' : 'não bloqueia') + '</span></div>' +
        '<span class="badge b-neutral pull-right">' + e.origem + '</span></div>';
    }).join('') : '<div class="empty" style="padding:1.5rem"><span class="dim">Sem eventos próximos.</span></div>';

    const ativHtml = st.atividade.length ? '<div class="timeline">' + st.atividade.slice(0, 8).map((a) =>
      '<div class="tl-item"><span class="tl-dot"></span><div class="txt">' + esc(a.texto) + '</div><div class="when">' + fmtData(a.quando) + '</div></div>').join('') + '</div>'
      : '<div class="empty" style="padding:1.5rem"><span class="dim">Nenhuma atividade ainda.</span></div>';

    const banner = c.escala_desatualizada ? bannerRemanejo(st.fila_remanejo.length) : '';
    const vlf = S.vagasLivresComFila();
    // só alerta quando há alguém que REALMENTE entra numa vaga livre (respeitando
    // conflito/restrição/30h) — evita banner inútil quando a fila só tem incompatíveis.
    const matCount = vlf.length ? S.previewRemanejo().fila_materializavel : 0;
    const bannerVaga = matCount > 0 ? bannerVagaLivre(vlf, matCount) : '';

    return '<div class="page-head"><div class="row"><div><h1>Painel de Operação</h1>' +
      '<p>Ciclo ' + S.parse(c.data_inicio).getFullYear() + ' · ' + fmtData(c.data_inicio) + ' → ' + fmtData(c.data_fim) + '</p></div></div></div>' +
      bannerVaga +
      banner +
      '<div class="grid g-5 mb">' + kpis + '</div>' +
      '<div class="grid g-3 mb">' +
        '<div class="card" style="grid-column:span 2"><div class="card-head"><h3>Ações rápidas</h3></div><div class="card-body"><div class="qa">' + acoes + '</div></div></div>' +
        '<div class="card"><div class="card-head"><h3>Próximos eventos</h3><button class="btn btn-ghost btn-sm" data-go="#/eventos">Ver todos</button></div><div class="card-body">' + eventosHtml + '</div></div>' +
      '</div>' +
      '<div class="grid g-2">' +
        '<div class="card"><div class="card-head"><h3>Progresso da turma</h3><button class="btn btn-ghost btn-sm" data-go="#/estagios">Ver escala</button></div><div class="card-body">' + progressoTurma() + '</div></div>' +
        '<div class="card"><div class="card-head"><h3>Atividade recente</h3></div><div class="card-body">' + ativHtml + '</div></div>' +
      '</div>';
  };

  function bannerVagaLivre(vlf, matCount) {
    const areas = vlf.map((v) => esc(v.area.nome) + ' (' + v.vagasLivres + ' vaga' + (v.vagasLivres > 1 ? 's' : '') + ' · ' + v.fila + ' na fila)').join(' · ');
    return '<div class="banner-remanejo"><div class="bico">' + icon('checkCircle') + '</div>' +
      '<div class="btxt"><b>Vaga livre com fila de espera — ' + matCount + ' aluno(s) podem entrar</b>' +
      '<span>' + areas + '. Normalmente uma conclusão liberou a vaga. Remanejar coloca a fila (aguardando) em andamento por prioridade — respeitando conflito de horário, restrição de local e teto de 30h; quem não couber segue aguardando.</span></div>' +
      '<div class="bacts"><button class="btn btn-primary btn-sm" id="ban-vagalivre">' + icon('shuffle') + ' Remanejar agora</button></div></div>';
  }

  function bannerRemanejo(n) {
    return '<div class="banner-remanejo"><div class="bico">' + icon('alert') + '</div>' +
      '<div class="btxt"><b>' + n + ' alteração(ões) pendente(s) afetam a escala</b>' +
      '<span>A escala exibida está marcada como desatualizada. Recalcule apenas o afetado — nada nas áreas concluídas será tocado.</span></div>' +
      '<div class="bacts"><button class="btn btn-secondary btn-sm" id="ban-detalhes">Ver detalhes</button>' +
      '<button class="btn btn-primary btn-sm" id="ban-remanejar">' + icon('shuffle') + ' Remanejar agora</button></div></div>';
  }

  function progressoTurma() {
    const st = S.get();
    // barra segmentada agregando estados de todas as matrículas + áreas a iniciar
    let iniciar = 0, andamento = 0, aguardando = 0, concluida = 0, risco = 0;
    st.alunos.forEach((al) => {
      S.progressoAluno(al.id).areasInfo.forEach((a) => {
        if (a.estado === 'iniciar') iniciar++; else if (a.estado === 'andamento') andamento++;
        else if (a.estado === 'aguardando') aguardando++;
        else if (a.estado === 'concluida') concluida++; else if (a.estado === 'risco') risco++;
      });
    });
    const total = iniciar + andamento + aguardando + concluida + risco || 1;
    const seg = '<div class="seg mb">' +
      span(concluida, total, 'var(--st-concluida)') + span(andamento, total, 'var(--st-andamento)') +
      span(aguardando, total, 'var(--st-aguardando)') +
      span(risco, total, 'var(--st-risco)') + span(iniciar, total, 'var(--st-iniciar)') + '</div>';
    const leg = [['concluida', 'Concluídas', concluida], ['andamento', 'Em andamento', andamento], ['aguardando', 'Aguardando', aguardando], ['risco', 'Em risco', risco], ['iniciar', 'Não faz neste ciclo', iniciar]]
      .map((l) => '<span class="badge b-' + l[0] + '"><span class="dt"></span>' + l[1] + ' · ' + l[2] + '</span>').join(' ');
    return seg + '<div class="flex flex-wrap" style="gap:.5rem">' + leg + '</div>' +
      '<p class="hint mt">Distribuição de ' + total + ' pares aluno×área no ciclo.</p>';
  }
  function span(v, total, cor) { return v ? '<span style="width:' + (v / total * 100) + '%;background:' + cor + '"></span>' : ''; }

  window.Views.painel_mount = function () {
    document.querySelectorAll('[data-qa]').forEach((b) => b.addEventListener('click', () => {
      const q = b.getAttribute('data-qa');
      if (q === '_remanejar') { window.Views.remanejar_open(); return; }
      window.Forms[q](null, () => window.rerender());
    }));
    document.querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => location.hash = b.getAttribute('data-go')));
    const bd = document.getElementById('ban-detalhes'); if (bd) bd.addEventListener('click', () => window.Views.remanejar_open());
    const br = document.getElementById('ban-remanejar'); if (br) br.addEventListener('click', () => window.Views.remanejar_open());
    const bv = document.getElementById('ban-vagalivre'); if (bv) bv.addEventListener('click', () => { S.sinalizarVagasLivres(); window.Views.remanejar_open(); });
  };
})();
