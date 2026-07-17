/* ============================================================================
   app.js — Boot, roteamento por hash e shell de layout (sidebar + topbar).
   ============================================================================ */
(function () {
  'use strict';
  const { icon, esc } = window.UI;
  const S = window.State;

  // --- Autenticação simulada (sem backend) --------------------------------
  // "Manter conectado" persiste em localStorage; caso contrário, só na sessão.
  const AUTH_KEY = 'gestao-estagios-auth';
  const Auth = {
    autenticado() {
      try {
        return localStorage.getItem(AUTH_KEY) === 'sim' ||
               sessionStorage.getItem(AUTH_KEY) === 'sim';
      } catch (e) { return false; }
    },
    entrar(manter) {
      try {
        if (manter) localStorage.setItem(AUTH_KEY, 'sim');
        else sessionStorage.setItem(AUTH_KEY, 'sim');
      } catch (e) {}
    },
    sair() {
      try { localStorage.removeItem(AUTH_KEY); sessionStorage.removeItem(AUTH_KEY); } catch (e) {}
    },
  };
  window.Auth = Auth;

  // Rotas que exigem o layout completo (sidebar). Welcome/Bootstrap são full-screen.
  const NAV = [
    { grupo: 'CADASTROS', itens: [
      { rota: '#/alunos', label: 'Alunos', ic: 'users' },
      { rota: '#/docentes', label: 'Docentes', ic: 'teacher' },
      { rota: '#/preceptores', label: 'Preceptores', ic: 'user' },
      { rota: '#/afastamentos', label: 'Afastamentos', ic: 'calendarOff' },
      { rota: '#/locais', label: 'Locais', ic: 'building' },
      { rota: '#/eventos', label: 'Eventos', ic: 'calendar' },
    ]},
    { grupo: 'VISUALIZAÇÕES', itens: [
      { rota: '#/painel', label: 'Painel', ic: 'dashboard' },
      { rota: '#/estagios', label: 'Estágios', ic: 'grid' },
      { rota: '#/historico', label: 'Histórico', ic: 'history' },
    ]},
    { grupo: 'OPERAÇÕES', itens: [
      { rota: '#/remanejar', label: 'Remanejar', ic: 'shuffle' },
      { rota: '#/encerrar', label: 'Encerrar ciclo', ic: 'power' },
    ]},
  ];

  function parseHash() {
    const h = location.hash || '';
    const m = h.replace(/^#\//, '').split('/');
    return { nome: m[0] || '', arg: m[1] || null, raw: h };
  }

  function toggleTema() {
    const cur = document.documentElement.getAttribute('data-theme');
    const novo = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', novo);
    try { localStorage.setItem('tema', novo); } catch (e) {}
    render();
  }

  function sidebar(rotaAtual) {
    const risco = S.alunosEmRisco();
    const ciclo = S.cicloAtivo();
    let groups = NAV.map((g) => {
      const links = g.itens.map((it) => {
        const active = rotaAtual.indexOf(it.rota.replace('#/', '')) === 0 && it.rota.replace('#/', '') === rotaAtual.split('/')[0];
        let badge = '';
        if (it.rota === '#/remanejar' && ciclo && ciclo.escala_desatualizada) {
          badge = '<span class="nav-badge">' + S.get().fila_remanejo.length + '</span>';
        }
        if (it.rota === '#/painel' && risco > 0) badge = '';
        return '<div class="nav-link ' + (active ? 'active' : '') + '" data-rota="' + it.rota + '">' +
          icon(it.ic) + '<span>' + it.label + '</span>' + badge + '</div>';
      }).join('');
      return '<div class="nav-group">' + g.grupo + '</div>' + links;
    }).join('');

    const temaIc = document.documentElement.getAttribute('data-theme') === 'dark' ? 'sun' : 'moon';

    return '<aside class="sidebar" id="sidebar">' +
      '<div class="brand"><div class="logo">' + icon('logo') + '</div>' +
        '<div><div class="t1">Gestão de Estágios</div><div class="t2">Fonoaudiologia · UFCSPA</div></div></div>' +
      '<nav class="nav">' + groups + '</nav>' +
      '<div class="sidebar-foot">' +
        '<div class="al-avatar" style="width:36px;height:36px;border-radius:10px;font-size:.85rem">CO</div>' +
        '<div class="who"><b>Coordenação</b><span class="dim">Comissão de Estágios</span></div>' +
        '<button class="icon-btn pull-right" id="btn-tema" title="Alternar tema">' + icon(temaIc) + '</button>' +
        '<button class="icon-btn" id="btn-sair" title="Sair">' + icon('logout') + '</button>' +
      '</div>' +
      '<div style="padding:0 .7rem .8rem"><button class="btn btn-ghost btn-sm btn-block" id="btn-reset">' +
        icon('reset') + ' Resetar dados de demonstração</button></div>' +
      '</aside>';
  }

  function topbar() {
    const ciclo = S.cicloAtivo();
    const ano = ciclo ? S.parse(ciclo.data_inicio).getFullYear() : '';
    return '<div class="topbar">' +
      '<button class="icon-btn menu-toggle" id="btn-menu">' + icon('grid') + '</button>' +
      '<div class="spacer"></div>' +
      (ciclo ? '<span class="chip-cycle"><span class="dot"></span>Ciclo ' + ano + ' · em andamento</span>' : '') +
      '</div>';
  }

  function render() {
    const app = document.getElementById('app');
    let { nome, arg } = parseHash();

    // Máquina de estados decide o acesso.
    const ciclo = S.cicloAtivo();
    const estado = S.estadoInicial();

    // --- Gate de autenticação: sem sessão, tudo cai no login ---------------
    if (!Auth.autenticado()) {
      if (nome !== 'login') { location.hash = '#/login'; return; }
      app.innerHTML = window.Views.login();
      window.Views.login_mount && window.Views.login_mount();
      return;
    }
    // Já autenticado tentando ver o login → manda para a tela inicial.
    if (nome === 'login') { location.hash = estado.rota; return; }

    // rotas full-screen (sem shell)
    if (!nome) { location.hash = estado.rota; return; }

    if (nome === 'welcome') {
      app.innerHTML = window.Views.welcome();
      window.Views.welcome_mount && window.Views.welcome_mount();
      return;
    }
    if (nome === 'bootstrap') {
      if (!ciclo || ciclo.status !== 'rascunho') { location.hash = estado.rota; return; }
      app.innerHTML = window.Views.bootstrap();
      window.Views.bootstrap_mount && window.Views.bootstrap_mount();
      return;
    }

    // Demais rotas exigem ciclo em_andamento.
    if (!ciclo || ciclo.status !== 'em_andamento') { location.hash = estado.rota; return; }

    const viewName = {
      painel: 'painel', alunos: 'alunos', aluno: 'aluno', docentes: 'docentes', preceptores: 'preceptores',
      afastamentos: 'afastamentos', locais: 'locais', eventos: 'eventos',
      estagios: 'estagios', remanejar: 'remanejar', historico: 'historico', encerrar: 'encerrar',
    }[nome] || 'painel';

    const viewFn = window.Views[viewName];
    const body = viewFn ? viewFn(arg) : '<div class="empty">Tela não encontrada.</div>';

    app.innerHTML =
      '<div class="shell">' +
        sidebar(nome) +
        '<div class="main">' + topbar() +
          '<main class="content" id="view-content">' + body + '</main></div>' +
      '</div>' +
      '<div class="drawer-backdrop" id="drawer-back"></div>';

    // monta comportamento da view
    const mountFn = window.Views[viewName + '_mount'];
    if (mountFn) mountFn(arg);

    wireShell();
  }

  function wireShell() {
    document.querySelectorAll('.nav-link[data-rota]').forEach((el) => {
      el.addEventListener('click', () => {
        const r = el.getAttribute('data-rota');
        if (r === '#/remanejar') { window.Views.remanejar_open && window.Views.remanejar_open(); return; }
        location.hash = r;
      });
    });
    const bt = document.getElementById('btn-tema');
    if (bt) bt.addEventListener('click', toggleTema);
    const bs = document.getElementById('btn-sair');
    if (bs) bs.addEventListener('click', () => {
      window.UI.confirmar('Sair da conta', 'Deseja encerrar a sessão e voltar à tela de login?', () => {
        Auth.sair();
        location.hash = '#/login';
      }, 'Sair');
    });
    const br = document.getElementById('btn-reset');
    if (br) br.addEventListener('click', () => {
      window.UI.confirmar('Resetar demonstração', 'Isso restaura todos os dados de demonstração ao estado inicial. Continuar?', () => {
        S.reset();
        try { localStorage.removeItem(S.KEY); } catch (e) {}
        S.reset();
        location.hash = '';
        window.UI.toast('Dados de demonstração restaurados', 'success');
        render();
      }, 'Resetar');
    });
    const menu = document.getElementById('btn-menu');
    const sb = document.getElementById('sidebar');
    const back = document.getElementById('drawer-back');
    if (menu && sb) {
      menu.addEventListener('click', () => { sb.classList.add('open'); back.classList.add('show'); });
      back.addEventListener('click', () => { sb.classList.remove('open'); back.classList.remove('show'); });
    }
  }

  // navegação helper global
  window.go = function (rota) { location.hash = rota; };
  window.rerender = render;

  window.addEventListener('hashchange', render);
  document.addEventListener('DOMContentLoaded', () => {
    if (!location.hash) location.hash = S.estadoInicial().rota;
    else render();
  });
  // caso DOMContentLoaded já tenha passado
  if (document.readyState !== 'loading') {
    if (!location.hash) location.hash = S.estadoInicial().rota; else render();
  }
})();
