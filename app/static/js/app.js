/* app.js — JS mínimo da FASE 5: tema, drawer mobile, toasts (HX-Trigger) e modal.
   Sem framework. HTMX cuida das interações de dados. */
(function () {
  'use strict';

  // ---- Tema (claro/escuro) -------------------------------------------------
  function toggleTema() {
    var cur = document.documentElement.getAttribute('data-theme');
    var novo = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', novo);
    try { localStorage.setItem('tema', novo); } catch (e) {}
  }

  // ---- Toast ---------------------------------------------------------------
  function toast(msg, tipo) {
    var cont = document.getElementById('toast-container');
    if (!cont) return;
    var el = document.createElement('div');
    el.className = 'toast toast-' + (tipo || 'info');
    el.textContent = msg;
    cont.appendChild(el);
    setTimeout(function () {
      el.style.opacity = '0'; el.style.transform = 'translateX(20px)';
      setTimeout(function () { el.remove(); }, 250);
    }, 3200);
  }

  // ---- Modal ---------------------------------------------------------------
  function fecharModal() {
    var root = document.getElementById('modal-root');
    if (root) root.innerHTML = '';
  }

  // ---- Ligações de UI (delegadas — sobrevivem a swaps do HTMX) -------------
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[id]') : null;
    var id = t ? t.id : null;
    if (id === 'btn-tema') { toggleTema(); return; }
    if (id === 'btn-menu') {
      var sb = document.getElementById('sidebar'); var bk = document.getElementById('drawer-back');
      if (sb) sb.classList.add('open'); if (bk) bk.classList.add('show');
      return;
    }
    if (id === 'drawer-back') {
      var sb2 = document.getElementById('sidebar'); var bk2 = document.getElementById('drawer-back');
      if (sb2) sb2.classList.remove('open'); if (bk2) bk2.classList.remove('show');
      return;
    }
    // fechar modal ao clicar no backdrop (exceto modais estáticos) ou num [data-close]
    if (e.target.classList && e.target.classList.contains('modal-backdrop')) {
      if (!e.target.hasAttribute('data-static')) fecharModal();
      return;
    }
    if (e.target.closest && e.target.closest('[data-close]')) { fecharModal(); return; }
    // login (stub): olho da senha (alterna visibilidade E o ícone) + avisos
    if (id === 'btn-eye') {
      var s = document.getElementById('login-senha');
      if (!s) return;
      var mostrar = s.type === 'password';
      s.type = mostrar ? 'text' : 'password';
      var eye = '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>';
      var eyeOff = '<path d="M9.9 4.24A9.1 9.1 0 0 1 12 4c6.5 0 10 8 10 8a18.5 18.5 0 0 1-2.16 3.19M6.6 6.6A18.5 18.5 0 0 0 2 12s3.5 7 10 7a9.1 9.1 0 0 0 5.4-1.6"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="M2 2l20 20"/>';
      t.innerHTML = '<span class="ic"><svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + (mostrar ? eyeOff : eye) + '</svg></span>';
      t.setAttribute('aria-label', mostrar ? 'Ocultar senha' : 'Mostrar senha');
      return;
    }
    if (id === 'btn-google') { toast('Login com Google ainda não disponível na demonstração', 'info'); return; }
    if (id === 'login-forgot') { e.preventDefault(); toast('Recuperação de senha ainda não disponível na demonstração', 'info'); return; }
  });

  document.addEventListener('keydown', function (e) {
    // Esc fecha o modal, exceto quando ele é estático (ex.: cadastro de aluno).
    if (e.key !== 'Escape') return;
    if (document.querySelector('.modal-backdrop[data-static]')) return;
    fecharModal();
  });

  // ---- Eventos vindos do servidor via HX-Trigger ---------------------------
  document.body.addEventListener('toast', function (e) {
    var d = e.detail || {}; toast(d.msg || d.value || '', d.tipo || 'info');
  });
  document.body.addEventListener('fechar-modal', fecharModal);

  // ---- Busca ao vivo no cliente (listas de alunos) -------------------------
  // Filtra as linhas [data-nome] dentro do [data-lista-wrap] que contém o input.
  window.filtrarLista = function (input) {
    var termo = (input.value || '').trim().toLowerCase();
    var box = input.closest('[data-lista-wrap]');
    if (!box) return;
    var linhas = box.querySelectorAll('[data-nome]');
    var visiveis = 0;
    linhas.forEach(function (el) {
      var hit = el.getAttribute('data-nome').indexOf(termo) !== -1;
      el.style.display = hit ? '' : 'none';
      if (hit) visiveis++;
    });
    var vazio = box.querySelector('[data-vazio-busca]');
    if (vazio) vazio.style.display = (visiveis === 0 && termo) ? '' : 'none';
  };

  // ---- Filtro de locais na Revisão (etapa 10): mostra só as caixas do local -----
  window.filtrarGruposLocal = function (sel) {
    var v = sel.value;
    var root = sel.closest ? document.querySelector('[data-grupos-root]') : null;
    if (!root) return;
    root.querySelectorAll('[data-filtro-local]').forEach(function (c) {
      c.style.display = (v === 'todos' || c.getAttribute('data-filtro-local') === v) ? '' : 'none';
    });
    root.querySelectorAll('[data-grupo-area]').forEach(function (a) {
      var cards = a.querySelectorAll('[data-filtro-local]');
      var visivel = Array.prototype.some.call(cards, function (c) { return c.style.display !== 'none'; });
      a.style.display = visivel ? '' : 'none';
    });
  };

  // ---- Montagem dos grupos: drag-and-drop (passo 9 do bootstrap) -----------
  // Delegado no document para sobreviver aos swaps do HTMX.
  var arrastando = null;
  document.addEventListener('dragstart', function (e) {
    var chip = e.target.closest && e.target.closest('[data-aluno]');
    if (!chip) return;
    arrastando = chip.getAttribute('data-aluno');
    try { e.dataTransfer.setData('text/plain', arrastando); e.dataTransfer.effectAllowed = 'move'; } catch (_) {}
    chip.style.opacity = '0.4';
  });
  document.addEventListener('dragend', function (e) {
    var chip = e.target.closest && e.target.closest('[data-aluno]');
    if (chip) chip.style.opacity = '';
  });
  document.addEventListener('dragover', function (e) {
    var dz = e.target.closest && e.target.closest('[data-grupo]');
    if (!dz) return;
    e.preventDefault(); e.dataTransfer.dropEffect = 'move';
    dz.style.outline = '2px solid var(--brand-400)';
  });
  document.addEventListener('dragleave', function (e) {
    var dz = e.target.closest && e.target.closest('[data-grupo]');
    if (dz) dz.style.outline = '';
  });
  document.addEventListener('drop', function (e) {
    var dz = e.target.closest && e.target.closest('[data-grupo]');
    if (!dz) return;
    e.preventDefault(); dz.style.outline = '';
    var aluno = arrastando || (e.dataTransfer && e.dataTransfer.getData('text/plain'));
    arrastando = null;
    if (!aluno || !window.htmx) return;
    window.htmx.ajax('POST', '/ui/montagem/colocar', {
      target: '#montagem-board', swap: 'innerHTML',
      values: { grupo_id: dz.getAttribute('data-grupo'), aluno_id: aluno },
    });
  });

  // ---- Toggles .segmented: o destaque azul acompanha o botão clicado ---------
  // Alguns toggles ficam no shell da página e o clique só troca o conteúdo (que
  // não contém o toggle), então a classe .active nunca era atualizada. Marcamos
  // aqui na hora (delegado, sobrevive aos swaps do HTMX).
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('.segmented button');
    if (!btn) return;
    var seg = btn.closest('.segmented');
    if (!seg) return;
    seg.querySelectorAll('button').forEach(function (b) { b.classList.remove('active'); });
    btn.classList.add('active');
  });
})();
