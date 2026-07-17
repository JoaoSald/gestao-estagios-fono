/* estagios.js — Escala geral com duas visões:
   • Por aluno  — tabela de alocações (clique abre o calendário do aluno).
   • Por campo  — calendário do cenário + painel do local (para o docente ver
                  quem terá no seu campo, quando e até quando).
   Calendário individual (modal, grade mensal) preservado.
   ============================================================================ */
(function () {
  'use strict';
  const { icon, esc, fmtData } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};
  const DIA = { segunda: 'Seg', terca: 'Ter', quarta: 'Qua', quinta: 'Qui', sexta: 'Sex', sabado: 'Sáb' };
  const DIA_LONGO = { segunda: 'Segunda', terca: 'Terça', quarta: 'Quarta', quinta: 'Quinta', sexta: 'Sexta', sabado: 'Sábado' };
  const TURNO = { manha: 'manhã', tarde: 'tarde', noite: 'noite' };
  // Paleta para diferenciar alunos dentro de um mesmo campo.
  const PALETA = ['#0ea5e9', '#f97316', '#8b5cf6', '#10b981', '#ec4899', '#f43f5e', '#eab308', '#14b8a6'];

  // Estado local da tela (persiste enquanto a sessão estiver aberta).
  let vista = 'aluno';   // 'aluno' | 'campo'
  let localSel = null;   // id do local selecionado na visão por campo
  let grupoAreaSel = 'todas';   // filtro por ÁREA na aba Grupos (§10.3)

  window.Views.estagios = function (arg) {
    if (arg === 'campo' || arg === 'aluno' || arg === 'grupos') vista = arg;   // deep-link da sub-visão
    const st = S.get();
    const c = S.cicloAtivo();
    S.atualizarConclusoes();
    // grupos são regenerados ao abrir a aba (reflete matrículas/alocações do momento,
    // inclusive matrícula feita no meio do ciclo → o aluno cai num grupo futuro).
    if (vista === 'grupos') S.gerarGrupos();
    const nAtivas = st.alocacoes.filter((a) => a.status === 'ativa').length;

    const seg = (v, ic, label) =>
      '<button data-vista="' + v + '" class="' + (vista === v ? 'active' : '') + '">' + icon(ic) + label + '</button>';

    const subs = {
      aluno: 'clique numa linha para o calendário do aluno',
      campo: 'calendário de cada cenário: quem vai, quando e até quando',
      grupos: 'grupos (ondas) por local: o atual e os próximos, com a previsão de quando entram',
    };
    return '<div class="page-head"><div class="row"><div><h1>Estágios</h1>' +
        '<p>Escala gerada · ' + nAtivas + ' alocações · ' + subs[vista] + '</p></div>' +
        (c.escala_desatualizada ? '<span class="badge b-risco"><span class="dt"></span>escala desatualizada</span>' :
          '<span class="badge b-concluida"><span class="dt"></span>escala atualizada</span>') + '</div></div>' +
      '<div class="flex flex-wrap mb" style="gap:.8rem">' +
        '<div class="segmented">' + seg('aluno', 'users', 'Por aluno') + seg('campo', 'building', 'Por campo') + seg('grupos', 'layers', 'Grupos') + '</div>' +
      '</div>' +
      (vista === 'campo' ? porCampo(st, c) : vista === 'grupos' ? porGrupos(st, c) : porAluno(st, c));
  };

  // ---- VISÃO POR GRUPOS (ondas por local), FILTRADA POR ÁREA — §10.3 ----
  function porGrupos(st, c) {
    const grupos = (st.grupos || []);
    const temMat = (st.matriculas || []).some((m) => m.status === 'em_andamento');
    if (!grupos.length && !temMat) return '<div class="tbl-wrap"><div class="empty"><div class="ei">' + icon('layers') + '</div>Nenhum grupo ainda — gere a escala primeiro.</div></div>';
    const nomeAluno = (id) => { const a = st.alunos.find((x) => x.id === id); return a ? a.nome : '?'; };
    // prioridade (ordenamento) do aluno, p/ exibir "Fulano · 3º" no roster
    const prioAluno = (id) => { const a = st.alunos.find((x) => x.id === id); return a && a.ordenamento ? a.ordenamento + 'º' : null; };
    const areaObj = (aid) => st.areas.find((a) => a.id === aid);
    const areaLabel = (a) => (a.area_mae ? ((areaObj(a.area_mae) || {}).nome || '') + ' - ' : '') + a.nome;
    const byLocal = {};
    grupos.forEach((g) => { (byLocal[g.local_id] = byLocal[g.local_id] || []).push(g); });
    // áreas que têm grupos, ordenadas pelo rótulo (mãe · sub)
    const byArea = {};
    grupos.forEach((g) => { (byArea[g.area_id] = byArea[g.area_id] || []).push(g); });
    // matriculados (em andamento) que NÃO estão em nenhum grupo → "aguardando · próximo ciclo".
    // Acontece quando não há vaga e nenhuma onda fecha até o fim do ciclo (corte de ciclo).
    // Não podem sumir da tela: entram numa faixa visível por área.
    const naArea = {};
    grupos.forEach((g) => g.membros.forEach((m) => { (naArea[g.area_id] = naArea[g.area_id] || {})[m.aluno_id] = true; }));
    const overflow = {};
    (st.matriculas || []).filter((m) => m.status === 'em_andamento').forEach((m) => {
      if (!(naArea[m.area_id] && naArea[m.area_id][m.aluno_id])) (overflow[m.area_id] = overflow[m.area_id] || []).push(m.aluno_id);
    });
    const areaIds = Array.from(new Set(Object.keys(byArea).concat(Object.keys(overflow))));
    const areasComGrupo = areaIds.map(areaObj).filter(Boolean).sort((a, b) => areaLabel(a).localeCompare(areaLabel(b)));

    // filtro por ÁREA
    if (grupoAreaSel !== 'todas' && !byArea[grupoAreaSel] && !overflow[grupoAreaSel]) grupoAreaSel = 'todas';
    const opts = '<option value="todas"' + (grupoAreaSel === 'todas' ? ' selected' : '') + '>Todas as áreas</option>' +
      areasComGrupo.map((a) => '<option value="' + a.id + '"' + (grupoAreaSel === a.id ? ' selected' : '') + '>' + esc(areaLabel(a)) + '</option>').join('');
    const filtro = '<div class="flex flex-wrap mb" style="gap:.6rem;align-items:center">' +
      '<label class="dim" style="font-size:.82rem">Área</label>' +
      '<select class="input" id="grupo-area-sel" style="max-width:360px">' + opts + '</select></div>';

    const areasMostrar = grupoAreaSel === 'todas' ? areasComGrupo : areasComGrupo.filter((a) => a.id === grupoAreaSel);

    // renderiza o card de um LOCAL (slot) com seus grupos (em andamento + na fila)
    function cardLocal(l, ar) {
      const ondas = byLocal[l.id].slice().sort((a, b) => a.onda - b.onda);
      const previstasMembros = ondas.filter((g) => g.status === 'previsto' && g.membros.length > 0);
      const podeSwap = previstasMembros.length >= 2;
      let out = '<div class="card" style="margin-bottom:.7rem"><div class="card-head">' +
        '<div><b>' + esc(l.campo) + '</b>' + (l.unidade ? ' <span class="dim">· ' + esc(l.unidade) + '</span>' : '') +
          '<div class="hint">' + window.UI.diasLabel(l) + ' · ' + window.UI.turnoLabel(l.turno) + ' · ' + l.hora_inicio + '–' + l.hora_fim + ' · cap. ' + l.capacidade + ' · ' + (l.numero_encontros || '?') + ' encontros</div></div></div>' +
        '<div class="card-body" style="padding-top:.5rem">';
      ondas.forEach((g, idx) => {
        const ehPrev = g.status === 'previsto';
        const badge = ehPrev
          ? '<span class="badge b-aguardando"><span class="dt"></span>na fila</span>'
          : '<span class="badge b-andamento"><span class="dt"></span>em andamento</span>';
        const temOutroGrupo = ehPrev && g.membros.length > 0 && previstasMembros.some((x) => x.onda !== g.onda);
        const btnGrupo = temOutroGrupo
          ? ' <button class="icon-btn btn-sm" data-sw-grupo="' + l.id + '" data-onda="' + g.onda + '" title="Trocar este grupo de posição com outro (swap de onda)">' + icon('shuffle') + '</button>'
          : '';
        const membros = g.membros.map((m) => {
          const av = m.aviso ? '<span class="badge b-risco" style="margin-left:.4rem" title="' + esc(m.aviso) + '">' + icon('alert') + ' ' + esc(m.aviso) + '</span>' : '';
          const acoes = (ehPrev && podeSwap)
            ? '<button class="icon-btn btn-sm" data-mv-aluno="' + m.aluno_id + '" data-mv-local="' + l.id + '" data-mv-onda="' + g.onda + '" title="Mover este aluno para outra leva (grupo)">' + icon('arrowRight') + '</button>'
            : '';
          const prio = prioAluno(m.aluno_id);
          // "montado" = tem pin/trava (posicionado à mão na Montagem ou no remanejo);
          // sem pin = preenchido pelo motor. Distingue decisão humana × automática.
          const fixado = (st.grupo_travas || []).some((t) => t.aluno_id === m.aluno_id && t.local_id === l.id && t.onda === g.onda);
          const selo = fixado
            ? ' <span class="badge b-iniciar" title="Posicionado à mão (Montagem dos grupos ou remanejo) — não foi o motor">' + icon('user') + ' montado</span>'
            : ' <span class="dim" style="font-size:.72rem" title="Preenchido automaticamente pelo motor">auto</span>';
          const ch = S.chSemanaAlunoGrupos(m.aluno_id);
          const chTxt = ch > 0 ? ' <span class="dim" style="' + (ch > 30 ? 'color:var(--st-risco);font-weight:700' : '') + '" title="Carga horária semanal de pico do aluno (teto 30h)">· ' + (Math.round(ch * 10) / 10) + 'h/30h</span>' : '';
          return '<div class="roster-item"><span class="roster-dot" style="background:' + ar.cor + '"></span>' +
            '<div style="flex:1;min-width:0"><div class="rn">' + esc(nomeAluno(m.aluno_id)) + (prio ? ' <span class="dim">· ' + prio + '</span>' : '') + selo + chTxt + av + '</div></div>' +
            (acoes ? '<div class="row-actions">' + acoes + '</div>' : '') + '</div>';
        }).join('') || '<div class="dim">—</div>';
        const cheia = g.membros.length >= l.capacidade;
        const ocupBadge = '<span style="font-size:.78rem;font-weight:700;margin-left:.15rem;color:' +
          (cheia ? 'var(--st-concluida)' : 'var(--st-aguardando)') +
          '" title="Ocupação da caixa — ' + (cheia ? 'cheia' : 'com vaga') + '">' + g.membros.length + '/' + l.capacidade + '</span>';
        out += '<div style="margin-bottom:.5rem">' +
          '<div class="flex between" style="align-items:center;margin-bottom:.35rem">' +
            '<div><b>Grupo ' + g.onda + '</b> ' + ocupBadge + ' ' + badge + btnGrupo + '</div>' +
            '<span class="dim" style="font-size:.8rem">' + fmtData(g.data_inicio) + ' → ' + fmtData(g.data_fim) + '</span>' +
          '</div>' + membros + '</div>';
        if (l.passagem_grupo && idx < ondas.length - 1) {
          out += '<div class="hint" style="display:flex;align-items:center;gap:.35rem;margin:.1rem 0 .7rem;color:var(--brand-400);font-weight:600">' +
            icon('shuffle') + ' passagem de grupo · ' + fmtData(g.data_fim) + ' (último do Grupo ' + g.onda + ' = 1º do Grupo ' + (g.onda + 1) + ')</div>';
        }
      });
      return out + '</div></div>';
    }

    let out = filtro + '<p class="dim" style="margin:0 0 .8rem">Cada <b>slot (campo+dia)</b> tem um grupo <b>em andamento</b> e, se há mais alunos que a capacidade, grupos <b>na fila</b> (próximas levas). <b>Trocar aluno</b> ou <b>trocar grupos</b> só reordena o planejado — nada trava; cada grupo se concretiza no 1º dia de encontros. Selo <b>montado</b> = você posicionou à mão (Montagem/remanejo); <b>auto</b> = o motor preencheu.</p>';
    areasMostrar.forEach((ar) => {
      const gs = byArea[ar.id] || [];
      const nAnd = gs.filter((g) => g.status === 'em_andamento').length;
      const naFila = gs.filter((g) => g.status === 'previsto' && g.membros.length > 0).length;
      const nAlunos = gs.reduce((s, g) => s + g.membros.length, 0);
      const espera = overflow[ar.id] || [];
      const locais = st.locais.filter((l) => l.area_id === ar.id && byLocal[l.id]).sort((a, b) => a.campo.localeCompare(b.campo));
      out += '<div style="margin:.9rem 0 .5rem"><span class="area-pill" style="background:' + ar.cor + '22;color:' + ar.cor + '"><span class="dt" style="background:' + ar.cor + '"></span>' + esc(areaLabel(ar)) + '</span>' +
        ' <span class="dim" style="font-size:.82rem">· ' + locais.length + ' local(is) · ' + nAnd + ' grupo(s) em andamento' + (naFila ? ' · <b>' + naFila + ' grupo(s) na fila</b>' : '') + ' · ' + nAlunos + ' aluno(s)' + (espera.length ? ' · <b>' + espera.length + ' aguardando</b>' : '') + '</span></div>';
      locais.forEach((l) => { out += cardLocal(l, ar); });
      if (espera.length) {
        const roster = espera.map((aid) => {
          const prio = prioAluno(aid);
          return '<div class="roster-item"><span class="roster-dot" style="background:' + ar.cor + '"></span>' +
            '<div style="flex:1;min-width:0"><div class="rn">' + esc(nomeAluno(aid)) + (prio ? ' <span class="dim">· ' + prio + '</span>' : '') + '</div></div></div>';
        }).join('');
        out += '<div class="card" style="margin-bottom:.7rem;border-style:dashed">' +
          '<div class="card-head"><div><b>Aguardando vaga</b> <span class="badge b-aguardando"><span class="dt"></span>próximo ciclo</span>' +
          '<div class="hint">Sem vaga com onda que feche até o fim do ciclo — entram ao liberar vaga ou no próximo ciclo.</div></div></div>' +
          '<div class="card-body" style="padding-top:.5rem">' + roster + '</div></div>';
      }
    });
    return out;
  }

  // Reuso da visão de Grupos (mesma tela) no bootstrap, com swap habilitado —
  // no bootstrap ainda não começou, então dá pra substituir pessoas e trocar grupos.
  window.Views.gruposRender = function () { return porGrupos(S.get(), S.cicloAtivo()); };
  window.Views.gruposMount = function () {
    const gsel = document.getElementById('grupo-area-sel');
    if (gsel) gsel.addEventListener('change', () => { grupoAreaSel = gsel.value; window.rerender(); });
    document.querySelectorAll('[data-mv-aluno]').forEach((b) => b.addEventListener('click', () => {
      pickAlunoMove(b.getAttribute('data-mv-local'), b.getAttribute('data-mv-aluno'), +b.getAttribute('data-mv-onda'));
    }));
    document.querySelectorAll('[data-sw-grupo]').forEach((b) => b.addEventListener('click', () => {
      const localId = b.getAttribute('data-sw-grupo'); const onda = +b.getAttribute('data-onda');
      pickGrupoSwap(localId, onda, (destino) => { S.trocarGruposInteiros(localId, onda, destino); window.UI.toast('Grupo ' + onda + ' ⇄ Grupo ' + destino + ' — ordem planejada atualizada', 'success'); window.rerender(); });
    }));
  };

  // Modal: MOVER um aluno para outra leva (grupo). §10.3 — "bloqueia tudo e sugere":
  // o movimento só acontece se a onda destino tem vaga, sem conflito de dia/turno e
  // sem estourar 30h; senão mostra os motivos e a onda mais cedo viável.
  function pickAlunoMove(localId, alunoId, ondaAtual) {
    const st = S.get();
    const l = st.locais.find((x) => x.id === localId) || {};
    const nome = (st.alunos.find((a) => a.id === alunoId) || {}).nome || 'aluno';
    // destinos: ondas previstas do local, exceto a atual do aluno
    const destinos = (st.grupos || []).filter((g) => g.local_id === localId && g.status === 'previsto' && g.onda !== ondaAtual)
      .sort((a, b) => a.onda - b.onda);
    const btnOnda = (g) => {
      const cheio = g.membros.length >= l.capacidade;
      return '<button class="btn btn-secondary" data-onda="' + g.onda + '" style="margin:.2rem">Grupo ' + g.onda +
        ' <span class="dim">· ' + g.membros.length + '/' + l.capacidade + (cheio ? ' (cheio)' : '') + ' · ' + fmtData(g.data_inicio) + '</span></button>';
    };
    const listaHtml =
      '<p class="muted mb">Escolha a <b>leva</b> (grupo) para onde mover <b>' + esc(nome) + '</b>. O sistema só move se couber sem conflito — senão explica o motivo e sugere a leva mais cedo possível.</p>' +
      '<div class="flex flex-wrap">' + (destinos.map(btnOnda).join('') || '<span class="dim">Não há outra leva prevista neste local.</span>') + '</div>';
    window.UI.modal({
      titulo: 'Mover ' + nome + ' para…',
      corpo: '<div id="mv-corpo">' + listaHtml + '</div>',
      rodape: '<button class="btn btn-secondary" data-close>Fechar</button>',
      onMount(el, close) {
        const corpo = el.querySelector('#mv-corpo');
        const renderLista = () => {
          corpo.innerHTML = listaHtml;
          corpo.querySelectorAll('[data-onda]').forEach((b) => b.addEventListener('click', () => tentar(+b.getAttribute('data-onda'))));
        };
        const tentar = (onda) => {
          const r = S.moverAlunoGrupo(alunoId, localId, onda);
          if (r.ok) { close(); window.UI.toast('Aluno movido para o Grupo ' + onda + ' — ordem planejada atualizada', 'success'); window.rerender(); return; }
          const sug = r.sugestaoOnda;
          const sugBtn = (sug && sug !== onda)
            ? '<button class="btn btn-primary btn-sm" data-sug="' + sug + '" style="margin-top:.7rem">' + icon('arrowRight') + ' Mover para o Grupo ' + sug + ' (cabe)</button>'
            : (sug ? '<p class="hint" style="margin-top:.7rem">O Grupo ' + sug + ' já é a leva mais cedo viável para este aluno.</p>'
                   : '<p class="hint" style="margin-top:.7rem">Não há outra leva viável neste local — o aluno segue onde está.</p>');
          corpo.innerHTML =
            '<div style="border:1px solid var(--st-risco);background:color-mix(in srgb,var(--st-risco) 10%,transparent);border-radius:.6rem;padding:.7rem .85rem;margin-bottom:.7rem;color:var(--text)">' +
            '<div style="color:var(--st-risco);font-weight:700;display:flex;align-items:center;gap:.4rem">' + icon('alert') + ' Não dá para mover para o Grupo ' + onda + '</div>' +
            '<ul style="margin:.45rem 0 0 1.1rem">' + r.motivos.map((mo) => '<li>' + esc(mo) + '</li>').join('') + '</ul>' + sugBtn + '</div>' +
            '<button class="btn btn-secondary btn-sm" data-voltar>← Escolher outra leva</button>';
          const bs = corpo.querySelector('[data-sug]'); if (bs) bs.addEventListener('click', () => tentar(+bs.getAttribute('data-sug')));
          const bv = corpo.querySelector('[data-voltar]'); if (bv) bv.addEventListener('click', renderLista);
        };
        renderLista();
      },
    });
  }
  // Modal: escolher o GRUPO (onda prevista) para TROCAR DE POSIÇÃO. §10.3
  function pickGrupoSwap(localId, ondaX, cb) {
    const st = S.get();
    const ondas = (st.grupos || []).filter((g) => g.local_id === localId && g.status === 'previsto' && g.membros.length > 0 && g.onda !== ondaX)
      .sort((a, b) => a.onda - b.onda);
    const botoes = ondas.map((g) => '<button class="btn btn-secondary" data-onda="' + g.onda + '" style="margin:.2rem">Grupo ' + g.onda + ' <span class="dim">· ' + g.membros.length + ' aluno(s)</span></button>').join('') ||
      '<span class="dim">Nenhum outro grupo previsto para trocar.</span>';
    window.UI.modal({
      titulo: 'Trocar o Grupo ' + ondaX + ' com…',
      corpo: '<p class="muted mb">Escolha o grupo para <b>trocar de posição</b> com o <b>Grupo ' + ondaX + '</b> (os dois trocam de onda; cada um mantém seus membros). É só a ordem planejada — dá pra refazer quando quiser (nada trava).</p><div class="flex flex-wrap">' + botoes + '</div>',
      rodape: '<button class="btn btn-secondary" data-close>Cancelar</button>',
      onMount(el, close) {
        el.querySelectorAll('[data-onda]').forEach((b) => b.addEventListener('click', () => { close(); cb(+b.getAttribute('data-onda')); }));
      },
    });
  }

  // ---- VISÃO POR ALUNO (tabela) -------------------------------------------
  function porAluno(st, c) {
    const rows = st.alocacoes.filter((a) => a.status !== 'cancelada').map((a) => {
      const al = st.alunos.find((x) => x.id === a.aluno_id);
      const lc = st.locais.find((x) => x.id === a.local_id);
      if (!al || !lc) return '';
      const ar = st.areas.find((x) => x.id === lc.area_id);
      const doc = st.docentes.find((x) => x.id === lc.docente_id);
      const mat = st.matriculas.find((m) => m.id === a.matricula_id);
      const total = st.sessoes.filter((s) => s.alocacao_id === a.id).length;
      const cumpr = st.sessoes.filter((s) => s.alocacao_id === a.id && s.status === 'cumprida').length;
      const risco = a.data_fim_prevista > c.data_fim;
      return '<tr data-open="' + al.id + '" style="cursor:pointer">' +
        '<td><b>' + esc(al.nome) + '</b></td>' +
        '<td><span class="area-pill" style="background:' + ar.cor + '22;color:' + ar.cor + '"><span class="dt" style="background:' + ar.cor + '"></span>' + esc(ar.nome) + '</span></td>' +
        '<td>' + esc(lc.campo) + '</td>' +
        '<td>' + esc(doc ? doc.nome : '') + '</td>' +
        '<td>' + window.UI.diasLabel(lc) + ' · ' + lc.hora_inicio + '–' + lc.hora_fim + '</td>' +
        '<td>' + cumpr + '/' + total + ' sessões</td>' +
        '<td>' + (mat && mat.status === 'concluida' ? '<span class="badge b-concluida"><span class="dt"></span>concluída</span>' :
          risco ? '<span class="badge b-risco"><span class="dt"></span>' + fmtData(a.data_fim_prevista) + '</span>' :
          '<span class="badge b-andamento"><span class="dt"></span>' + fmtData(a.data_fim_prevista) + '</span>') + '</td></tr>';
    }).join('');

    return '<div class="flex flex-wrap mb" style="gap:.8rem">' + window.UI.searchBox('busca-estagios', 'Buscar por aluno, área, campo ou docente…') + '</div>' +
      '<div class="tbl-wrap scroll-x scroll-y"><table class="tbl"><thead><tr><th>Aluno</th><th>Área</th><th>Campo</th><th>Docente</th><th>Horário</th><th>Sessões</th><th>Conclusão prevista</th></tr></thead><tbody>' +
      (rows || '<tr data-nofilter><td colspan="7"><div class="empty">Nenhuma alocação gerada.</div></td></tr>') +
      '<tr data-nofilter class="sem-resultado" style="display:none"><td colspan="7"><div class="empty">Nenhum resultado.</div></td></tr></tbody></table></div>';
  }

  // ---- VISÃO POR CAMPO (calendário + painel do cenário) -------------------
  function locaisComEstagio(st) {
    return st.locais.filter((l) => st.alocacoes.some((a) => a.local_id === l.id && a.status !== 'cancelada'));
  }

  function porCampo(st, c) {
    const locais = locaisComEstagio(st);
    if (!locais.length) return '<div class="tbl-wrap"><div class="empty"><div class="ei">' + icon('grid') + '</div>Nenhuma alocação gerada ainda.</div></div>';
    if (!localSel || !locais.some((l) => l.id === localSel)) localSel = locais[0].id;

    const local = st.locais.find((l) => l.id === localSel);
    const ar = st.areas.find((x) => x.id === local.area_id);
    const doc = st.docentes.find((x) => x.id === local.docente_id);
    const prec = S.preceptorDoLocal(local);
    const alocs = st.alocacoes.filter((a) => a.local_id === local.id && a.status !== 'cancelada');

    // roster: aluno + cor + progresso
    const roster = alocs.map((a, i) => {
      const al = st.alunos.find((x) => x.id === a.aluno_id);
      const total = st.sessoes.filter((s) => s.alocacao_id === a.id).length;
      const cumpr = st.sessoes.filter((s) => s.alocacao_id === a.id && s.status === 'cumprida').length;
      const pct = total ? Math.round((cumpr / total) * 100) : 0;
      return { aloc: a, aluno: al, cor: corGrupo(1), total, cumpr, pct, fim: a.data_fim_prevista };
    }).filter((r) => r.aluno);

    const options = locais.map((l) => {
      const a2 = st.areas.find((x) => x.id === l.area_id);
      const n = st.alocacoes.filter((a) => a.local_id === l.id && a.status !== 'cancelada').length;
      return '<option value="' + l.id + '"' + (l.id === localSel ? ' selected' : '') + '>' +
        esc((a2 ? a2.nome : '') + ' — ' + l.campo) + ' (' + n + '/' + l.capacidade + ')</option>';
    }).join('');

    const iniGeral = alocs.reduce((m, a) => (a.data_inicio < m ? a.data_inicio : m), alocs[0].data_inicio);
    const fimGeral = alocs.reduce((m, a) => (a.data_fim_prevista > m ? a.data_fim_prevista : m), alocs[0].data_fim_prevista);
    const vagasLivres = local.capacidade - alocs.length;

    const li = (ic, k, v) => '<div class="li">' + icon(ic) + '<div><span class="k">' + k + ':</span> ' + v + '</div></div>';

    const rosterHtml = roster.map((r) =>
      '<div class="roster-item"><span class="roster-dot" style="background:' + r.cor + '"></span>' +
        '<div style="min-width:0;flex:1"><div class="rn">' + esc(r.aluno.nome) + (r.aloc.travada ? ' ' + icon('lock') : '') + '</div>' +
          '<div class="rm">' + r.cumpr + '/' + r.total + ' sessões · ' + r.pct + '% · até ' + fmtData(r.fim) + '</div></div>' +
        (r.fim > c.data_fim ? '<span class="badge b-risco"><span class="dt"></span>risco</span>' : '') +
        '<div class="row-actions">' +
          '<button class="icon-btn btn-sm" data-mover="' + r.aloc.id + '" title="Mover para outro local da área">' + icon('shuffle') + '</button>' +
          '<button class="icon-btn btn-sm" data-remover="' + r.aloc.id + '" title="Remover do local (libera a vaga)">' + icon('trash') + '</button>' +
        '</div>' +
      '</div>').join('');

    return '<div class="flex flex-wrap mb" style="gap:.6rem">' +
        '<label class="dim" style="font-size:.8rem;font-weight:600">Cenário</label>' +
        '<select class="select" id="campo-sel" style="width:auto;max-width:34rem">' + options + '</select>' +
      '</div>' +
      '<div class="campo-layout">' +
        '<div class="cal-host" id="campo-cal"></div>' +
        '<div class="card"><div class="card-head" style="border-left:4px solid ' + ar.cor + '">' +
            '<div><span class="area-pill" style="background:' + ar.cor + '22;color:' + ar.cor + '"><span class="dt" style="background:' + ar.cor + '"></span>' + esc(ar.nome) + '</span>' +
            '<div style="font-weight:700;font-size:1rem;margin-top:.4rem">' + esc(local.campo) + '</div></div></div>' +
          '<div class="card-body campo-info">' +
            li('teacher', 'Docente', esc(doc ? doc.nome : '—')) +
            li('user', 'Preceptor', prec ? (esc(prec.nome) + (prec.tipo === 'docente' ? ' (docente)' : '')) : '<span class="dim">— (só o docente)</span>') +
            li('clock', 'Horário', window.UI.diasLabel(local, true) + ' · ' + window.UI.turnoLabel(local.turno) + ' · ' + local.hora_inicio + '–' + local.hora_fim) +
            li('calendar', 'Período', fmtData(iniGeral) + ' → ' + fmtData(fimGeral)) +
            li('shuffle', 'Passagem de grupo', local.passagem_grupo
              ? '<b>sim</b> <span class="dim">· dia ' + fmtData(fimGeral) + ' o próximo grupo entra (último encontro deste)</span>'
              : '<span class="dim">não</span>') +
            li('layers', 'Vagas', '<b>' + alocs.length + '/' + local.capacidade + '</b> ' +
              (vagasLivres > 0 ? '<span class="dim">(' + vagasLivres + ' livre' + (vagasLivres > 1 ? 's' : '') + ')</span>' : '<span class="dim">(lotado)</span>')) +
          '</div>' +
          '<div class="card-head"><div class="flex between" style="width:100%;align-items:center;gap:.5rem">' +
            '<div class="dim" style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em">Alunos no cenário</div>' +
            '<div class="row-actions">' +
              (vagasLivres > 0 ? '<button class="btn btn-secondary btn-sm" data-add-aloc="' + local.id + '">' + icon('plus') + ' Adicionar</button>' : '') +
              (roster.length ? '<button class="btn btn-secondary btn-sm" data-concluir-grupo="' + local.id + '">' + icon('check') + ' Concluir grupo</button>' : '') +
            '</div>' +
          '</div></div>' +
          '<div class="card-body" style="padding-top:.4rem">' + (rosterHtml || '<div class="dim">Nenhum aluno.</div>') + '</div>' +
        '</div>' +
      '</div>';
  }

  // ---- Mount ---------------------------------------------------------------
  window.Views.estagios_mount = function () {
    document.querySelectorAll('.segmented [data-vista]').forEach((b) => b.addEventListener('click', () => {
      vista = b.getAttribute('data-vista'); window.rerender();
    }));

    if (vista === 'aluno') {
      document.querySelectorAll('[data-open]').forEach((r) => r.addEventListener('click', () => window.Views.calendarioAluno(r.getAttribute('data-open'))));
      const tb = document.querySelector('.tbl-wrap tbody');
      window.UI.wireSearch(document.getElementById('busca-estagios'), tb, (n, q) => {
        const vazio = tb && tb.querySelector('.sem-resultado'); if (vazio) vazio.style.display = (n === 0 && q) ? '' : 'none';
      });
      return;
    }

    if (vista === 'grupos') { window.Views.gruposMount(); return; }

    // visão por campo
    const sel = document.getElementById('campo-sel');
    if (sel) sel.addEventListener('change', () => { localSel = sel.value; window.rerender(); });
    const host = document.getElementById('campo-cal');
    if (host) montarCalCampo(host);

    // ações manuais (ajuste da escala)
    const bAdd = document.querySelector('[data-add-aloc]');
    if (bAdd) bAdd.addEventListener('click', () => window.Forms.adicionarAloc(bAdd.getAttribute('data-add-aloc'), () => window.rerender()));
    const bCon = document.querySelector('[data-concluir-grupo]');
    if (bCon) bCon.addEventListener('click', () => {
      const lid = bCon.getAttribute('data-concluir-grupo');
      const lc = S.get().locais.find((l) => l.id === lid);
      window.UI.confirmar('Concluir grupo', 'Concluir todos os alunos ativos de <b>' + esc(lc ? lc.campo : '') + '</b>? As áreas deles serão dadas como concluídas e as vagas liberadas para a próxima turma.', () => {
        S.concluirGrupoLocal(lid);
        window.UI.toast('Grupo concluído — vagas liberadas', 'success');
        window.rerender();
      }, 'Concluir');
    });
    document.querySelectorAll('[data-mover]').forEach((b) => b.addEventListener('click', () => window.Forms.moverAloc(b.getAttribute('data-mover'), () => window.rerender())));
    document.querySelectorAll('[data-remover]').forEach((b) => b.addEventListener('click', () => {
      const aid = b.getAttribute('data-remover');
      const st = S.get(); const a = st.alocacoes.find((x) => x.id === aid);
      const al = a && st.alunos.find((x) => x.id === a.aluno_id);
      window.UI.confirmar('Remover do local', 'Remover <b>' + esc(al ? al.nome : 'o aluno') + '</b> deste local? A vaga é liberada e o aluno volta para a fila daquela área.', () => {
        S.removerAlocacao(aid);
        window.UI.toast('Aluno removido — vaga liberada', 'success');
        window.rerender();
      }, 'Remover');
    }));
  };

  // Constrói as sessões (por dia) do local selecionado, agrupando alunos.
  // cor macro por GRUPO (onda) — 1 cor por onda, não por aluno
  function corGrupo(onda) { return PALETA[(onda - 1) % PALETA.length]; }

  function montarCalCampo(host) {
    const st = S.get();
    const c = S.cicloAtivo();
    const local = st.locais.find((l) => l.id === localSel);
    // grupos (ondas) do local, incluindo os previstos — para colorir e marcar início/fim
    S.gerarGrupos();
    const grupos = S.get().grupos.filter((g) => g.local_id === local.id).sort((a, b) => a.onda - b.onda);
    const ondaDoAluno = {};
    grupos.forEach((g) => g.membros.forEach((m) => { ondaDoAluno[m.aluno_id] = g.onda; }));

    const alocs = st.alocacoes.filter((a) => a.local_id === local.id && a.status !== 'cancelada');
    // sessões (onda em andamento) agregadas por dia, coloridas pela cor do GRUPO
    const porDia = {};
    alocs.forEach((a) => {
      const onda = ondaDoAluno[a.aluno_id] || 1;
      st.sessoes.filter((s) => s.alocacao_id === a.id && s.status !== 'remanejada' && s.status !== 'cancelada').forEach((s) => {
        const rec = (porDia[s.data] = porDia[s.data] || {});
        const g = (rec[onda] = rec[onda] || { onda, cor: corGrupo(onda), n: 0, cumprida: true });
        g.n++; if (s.status !== 'cumprida') g.cumprida = false;
      });
    });
    // grupos PREVISTOS: projeta os encontros semanais na janela do grupo, para o grupo
    // aparecer em todos os seus dias (início→fim) como o grupo em andamento faz.
    grupos.filter((g) => g.status === 'previsto').forEach((g) => {
      let dia = g.data_inicio, guard = 0;
      while (dia <= g.data_fim && guard < 400) {
        const rec = (porDia[dia] = porDia[dia] || {});
        rec[g.onda] = rec[g.onda] || { onda: g.onda, cor: corGrupo(g.onda), n: g.membros.length, cumprida: false };
        dia = S.addDays(dia, 7); guard++;
      }
    });
    // marcos de início e fim de CADA grupo
    const marcos = {};
    grupos.forEach((g) => {
      (marcos[g.data_inicio] = marcos[g.data_inicio] || []).push({ onda: g.onda, tipo: 'início', cor: corGrupo(g.onda) });
      (marcos[g.data_fim] = marcos[g.data_fim] || []).push({ onda: g.onda, tipo: 'fim', cor: corGrupo(g.onda) });
    });
    const legenda = grupos.map((g) => ({
      onda: g.onda, cor: corGrupo(g.onda), n: g.membros.length,
      ini: g.data_inicio, fim: g.data_fim, previsto: g.status === 'previsto',
    }));

    // navegação cobre do 1º início ao último fim (grupos previstos passam do fim do ciclo)
    let rangeMin = c.data_inicio.slice(0, 7), rangeMax = c.data_fim.slice(0, 7);
    grupos.forEach((g) => {
      if (g.data_inicio.slice(0, 7) < rangeMin) rangeMin = g.data_inicio.slice(0, 7);
      if (g.data_fim.slice(0, 7) > rangeMax) rangeMax = g.data_fim.slice(0, 7);
    });
    let mesRef = (grupos.length ? grupos[0].data_inicio : c.data_inicio).slice(0, 7);
    if (mesRef < rangeMin) mesRef = rangeMin;
    const handover = (local.passagem_grupo && alocs.length)
      ? alocs.reduce((m, a) => (a.data_fim_prevista > m ? a.data_fim_prevista : m), alocs[0].data_fim_prevista) : null;
    renderCalCampo(host, mesRef, porDia, marcos, legenda, rangeMin, rangeMax, handover);
  }

  function renderCalCampo(host, mesRef, porDia, marcos, legenda, rangeMin, rangeMax, handover) {
    const [y, mo] = mesRef.split('-').map(Number);
    const startDow = new Date(y, mo - 1, 1).getDay();
    const daysInMonth = new Date(y, mo, 0).getDate();
    const hoje = S.hoje();
    const dows = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

    let cells = '';
    for (let i = 0; i < startDow; i++) cells += '<div class="cal-cell out"></div>';
    for (let d = 1; d <= daysInMonth; d++) {
      const dia = y + '-' + String(mo).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      const rec = porDia[dia] || {};
      let inner = '<div class="dn">' + d + '</div>';
      // encontros do dia, agrupados por onda (1 cor por grupo)
      Object.keys(rec).map((k) => rec[k]).sort((a, b) => a.onda - b.onda).forEach((g) => {
        inner += '<span class="cal-sess" style="background:' + g.cor + (g.cumprida ? '' : ';opacity:.72') + '" title="Grupo ' + g.onda + ' · ' + g.n + ' aluno(s)">G' + g.onda + ' ·' + g.n + '</span>';
      });
      // marcos de início/fim de grupo
      (marcos[dia] || []).forEach((mk) => {
        inner += '<span class="cal-ev" style="background:' + mk.cor + '22;color:' + mk.cor + ';border:1px solid ' + mk.cor + '66" title="Grupo ' + mk.onda + ' ' + mk.tipo + ' em ' + fmtData(dia) + '">G' + mk.onda + ' ' + mk.tipo + '</span>';
      });
      if (dia === handover) inner += '<span class="cal-ev" title="Passagem de grupo: entra o próximo grupo">🔁 passagem</span>';
      cells += '<div class="cal-cell ' + (dia === hoje ? 'today' : '') + '">' + inner + '</div>';
    }

    const podePrev = mesRef > rangeMin;
    const podeNext = mesRef < rangeMax;
    host.innerHTML = '<div class="cal"><div class="cal-head">' +
        '<button class="icon-btn" id="cc-prev" ' + (podePrev ? '' : 'disabled') + '>' + icon('chevronLeft') + '</button>' +
        '<h3>' + window.UI.MESES_LONGO[mo - 1] + ' ' + y + '</h3>' +
        '<button class="icon-btn" id="cc-next" ' + (podeNext ? '' : 'disabled') + '>' + icon('chevronRight') + '</button></div>' +
        '<div class="cal-grid">' + dows.map((d) => '<div class="cal-dow">' + d + '</div>').join('') + cells + '</div></div>' +
      '<div class="cal-legend mt-sm">' + legenda.map((l) =>
        '<span class="leg-item"><span class="leg-dot" style="background:' + l.cor + '"></span>Grupo ' + l.onda +
          ' <span class="dim">· ' + fmtData(l.ini) + '→' + fmtData(l.fim) + ' · ' + l.n + ' aluno(s)' + (l.previsto ? ' · previsto' : ' · em andamento') + '</span></span>').join('') + '</div>';

    const prev = host.querySelector('#cc-prev'); const next = host.querySelector('#cc-next');
    if (prev) prev.addEventListener('click', () => { const d = new Date(y, mo - 2, 1); renderCalCampo(host, d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'), porDia, marcos, legenda, rangeMin, rangeMax, handover); });
    if (next) next.addEventListener('click', () => { const d = new Date(y, mo, 1); renderCalCampo(host, d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'), porDia, marcos, legenda, rangeMin, rangeMax, handover); });
  }

  // ---- Encontros do aluno (modal, SOMENTE LEITURA): resumo + calendário ----
  window.Views.calendarioAluno = function (alunoId) {
    const st = S.get();
    const al = st.alunos.find((a) => a.id === alunoId);
    const c = S.cicloAtivo();
    let mesRef = S.hoje().slice(0, 7);
    if (mesRef < c.data_inicio.slice(0, 7)) mesRef = c.data_inicio.slice(0, 7);
    const estado = { mes: mesRef };

    window.UI.modal({
      titulo: 'Encontros — ' + al.nome, wide: true,
      corpo: '<div id="enc-host"></div>',
      rodape: '<button class="btn btn-primary" data-close>Fechar</button>',
      onMount(el) { renderEncontros(el.querySelector('#enc-host'), alunoId, estado); },
    });
  };

  function renderEncontros(host, alunoId, estado) {
    const st = S.get();
    const c = S.cicloAtivo();
    S.atualizarConclusoes();
    const alocs = st.alocacoes.filter((a) => a.aluno_id === alunoId && a.status !== 'cancelada');
    const sessoes = [];
    const resumo = alocs.map((a) => {
      const lc = st.locais.find((l) => l.id === a.local_id);
      const ar = lc ? st.areas.find((x) => x.id === lc.area_id) : null;
      const mat = st.matriculas.find((m) => m.id === a.matricula_id);
      const enc = mat ? S.encontrosMatricula(mat) : { total: 0, feitos: 0 };
      const pct = enc.total ? Math.round((enc.feitos / enc.total) * 100) : 0;
      const concl = mat && mat.status === 'concluida';
      st.sessoes.filter((s) => s.alocacao_id === a.id && s.status !== 'remanejada' && s.status !== 'cancelada').forEach((s) => {
        sessoes.push({ data: s.data, cor: ar ? ar.cor : '#64748b', nome: ar ? ar.nome : '', hora: s.hora_inicio, status: s.status });
      });
      return { ar, enc, pct, concl, cor: ar ? ar.cor : '#64748b' };
    });

    const sumHtml = resumo.length ? resumo.map((r) =>
      '<div style="margin-bottom:.7rem"><div class="flex between" style="font-size:.82rem;margin-bottom:.25rem">' +
        '<b>' + esc(r.ar ? r.ar.nome : '—') + '</b>' +
        '<span class="dim">' + r.enc.feitos + '/' + r.enc.total + ' encontros · ' + r.pct + '%' +
          (r.concl ? ' · concluída' : '') + '</span></div>' +
        window.UI.bar(r.pct, r.cor) + '</div>').join('') : '<div class="empty">Sem alocações — gere a escala primeiro.</div>';

    host.innerHTML = '<div class="stack" style="gap:1rem">' +
      '<div class="card"><div class="card-body" style="padding:1rem 1.1rem">' + sumHtml + '</div></div>' +
      '<div id="enc-cal"></div>' +
      '<p class="hint">Visualização. Para registrar falta ou conceder reforço, use <b>Cadastros → Alunos → Encontros</b>.</p>' +
    '</div>';

    renderCalEnc(host.querySelector('#enc-cal'), estado, sessoes, c);
  }

  function renderCalEnc(host, estado, sessoes, ciclo) {
    const [y, mo] = estado.mes.split('-').map(Number);
    const startDow = new Date(y, mo - 1, 1).getDay();
    const daysInMonth = new Date(y, mo, 0).getDate();
    const hoje = S.hoje();
    const dows = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

    let cells = '';
    for (let i = 0; i < startDow; i++) cells += '<div class="cal-cell out"></div>';
    for (let d = 1; d <= daysInMonth; d++) {
      const dia = y + '-' + String(mo).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      const doDia = sessoes.filter((s) => s.data === dia);
      const evs = S.get().eventos.filter((e) => e.bloqueia_estagio && dia >= e.data_inicio && dia <= e.data_fim);
      let inner = '<div class="dn">' + d + '</div>';
      doDia.slice(0, 3).forEach((s) => {
        const op = s.status === 'cumprida' ? '' : ';opacity:.72';
        inner += '<span class="cal-sess" style="background:' + s.cor + op + '" title="' + esc(s.nome) + ' ' + s.hora + '">' + esc(s.nome) + '</span>';
      });
      evs.slice(0, 1).forEach((e) => { inner += '<span class="cal-ev">' + esc(e.nome) + '</span>'; });
      cells += '<div class="cal-cell ' + (dia === hoje ? 'today' : '') + '">' + inner + '</div>';
    }

    const podePrev = estado.mes > ciclo.data_inicio.slice(0, 7);
    const podeNext = estado.mes < ciclo.data_fim.slice(0, 7);
    host.innerHTML = '<div class="cal"><div class="cal-head">' +
      '<button class="icon-btn" id="cal-prev" ' + (podePrev ? '' : 'disabled') + '>' + icon('chevronLeft') + '</button>' +
      '<h3>' + window.UI.MESES_LONGO[mo - 1] + ' ' + y + '</h3>' +
      '<button class="icon-btn" id="cal-next" ' + (podeNext ? '' : 'disabled') + '>' + icon('chevronRight') + '</button></div>' +
      '<div class="cal-grid">' + dows.map((d) => '<div class="cal-dow">' + d + '</div>').join('') + cells + '</div></div>';

    const prev = host.querySelector('#cal-prev'); const next = host.querySelector('#cal-next');
    if (prev) prev.addEventListener('click', () => { const dt = new Date(y, mo - 2, 1); estado.mes = dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0'); renderCalEnc(host, estado, sessoes, ciclo); });
    if (next) next.addEventListener('click', () => { const dt = new Date(y, mo, 1); estado.mes = dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0'); renderCalEnc(host, estado, sessoes, ciclo); });
  }
})();
