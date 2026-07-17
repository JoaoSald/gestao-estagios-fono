/* aluno.js — Detalhe do aluno: áreas concluídas, % carga, prazo, card por área. */
(function () {
  'use strict';
  const { icon, esc, fmtData } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  const ESTADO_LABEL = { iniciar: 'Não faz neste ciclo', andamento: 'Em andamento', aguardando: 'Aguardando vaga', concluida: 'Concluída', risco: 'Em risco', interrompida: 'Interrompida' };

  window.Views.aluno = function (id) {
    const st = S.get();
    const al = st.alunos.find((a) => a.id === id);
    if (!al) return '<div class="empty">Aluno não encontrado. <a href="#/alunos">Voltar</a></div>';
    S.atualizarConclusoes();
    const p = S.progressoAluno(id);
    const ini = al.nome.split(' ').map((x) => x[0]).slice(0, 2).join('').toUpperCase();

    const cards = p.areasInfo.map((a) => {
      const pct = a.pct;
      const corBar = { iniciar: 'var(--st-iniciar)', andamento: 'var(--st-andamento)', aguardando: 'var(--st-aguardando)', concluida: 'var(--st-concluida)', risco: 'var(--st-risco)', interrompida: 'var(--st-interrompida)' }[a.estado];
      // "Interromper" só faz sentido em áreas que o aluno está de fato cursando.
      const podeInterromper = a.estado === 'andamento' || a.estado === 'risco';
      const metaDir =
        a.estado === 'concluida'    ? 'concluída em ' + fmtData(a.mat.data_conclusao) :
        a.estado === 'interrompida' ? 'interrompida em ' + fmtData(a.mat.data_interrupcao) +
              (a.mat.motivo_interrupcao ? ' · ' + esc(a.mat.motivo_interrupcao) : '') :
        a.estado === 'iniciar'      ? 'não faz neste ciclo' :
        a.estado === 'aguardando'   ? aguardandoMeta(a.area.id, id) :
                                      'previsão: ' + fmtData(a.prevista);
      const maeNome = a.area.area_mae ? ((st.areas.find((x) => x.id === a.area.area_mae) || {}).nome || '') : '';
      const nomeArea = (maeNome ? '<span class="dim" style="font-weight:600">' + esc(maeNome) + ' · </span>' : '') + esc(a.area.nome);
      return '<div class="area-card" style="--laccent:' + a.area.cor + '">' +
        '<div class="achead"><b>' + nomeArea + '</b>' +
          '<span class="badge b-' + a.estado + '"><span class="dt"></span>' + ESTADO_LABEL[a.estado] + '</span></div>' +
        window.UI.bar(pct, corBar) +
        '<div class="area-meta"><span>' + a.encontros.feitos + ' / ' + a.encontros.total + ' encontros · ' + pct + '%</span>' +
          '<span>' + metaDir + '</span></div>' +
        (podeInterromper
          ? '<div class="mt-sm" style="text-align:right"><button class="btn btn-ghost btn-sm" data-interromper="' + a.area.id + '">' +
              icon('calendarOff') + ' Interromper estágio</button></div>'
          : '') +
      '</div>';
    }).join('');

    // Resumo do porquê do risco: áreas que não concluem dentro do ciclo + áreas ainda na fila.
    const ciclo = S.cicloAtivo();
    const fimCiclo = ciclo ? ciclo.data_fim : null;
    const motivos = [];
    p.areasInfo.filter((a) => a.estado === 'risco').forEach((a) => {
      motivos.push('<li><b>' + esc(a.area.nome) + '</b> — conclusão prevista para ' + fmtData(a.prevista) +
        (fimCiclo ? ', depois do fim do ciclo (' + fmtData(fimCiclo) + ')' : '') + '</li>');
    });
    p.areasInfo.filter((a) => a.estado === 'aguardando').forEach((a) => {
      motivos.push('<li><b>' + esc(a.area.nome) + '</b> — ' + aguardandoMeta(a.area.id, id) + '</li>');
    });
    const riscoBox = p.risco
      ? '<div class="mt" style="background:color-mix(in srgb,var(--st-risco) 9%,transparent);border:1px solid color-mix(in srgb,var(--st-risco) 32%,transparent);border-radius:var(--radius);padding:.7rem .9rem">' +
          '<div style="display:flex;align-items:center;gap:.4rem;font-weight:700;color:var(--st-risco);margin-bottom:.4rem">' +
            icon('alert') + ' Por que está em risco</div>' +
          '<ul class="dim" style="margin:0;padding-left:1.15rem;font-size:.82rem;line-height:1.55">' + motivos.join('') + '</ul>' +
        '</div>'
      : '';

    return '<div class="page-head"><a href="#/alunos" class="btn btn-ghost btn-sm mb">' + icon('chevronLeft') + ' Voltar aos alunos</a>' +
      '<div class="card"><div class="card-body">' +
      '<div class="al-header"><div class="al-avatar">' + ini + '</div>' +
        '<div style="flex:1"><h1 style="font-size:1.4rem">' + esc(al.nome) + '</h1>' +
        '<p class="muted" style="margin:.2rem 0 0">Matrícula ' + esc(al.matricula) + ' · ' +
          (p.fase5 ? '7º semestre (mini-ciclo · Audiologia I)' : '9º/10º semestre') + ' · prioridade #' + al.ordenamento + '</p>' +
        (!p.fase5 && p.preReqArea ? '<div class="mt-sm">' + (p.preReqConcluido
            ? '<span class="badge b-concluida"><span class="dt"></span>Pré-requisito ' + esc(p.preReqArea.nome) + ' concluído</span>'
            : '<span class="badge b-aguardando" title="Responsabilidade compartilhada: confira o histórico do aluno. Não bloqueia a alocação."><span class="dt"></span>Sem registro de ' + esc(p.preReqArea.nome) + ' — conferir</span>') + '</div>' : '') +
        '</div>' +
        '<button class="btn btn-secondary" id="btn-cal">' + icon('calendar') + ' Encontros</button></div>' +
      '<div class="stat-row mt" style="border-top:1px solid var(--border);padding-top:1.1rem">' +
        stat('Áreas concluídas', p.concluidas + ' / ' + p.totalAreas) +
        stat('Carga cumprida', p.pctCarga + '%') +
        stat('Dias restantes', p.diasRest) +
        stat('Situação', p.risco ? '<span style="color:var(--st-risco)">Em risco</span>' : '<span style="color:var(--st-concluida)">No prazo</span>') +
      '</div>' + riscoBox + '</div></div></div>' +
      '<h3 class="mb">Áreas do currículo</h3>' +
      '<div class="grid g-2">' + cards + '</div>';
  };

  function stat(k, v) { return '<div class="stat"><div class="k">' + k + '</div><div class="v">' + v + '</div></div>'; }

  // Texto do card/lista para uma área que o aluno AGUARDA (na fila): posição + previsão de início.
  function aguardandoMeta(areaId, alunoId) {
    const pv = S.previsaoInicioArea(areaId);
    const pos = pv.fila.findIndex((f) => f.aluno_id === alunoId);
    const eu = pos >= 0 ? pv.fila[pos] : null;
    const posTxt = pos >= 0 ? (pos + 1) + 'º de ' + pv.fila.length + ' na fila' : 'na fila';
    if (eu && eu.previsao) return posTxt + ' · início previsto ' + fmtData(eu.previsao) + (eu.remanejamento ? ' (por remanejamento)' : '');
    return posTxt + ' · ' + esc((eu && eu.motivo) || 'sem previsão neste ciclo');
  }

  window.Views.aluno_mount = function (id) {
    const bc = document.getElementById('btn-cal');
    if (bc) bc.addEventListener('click', () => window.Views.calendarioAluno(id));

    document.querySelectorAll('[data-interromper]').forEach((b) => b.addEventListener('click', () => {
      const areaId = b.getAttribute('data-interromper');
      const st = S.get();
      const al = st.alunos.find((a) => a.id === id);
      const ar = st.areas.find((a) => a.id === areaId);
      window.UI.modal({
        titulo: 'Interromper estágio',
        corpo:
          '<p class="muted mb">Interromper <b>' + esc(ar ? ar.nome : '') + '</b> de <b>' + esc(al ? al.nome : '') + '</b>. ' +
          'A matrícula fica registrada como <b>interrompida</b> (não é apagada): a vaga é liberada para a fila e a área fica ' +
          'pendente para refazer no próximo ciclo.</p>' +
          '<div class="field"><label>Motivo (opcional)</label>' +
          '<textarea class="input" id="f-motivo" rows="3" placeholder="Ex.: afastamento por saúde"></textarea></div>',
        rodape:
          '<button class="btn btn-secondary" data-close>Cancelar</button>' +
          '<button class="btn btn-primary" data-confirmar>Interromper estágio</button>',
        onMount(el, close) {
          const btn = el.querySelector('[data-confirmar]');
          if (!btn) return;
          btn.addEventListener('click', () => {
            const ta = el.querySelector('#f-motivo');
            const motivo = ta ? (ta.value || '').trim() : '';
            const ok = S.desmatricular(id, areaId, motivo);
            if (close) close();
            if (ok) {
              window.UI.toast('Estágio interrompido — vaga liberada', 'success');
              if (window.rerender) window.rerender();
            } else {
              window.UI.toast('Não foi possível interromper (área não está em andamento)', 'error');
            }
          });
        },
      });
    }));
  };
})();
