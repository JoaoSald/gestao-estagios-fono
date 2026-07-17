/* encerrar.js — Fluxo 3: assistente de encerramento em 3 etapas. */
(function () {
  'use strict';
  const { icon, esc, fmtData } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  let etapa = 1;

  window.Views.encerrar = function () {
    const c = S.cicloAtivo();
    const ano = S.parse(c.data_inicio).getFullYear();
    S.atualizarConclusoes();

    const passos = ['Revisão do estado final', 'Prévia do histórico', 'Confirmação'];
    const stepper = '<div class="stepper">' + passos.map((p, i) => {
      const n = i + 1, cls = n < etapa ? 'done' : n === etapa ? 'current' : '';
      return '<div class="step ' + cls + '"><span class="num">' + (n < etapa ? icon('check') : n) + '</span><span>' + p + '</span></div>' +
        (i < passos.length - 1 ? '<span class="step-line ' + (n < etapa ? 'done' : '') + '"></span>' : '');
    }).join('') + '</div>';

    return '<div class="page-head"><h1>Encerrar ciclo ' + ano + '</h1><p>Grava o histórico do ano e zera a operação para o próximo ciclo · ação irreversível</p></div>' +
      stepper + '<div class="bootstrap-body">' + etapaBody(ano) + '</div>';
  };

  function etapaBody(ano) {
    const st = S.get();
    const resumo = st.alunos.map((al) => {
      const p = S.progressoAluno(al.id);
      return { al, p };
    });
    const completos = resumo.filter((r) => r.p.concluidas === r.p.totalAreas).length;
    const pendentes = resumo.length - completos;

    if (etapa === 1) {
      const pend = resumo.filter((r) => r.p.concluidas < r.p.totalAreas).map((r) => {
        // "em aberto" = só áreas do PLANO não concluídas; 'iniciar' = não faz neste ciclo (não é pendência)
        const faltam = r.p.areasInfo.filter((a) => a.estado !== 'concluida' && a.estado !== 'iniciar').map((a) => a.area.nome);
        return '<tr><td><b>' + esc(r.al.nome) + '</b></td><td>' + r.p.concluidas + '/' + r.p.totalAreas + '</td>' +
          '<td class="muted">' + faltam.slice(0, 4).join(', ') + (faltam.length > 4 ? '…' : '') + '</td></tr>';
      }).join('');
      return '<div class="stack">' +
        '<div class="grid g-3">' +
          kpi('Alunos', resumo.length, 'users', '') +
          kpi('Concluíram tudo', completos, 'checkCircle', '') +
          kpi('Com pendência', pendentes, 'alert', pendentes ? 'warn' : '') + '</div>' +
        '<div class="card"><div class="card-head"><h3>Pendências (serão gravadas como estão)</h3><span class="card-sub">Pendências não impedem o encerramento.</span></div>' +
          '<div class="card-body">' + (pend ? '<div class="tbl-wrap scroll-x"><table class="tbl"><thead><tr><th>Aluno</th><th>Áreas</th><th>Áreas em aberto</th></tr></thead><tbody>' + pend + '</tbody></table></div>'
            : '<div class="flex" style="gap:.6rem;color:var(--st-concluida)">' + icon('checkCircle') + '<span style="color:var(--text)">Todos concluíram suas áreas.</span></div>') + '</div></div>' +
        foot(false, true);
    }
    if (etapa === 2) {
      const rows = resumo.map((r) => '<tr><td><b>' + esc(r.al.nome) + '</b></td><td>' + esc(r.al.matricula) + '</td>' +
        '<td>' + r.p.concluidas + '/' + r.p.totalAreas + '</td><td>' + r.p.totalCump + ' h</td>' +
        '<td>' + (r.p.concluidas === r.p.totalAreas ? '<span class="badge b-concluida"><span class="dt"></span>completo</span>' : '<span class="badge b-risco"><span class="dt"></span>pendente</span>') + '</td></tr>').join('');
      return '<div class="stack">' +
        '<div class="card"><div class="card-head"><h3>Prévia do histórico ' + ano + '</h3><span class="card-sub">É o retrato que será arquivado — confira antes de assinar.</span></div>' +
          '<div class="card-body"><div class="tbl-wrap scroll-x"><table class="tbl"><thead><tr><th>Aluno</th><th>Matrícula</th><th>Áreas</th><th>Carga total</th><th>Situação</th></tr></thead><tbody>' + rows + '</tbody></table></div></div></div>' +
        foot(true, true);
    }
    // etapa 3 — confirmação forte
    return '<div class="stack"><div class="card"><div class="card-body text-c">' +
      '<div class="al-avatar" style="margin:0 auto 1rem;background:color-mix(in srgb,var(--st-risco) 30%,transparent);color:var(--st-risco)">' + icon('alert') + '</div>' +
      '<h3>Confirmação irreversível</h3>' +
      '<p class="muted">Ao confirmar, o histórico de <b>' + resumo.length + ' alunos</b> será gravado, o ciclo será marcado como <b>encerrado</b> e a operação será zerada. Nada é apagado — os dados continuam no banco, amarrados ao ciclo.</p>' +
      '<div class="field" style="max-width:260px;margin:1.2rem auto 0"><label>Digite o ano do ciclo para confirmar</label>' +
        '<input class="input" id="conf-ano" placeholder="' + ano + '" style="text-align:center;font-size:1.2rem;font-weight:700"></div>' +
      '<div class="field-err" id="conf-err" style="display:none"></div>' +
      '</div></div>' + foot(true, false, ano);
  }

  function kpi(k, v, ic, cls) { return '<div class="kpi ' + cls + '"><div class="khead"><span class="kicon">' + icon(ic) + '</span>' + k + '</div><div class="kval">' + v + '</div></div>'; }

  function foot(voltar, avancar, ano) {
    return '<div class="wizard-foot">' +
      (voltar ? '<button class="btn btn-secondary" id="e-voltar">' + icon('chevronLeft') + ' Voltar</button>' : '<a href="#/painel" class="btn btn-ghost">Cancelar</a>') +
      (avancar ? '<button class="btn btn-primary" id="e-avancar">Avançar ' + icon('chevronRight') + '</button>' :
        '<button class="btn btn-danger" id="e-confirmar">' + icon('power') + ' Encerrar ciclo definitivamente</button>') +
      '</div>';
  }

  window.Views.encerrar_mount = function () {
    const c = S.cicloAtivo();
    const ano = S.parse(c.data_inicio).getFullYear();
    const av = document.getElementById('e-avancar');
    if (av) av.addEventListener('click', () => { etapa++; window.rerender(); });
    const vt = document.getElementById('e-voltar');
    if (vt) vt.addEventListener('click', () => { etapa--; window.rerender(); });
    const cf = document.getElementById('e-confirmar');
    if (cf) cf.addEventListener('click', () => {
      const val = document.getElementById('conf-ano').value.trim();
      const err = document.getElementById('conf-err');
      if (val !== String(ano)) { err.textContent = 'Digite exatamente "' + ano + '" para confirmar.'; err.style.display = 'block'; return; }
      S.encerrarCiclo();
      etapa = 1;
      window.UI.toast('Ciclo ' + ano + ' encerrado e arquivado no histórico', 'success');
      location.hash = '#/welcome';
    });
  };
})();
