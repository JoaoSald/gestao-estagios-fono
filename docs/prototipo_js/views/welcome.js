/* welcome.js — Tela de boas-vindas (sem ciclo ativo / após encerramento). */
(function () {
  'use strict';
  const { icon, esc } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  window.Views.welcome = function () {
    const st = S.get();
    const anos = [...new Set(st.historico.map((h) => h.ano))].sort((a, b) => b - a);
    const ultimoAno = anos[0];
    const encerrados = st.ciclos.filter((c) => c.status === 'encerrado').length;

    return '<div class="welcome"><div class="welcome-card">' +
      '<div class="hero-logo">' + icon('logo') + '</div>' +
      '<h1>Nenhum ciclo ativo</h1>' +
      '<p>Abra um novo ciclo de estágios para iniciar o cadastro da base, gerar a primeira escala e acompanhar a operação ao longo do ano.</p>' +
      '<div class="flex" style="justify-content:center;gap:.7rem">' +
        '<button class="btn btn-primary" id="btn-abrir">' + icon('plus') + ' Abrir novo ciclo</button>' +
        (anos.length ? '<button class="btn btn-secondary" id="btn-hist">' + icon('history') + ' Ver histórico</button>' : '') +
      '</div>' +
      (anos.length ? '<div class="card mt" style="text-align:left;margin-top:2rem">' +
        '<div class="card-body"><div class="flex between mb"><b>Anos anteriores</b>' +
          '<span class="badge b-neutral">' + encerrados + ' ciclo(s) encerrado(s)</span></div>' +
        anos.map((a) => {
          const egressos = st.historico.filter((h) => h.ano === a);
          const completos = egressos.filter((e) => e.situacao === 'ciclo_completo').length;
          return '<div class="flex between" style="padding:.6rem 0;border-top:1px solid var(--border)">' +
            '<div><b>' + a + '</b> <span class="dim">· ' + egressos.length + ' egressos</span></div>' +
            '<span class="badge b-concluida"><span class="dt"></span>' + completos + ' completos</span></div>';
        }).join('') +
      '</div></div>' : '') +
      '</div></div>';
  };

  window.Views.welcome_mount = function () {
    document.getElementById('btn-abrir').addEventListener('click', abrirCicloModal);
    const h = document.getElementById('btn-hist');
    if (h) h.addEventListener('click', () => {
      // cria acesso temporário ao histórico sem ciclo ativo
      window.Views.historico_standalone();
    });
  };

  function abrirCicloModal() {
    const ano = new Date().getFullYear();
    window.UI.modal({
      titulo: 'Abrir novo ciclo',
      corpo:
        '<p class="muted mb">Defina o intervalo do ciclo. É com base no início→fim que o sistema prevê o fechamento de carga e os alertas de risco.</p>' +
        '<div class="form-grid">' +
          '<div class="field"><label>Data de início</label><input class="input" type="date" id="ci" value="' + ano + '-03-02"></div>' +
          '<div class="field"><label>Data de fim</label><input class="input" type="date" id="cf" value="' + ano + '-12-11"></div>' +
        '</div><div class="field-err" id="err" style="display:none"></div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>' +
              '<button class="btn btn-primary" id="ok">' + icon('arrowRight') + ' Criar e iniciar bootstrap</button>',
      onMount(el, close) {
        el.querySelector('#ok').addEventListener('click', () => {
          const ini = el.querySelector('#ci').value;
          const fim = el.querySelector('#cf').value;
          const err = el.querySelector('#err');
          if (!ini || !fim) { err.textContent = 'Preencha as duas datas.'; err.style.display = 'block'; return; }
          if (fim <= ini) { err.textContent = 'A data de fim deve ser posterior ao início.'; err.style.display = 'block'; return; }
          S.abrirCiclo(ini, fim);
          close();
          window.UI.toast('Ciclo aberto — vamos ao bootstrap', 'success');
          location.hash = '#/bootstrap';
        });
      },
    });
  }
})();
