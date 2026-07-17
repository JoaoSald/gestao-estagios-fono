/* ============================================================================
   bootstrap.js — Fluxo 1: carrossel de abertura de ciclo (10 passos).
   Cada "Avançar" persiste o passo (retomável após refresh).
   ============================================================================ */
(function () {
  'use strict';
  const { icon, esc, fmtData } = window.UI;
  const S = window.State;
  window.Views = window.Views || {};

  const PASSOS = ['Ciclo', 'Docentes', 'Áreas e Locais', 'Preceptores', 'Configurações de campo', 'Afastamentos', 'Alunos', 'Eventos', 'Montagem dos grupos', 'Revisão & Geração'];
  const NPASSOS = PASSOS.length; // 10
  let sub7 = 'revisao'; // sub-tela do passo final: revisao | gerando | relatorio
  let relatorio = null;

  // Nome da área com prefixo da área-mãe p/ sub-áreas de áreas compostas (ex.: "Audiologia II · SADT (SA)").
  const nomeComMae = (a, st) => (a && a.area_mae ? ((st.areas.find((x) => x.id === a.area_mae) || {}).nome || '') + ' - ' : '') + (a ? a.nome : '');

  function stepper(atual) {
    let out = '<div class="stepper">';
    PASSOS.forEach((p, i) => {
      const n = i + 1;
      const cls = n < atual ? 'done' : n === atual ? 'current' : '';
      out += '<div class="step ' + cls + '" data-goto="' + n + '"><span class="num">' +
        (n < atual ? icon('check') : n) + '</span><span>' + p + '</span></div>';
      if (i < PASSOS.length - 1) out += '<span class="step-line ' + (n < atual ? 'done' : '') + '"></span>';
    });
    return out + '</div>';
  }

  // --------- tabelinha compacta reutilizada nos passos ----------------------
  //  maxH (opcional): altura máx. com rolagem vertical + cabeçalho fixo — usado
  //  nos passos que ficam extensos (Docentes, Alunos).
  // dragFase (opcional): quando setado, as linhas ficam arrastáveis p/ reordenar a
  // prioridade daquela fase (7 | 9_10). A tabela ganha data-fase-list e cada linha
  // data-drag-id — o mount cuida do drag-and-drop.
  function miniTable(cols, rows, maxH, dragFase) {
    if (!rows.length) return '<div class="empty"><div class="ei">' + icon('file') + '</div>Nada cadastrado ainda.</div>';
    const wrapCls = 'tbl-wrap scroll-x' + (maxH ? ' scroll-y' : '');
    const wrapStyle = maxH ? ' style="max-height:' + maxH + '"' : '';
    const tblAttr = dragFase ? ' data-fase-list="' + dragFase + '"' : '';
    return '<div class="' + wrapCls + '"' + wrapStyle + '><table class="tbl"' + tblAttr + '><thead><tr>' +
      cols.map((c) => '<th>' + c + '</th>').join('') + '<th></th></tr></thead><tbody>' +
      rows.map((r) => '<tr' + (dragFase ? ' draggable="true" data-drag-id="' + r.id + '" style="cursor:grab"' : '') + '>' +
        r.cells.map((c) => '<td>' + c + '</td>').join('') +
        '<td><div class="row-actions">' +
          (r.edit ? '<button class="icon-btn btn-sm" data-edit="' + r.id + '">' + icon('edit') + '</button>' : '') +
          (r.del ? '<button class="icon-btn btn-sm" data-del="' + r.id + '">' + icon('trash') + '</button>' : '') +
        '</div></td></tr>').join('') +
      '</tbody></table></div>';
  }

  function passoBody(n) {
    const st = S.get();
    const c = S.cicloAtivo();
    if (n === 1) {
      return '<div class="card"><div class="card-head"><h3>Passo 1 · Dados do ciclo</h3></div><div class="card-body">' +
        '<p class="muted mb">É com base no intervalo início→fim que o sistema monitora o avanço, prevê o fechamento de carga e emite alertas de risco.</p>' +
        '<div class="form-grid">' +
          '<div class="field"><label>Data de início</label><input class="input" type="date" id="ci" value="' + c.data_inicio + '"></div>' +
          '<div class="field"><label>Data de fim</label><input class="input" type="date" id="cf" value="' + c.data_fim + '"></div>' +
        '</div><div class="field-err" id="err1" style="display:none"></div></div></div>';
    }
    if (n === 2) {
      const rows = st.docentes.map((d) => ({ id: d.id, edit: true, del: false,
        cells: [esc(d.nome), d.email ? esc(d.email) : '<span class="dim">—</span>',
          d.ativo ? '<span class="badge b-concluida"><span class="dt"></span>ativo</span>' : '<span class="badge b-neutral">inativo</span>'] }));
      return card('Passo 2 · Docentes', 'Professores da UFCSPA. Atravessam ciclos — venha antes de preceptores, afastamentos e locais. O e-mail é usado nas notificações.',
        '<button class="btn btn-primary btn-sm" data-add="docente">' + icon('plus') + ' Novo docente</button>',
        miniTable(['Nome', 'E-mail', 'Status'], rows, '46vh'));
    }
    if (n === 3) {
      const chip = (a) => '<span class="area-pill" style="background:' + a.cor + '22;color:' + a.cor + '"><span class="dt" style="background:' + a.cor + '"></span>' + esc(nomeComMae(a, st)) + '</span>';
      // ---- ÁREAS (simples + compostas). Sub-áreas são geridas DENTRO da edição da área. ----
      const linhaArea = (a) => '<div class="flex between" style="align-items:center;padding:.32rem 0;border-bottom:1px solid var(--border)">' +
        '<div>' + chip(a) + ' <span class="dim">· ' + a.carga_exigida + 'h</span>' + (a.pre_requisito ? ' <span class="badge b-iniciar">pré-req</span>' : '') + '</div>' +
        '<button class="icon-btn btn-sm" data-edit-area="' + a.id + '" title="Editar área">' + icon('edit') + '</button></div>';
      const simples = st.areas.filter((a) => !a.area_mae && !a.composta);
      const containers = st.areas.filter((a) => a.composta);
      let areasHtml = simples.map(linhaArea).join('');
      containers.forEach((mae) => {
        const filhos = st.areas.filter((a) => a.area_mae === mae.id);
        const soma = filhos.reduce((s, f) => s + f.carga_exigida, 0);
        areasHtml += '<div class="flex between" style="align-items:center;margin-top:.7rem;padding-top:.4rem;border-top:2px solid var(--border)">' +
          '<div>' + chip(mae) + ' <span class="dim">· composta · total ' + mae.carga_exigida + 'h (' + filhos.length + ' sub-áreas, soma ' + soma + 'h)</span></div>' +
          '<button class="icon-btn btn-sm" data-edit-area="' + mae.id + '" title="Editar área e sub-áreas">' + icon('edit') + '</button></div>' +
          '<div style="padding-left:.9rem" class="dim">' + (filhos.map((f) => '<div style="padding:.2rem 0">↳ ' + esc(f.nome) + ' · ' + f.carga_exigida + 'h</div>').join('') || '<div style="padding:.2rem 0">sem sub-áreas</div>') + '</div>';
      });
      const areasCard = card('Passo 3a · Áreas', 'Simples (o aluno cumpre em qualquer local) e compostas (edite a área para criar/remover sub-áreas com CH que somam o total, ex.: Audiologia II, Hospitalar).',
        '<button class="btn btn-primary btn-sm" data-add="area">' + icon('plus') + ' Nova área</button>', areasHtml);

      // ---- LOCAIS (slots) + resumo de slots paralelos por área ----
      const rows = st.locais.map((l) => {
        const ar = st.areas.find((a) => a.id === l.area_id);
        return { id: l.id, edit: true, del: true, cells: [
          ar ? chip(ar) : '<span class="dim">—</span>',
          '<b>' + esc(l.campo) + '</b>' + (l.unidade ? '<div class="hint">' + esc(l.unidade) + '</div>' : ''),
          window.UI.diasLabel(l) + ' · ' + window.UI.turnoLabel(l.turno) + ' · ' + l.hora_inicio + '–' + l.hora_fim,
          '<b>' + (l.numero_encontros || '?') + '</b> enc', l.capacidade + ' vagas'] };
      });
      const porArea = {};
      st.locais.filter((l) => l.ativo).forEach((l) => { (porArea[l.area_id] = porArea[l.area_id] || []).push(l); });
      const resumo = Object.keys(porArea).map((aid) => {
        const ar = st.areas.find((a) => a.id === aid); const ls = porArea[aid];
        const capTot = ls.reduce((s, l) => s + l.capacidade, 0);
        return '<div class="hint">' + (ar ? esc(ar.nome) : aid) + ': <b>' + ls.length + ' slot(s)</b> → ' + ls.length + ' grupo(s) em paralelo · até <b>' + capTot + '</b> aluno(s)/leva · ~' + (ls[0].numero_encontros || '?') + ' encontros p/ concluir</div>';
      }).join('') || '<span class="dim">Nenhum local cadastrado.</span>';
      const locaisCard = card('Passo 3b · Locais (slots)', 'Cada dia de um campo é um SLOT = 1 grupo que roda EM PARALELO com os outros dias. O nº de encontros vem de CH ÷ horas por encontro.',
        '<button class="btn btn-primary btn-sm" data-add="local">' + icon('plus') + ' Novo local</button>',
        '<div class="mb" style="padding:.2rem .1rem .6rem;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:.2rem">' + resumo + '</div>' +
        miniTable(['Área', 'Campo / Unidade', 'Quando', 'Encontros', 'Capacidade'], rows, '34vh'));
      return areasCard + '<div style="height:1rem"></div>' + locaisCard;
    }
    if (n === 4) {
      // CATÁLOGO de preceptores (igual ao passo Docentes): listar, editar,
      // ativar/desativar, cadastrar. O vínculo com o local vem no passo seguinte.
      const rows = (st.preceptores || []).map((p) => ({ id: p.id, edit: true, del: false,
        cells: [esc(p.nome), p.email ? esc(p.email) : '<span class="dim">—</span>',
          p.ativo ? '<span class="badge b-concluida"><span class="dt"></span>ativo</span>' : '<span class="badge b-neutral">inativo</span>'] }));
      return card('Passo 4 · Preceptores', 'Fonoaudiólogas(os) de campo — atravessam ciclos, igual aos docentes. Ative/desative ou cadastre novos (a conta é o e-mail). No passo seguinte (Configurações de campo) você vincula cada um a um local.',
        '<button class="btn btn-primary btn-sm" data-add="preceptor">' + icon('plus') + ' Novo preceptor</button>',
        miniTable(['Nome', 'E-mail', 'Status'], rows, '46vh'));
    }
    if (n === 5) {
      // CONFIGURAÇÕES DE CAMPO: por local, escolher o DOCENTE responsável e o
      // PRECEPTOR de campo (opcional). Ambos saem dos catálogos (Docentes/Preceptores).
      const trs = st.locais.map((l) => {
        const ar = st.areas.find((a) => a.id === l.area_id);
        const docsOpt = '<option value="">— escolher docente —</option>' +
          st.docentes.filter((d) => d.ativo || d.id === l.docente_id)
            .map((d) => '<option value="' + d.id + '"' + (d.id === l.docente_id ? ' selected' : '') + '>' + esc(d.nome) + '</option>').join('');
        return '<tr>' +
          '<td><span class="area-pill" style="background:' + ar.cor + '22;color:' + ar.cor + '"><span class="dt" style="background:' + ar.cor + '"></span>' + esc(nomeComMae(ar, st)) + '</span></td>' +
          '<td><b>' + esc(l.campo) + '</b>' + (l.unidade ? '<div class="hint">' + esc(l.unidade) + '</div>' : '') + '</td>' +
          '<td class="hint">' + window.UI.diasLabel(l) + ' · ' + window.UI.turnoLabel(l.turno) + '<div class="hint">' + l.hora_inicio + '–' + l.hora_fim + '</div></td>' +
          '<td><select class="select" data-doc-local="' + l.id + '">' + docsOpt + '</select></td>' +
          '<td><select class="select" data-prec-local="' + l.id + '">' + window.Forms.opcoesPreceptor(l, true) + '</select></td>' +
        '</tr>';
      }).join('');
      const tabela = st.locais.length
        ? '<div class="tbl-wrap scroll-x scroll-y" style="max-height:52vh"><table class="tbl"><thead><tr>' +
            '<th>Área</th><th>Local</th><th>Quando</th><th>Docente responsável</th><th>Preceptor de campo</th></tr></thead><tbody>' + trs + '</tbody></table></div>'
        : '<div class="empty"><div class="ei">' + icon('building') + '</div>Cadastre os locais no passo "Áreas e Locais" primeiro.</div>';
      return card('Passo 5 · Configurações de campo',
        'Cada linha é um SLOT = local · dia · turno (o mesmo campo pode ter vários slots — ex.: segunda de manhã e segunda de tarde, para grupos diferentes). Por slot, escolha o DOCENTE responsável e o PRECEPTOR de campo (opcional — às vezes só o docente responde; pode repetir a mesma pessoa em vários slots). Um slot só cai quando docente E preceptor estiverem afastados ao mesmo tempo.',
        '', tabela);
    }
    if (n === 6) {
      const rows = st.afastamentos.map((a) => {
        const ehPrec = !!a.preceptor_id;
        const p = ehPrec ? (st.preceptores || []).find((x) => x.id === a.preceptor_id) : st.docentes.find((x) => x.id === a.docente_id);
        const papel = ehPrec ? '<span class="badge b-iniciar">preceptor</span>' : '<span class="badge b-andamento">docente</span>';
        return { id: a.id, edit: true, del: true, cells: [esc(p ? p.nome : '?') + ' ' + papel,
          '<span class="badge b-neutral">' + a.tipo + '</span>', esc(a.motivo || '—'), fmtData(a.data_inicio) + ' → ' + fmtData(a.data_retorno)] };
      });
      return card('Passo 6 · Afastamentos', 'Férias, licenças e outras ausências — cada registro referencia um docente OU um preceptor.',
        '<button class="btn btn-primary btn-sm" data-add="afastamento">' + icon('plus') + ' Novo afastamento</button>',
        miniTable(['Pessoa', 'Tipo', 'Motivo', 'Período'], rows));
    }
    if (n === 7) {
      // Sem ordenação manual: marca-se só quem tem PRIORIDADE (checkbox). Esses vão
      // para a Montagem dos grupos (posicionamento à mão); o resto o motor aloca.
      const linha = (al) => {
        const mats = st.matriculas.filter((m) => m.aluno_id === al.id);
        const emAnd = mats.filter((m) => m.status === 'em_andamento').length;
        const conc = mats.filter((m) => m.status === 'concluida').length;
        const chk = '<label class="check ' + (al.prioridade ? 'on' : '') + '" style="padding:.1rem .45rem"><input type="checkbox" data-prio-aluno="' + al.id + '"' + (al.prioridade ? ' checked' : '') + '><span>prioridade</span></label>';
        return { id: al.id, edit: true, del: true, cells: [esc(al.nome),
          esc(al.matricula), al.email ? esc(al.email) : '<span class="dim">—</span>', 'Sem. ' + al.semestre,
          emAnd + ' em andamento' + (conc ? ' · <span class="dim">' + conc + ' concl.</span>' : ''), chk] };
      };
      const porFase = (f) => st.alunos.filter((a) => (+a.semestre <= 7) === (f === '7')).sort((a, b) => a.ordenamento - b.ordenamento);
      const cols = ['Aluno', 'Matrícula', 'E-mail', 'Semestre', 'Matrículas', 'Prioridade'];
      const secao = (titulo, sub, fase, rows) =>
        '<div class="flex between" style="align-items:center;margin:.2rem 0 .55rem">' +
          '<div><b>' + titulo + '</b> <span class="dim">· ' + rows.length + ' aluno(s)</span><div class="hint">' + sub + '</div></div>' +
          '<button class="btn btn-secondary btn-sm" data-add-fase="' + fase + '">' + icon('plus') + ' Novo aluno</button>' +
        '</div>' + miniTable(cols, rows, '32vh');
      const body =
        '<p class="hint" style="margin:0 0 .7rem">Marque <b>prioridade</b> em quem você quer <b>posicionar à mão</b> no passo <b>Montagem dos grupos</b>. Não precisa ordenar todo mundo — o resto o sistema aloca sozinho (prioritários não-colocados primeiro, depois por matrícula).</p>' +
        secao('7º semestre — mini-ciclo', 'Cursam apenas o estágio de Audiologia I.', '7', porFase('7').map(linha)) +
        '<div style="height:1.2rem"></div>' +
        secao('9º/10º semestre — demais estágios', 'Começam com Audiologia I concluída (pré-requisito).', '9_10', porFase('9_10').map(linha));
      return card('Passo 7 · Alunos', 'Alunos do ciclo por fase. Marque quem tem prioridade (posicionamento manual na Montagem). O e-mail é usado nas notificações.', '', body);
    }
    if (n === 8) {
      const rows = st.eventos.map((e) => ({ id: e.id, edit: true, del: true, cells: [esc(e.nome),
        '<span class="badge b-neutral">' + e.tipo + '</span>', '<span class="dim">' + e.origem + '</span>',
        fmtData(e.data_inicio), e.bloqueia_estagio ? '<span class="badge b-risco"><span class="dt"></span>bloqueia</span>' : '<span class="badge b-andamento"><span class="dt"></span>não bloqueia</span>'] }));
      return card('Passo 8 · Eventos', 'Eventos acadêmicos manuais. Feriados nacionais/estaduais já vêm importados automaticamente.',
        '<button class="btn btn-primary btn-sm" data-add="evento">' + icon('plus') + ' Novo evento</button>',
        miniTable(['Nome', 'Tipo', 'Origem', 'Data', 'Estágio'], rows));
    }
    if (n === 9) {
      // MONTAGEM DOS GRUPOS: molde vazio (caixas por área/slot/onda) + banco de
      // alunos de prioridade. Arrasta-se o aluno para a vaga; a CH vai somando.
      S.materializarMoldeVazio();
      const banco = S.bancoPrioridade();
      const chip = (a) => '<span class="badge b-neutral" draggable="true" data-drag-aluno="' + a.id + '" style="cursor:grab;display:inline-flex;gap:.35rem;align-items:center;margin:.15rem">' + esc(a.nome) + ' <span class="dim">' + (+a.semestre <= 7 ? '7º' : '9/10') + ' · ' + S.chSemanaAlunoGrupos(a.id) + 'h/sem</span></span>';
      const bancoHtml = banco.length
        ? banco.map((a) => chip(a)).join('')
        : '<span class="dim">Nenhum aluno de prioridade pendente. Marque "prioridade" no passo Alunos.</span>';
      const porArea = {};
      (st.grupos || []).forEach((g) => { (porArea[g.area_id] = porArea[g.area_id] || []).push(g); });
      // uma "onda" (caixa) = 1 dropzone; agrupada por ÁREA → SLOT (local·dia·turno).
      const ondaCard = (g, l) => {
        const lot = g.membros.length >= l.capacidade;
        const membros = g.membros.map((m) => { const al = st.alunos.find((a) => a.id === m.aluno_id);
          return '<span class="badge b-andamento" style="display:inline-flex;gap:.3rem;align-items:center;margin:.12rem">' + esc(al ? al.nome : '?') +
            ' <button class="icon-btn btn-sm" data-rm-aluno="' + m.aluno_id + '" data-rm-grupo="' + g.id + '" title="Tirar">' + icon('x') + '</button></span>'; }).join('');
        return '<div class="card" data-dropzone-grupo="' + g.id + '" style="padding:.5rem;border:1px ' + (lot ? 'solid' : 'dashed') + ' var(--border);border-radius:.5rem">' +
          '<div class="flex between" style="align-items:center"><b>Onda ' + g.onda + '</b> <span class="badge ' + (lot ? 'b-concluida' : 'b-iniciar') + '">' + g.membros.length + '/' + l.capacidade + '</span></div>' +
          '<div class="hint">' + fmtData(g.data_inicio) + ' – ' + fmtData(g.data_fim) + '</div>' +
          '<div style="margin-top:.3rem;min-height:1.6rem">' + (membros || '<span class="dim">arraste um aluno aqui</span>') + '</div>' +
        '</div>';
      };
      const areasHtml = Object.keys(porArea).length ? Object.keys(porArea).map((aid) => {
        const ar = st.areas.find((a) => a.id === aid);
        const porLocal = {};
        porArea[aid].forEach((g) => { (porLocal[g.local_id] = porLocal[g.local_id] || []).push(g); });
        const slots = Object.keys(porLocal).map((lid) => {
          const l = st.locais.find((x) => x.id === lid); if (!l) return '';
          const ondas = porLocal[lid].slice().sort((a, b) => a.onda - b.onda).map((g) => ondaCard(g, l)).join('');
          // cabeçalho do SLOT: campo + nº de encontros + dia/turno/horário (uma vez só)
          return '<div style="border-left:3px solid ' + ar.cor + ';padding:.15rem 0 .35rem .65rem;margin:.5rem 0">' +
            '<div class="flex between" style="align-items:baseline;flex-wrap:wrap;gap:.4rem">' +
              '<div><b>' + esc(l.campo) + '</b>' + (l.unidade ? ' <span class="dim">· ' + esc(l.unidade) + '</span>' : '') +
                ' <span class="badge b-neutral">' + (l.numero_encontros || '?') + ' enc · ' + (l.horas_sessao || '?') + 'h/enc</span></div>' +
              '<span class="hint">' + window.UI.diasLabel(l) + ' · ' + window.UI.turnoLabel(l.turno) + ' · ' + l.hora_inicio + '–' + l.hora_fim + ' · ' + ((l.horas_sessao || 0) * ((l.dias && l.dias.length) || 1)) + 'h/sem · ' + l.capacidade + ' vagas/onda</span>' +
            '</div>' +
            '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.45rem;margin-top:.35rem">' + ondas + '</div>' +
          '</div>';
        }).join('');
        return '<div style="margin-bottom:1.2rem"><div style="margin:.2rem 0 .3rem"><span class="area-pill" style="background:' + ar.cor + '22;color:' + ar.cor + '"><span class="dt" style="background:' + ar.cor + '"></span>' + esc(nomeComMae(ar, st)) + '</span></div>' + slots + '</div>';
      }).join('') : '<div class="empty"><div class="ei">' + icon('layers') + '</div>Sem molde — cadastre locais e datas nos passos anteriores.</div>';
      return card('Passo 9 · Montagem dos grupos',
        'Pré-monte as caixas: arraste os alunos de PRIORIDADE (banco abaixo) para as vagas. A CH de cada aluno vai somando. O que você NÃO posicionar, o sistema preenche ao gerar a escala (prioritários não-colocados primeiro, depois por matrícula).', '',
        '<div class="mb" style="padding:.55rem;border:1px dashed var(--border);border-radius:.6rem">' +
          '<div class="hint" style="font-weight:700;margin-bottom:.3rem">Banco de prioridade — arraste para uma caixa</div>' + bancoHtml + '</div>' +
        '<div class="tbl-wrap scroll-y" style="max-height:52vh">' + areasHtml + '</div>');
    }
    if (n === 10) return passoFinal();
    return '';
  }

  function card(titulo, sub, acts, body) {
    return '<div class="card"><div class="card-head"><div><h3>' + titulo + '</h3><div class="card-sub">' + sub + '</div></div>' + (acts || '') + '</div>' +
      '<div class="card-body">' + body + '</div></div>';
  }

  // --------- passo final: revisão / geração / relatório ---------------------
  function passoFinal() {
    if (sub7 === 'gerando') {
      return '<div class="card"><div class="card-body gen-stage">' +
        '<div class="spinner"></div>' +
        '<h3 class="mt">Gerando a escala…</h3>' +
        '<p class="muted">O motor está alocando alunos por prioridade, respeitando capacidade, conflitos, afastamentos e eventos.</p>' +
        '<div class="gen-log" id="gen-log"></div></div></div>';
    }
    if (sub7 === 'relatorio' && relatorio) return relatorioBody();
    return revisaoBody();
  }

  function revisaoBody() {
    const st = S.get();
    const avisos = [];
    // Containers de áreas compostas (composta:true) não têm local próprio — os locais apontam para as sub-áreas leaf; checa só as leaf.
    st.areas.filter((ar) => !ar.composta).forEach((ar) => { if (!st.locais.some((l) => l.area_id === ar.id && l.ativo)) avisos.push('Área <b>' + esc(nomeComMae(ar, st)) + '</b> não tem nenhum local ativo.'); });
    st.locais.filter((l) => l.ativo && !l.docente_id).forEach((l) => avisos.push('Local <b>' + esc(l.campo) + '</b> está sem docente responsável — defina em Configurações de campo.'));
    st.alunos.forEach((al) => { if (!st.matriculas.some((m) => m.aluno_id === al.id)) avisos.push('Aluno <b>' + esc(al.nome) + '</b> está sem matrícula inicial.'); });
    // capacidade x demanda por área (só leaf — matrículas e locais são por sub-área)
    st.areas.filter((ar) => !ar.composta).forEach((ar) => {
      const cap = st.locais.filter((l) => l.area_id === ar.id && l.ativo).reduce((s, l) => s + l.capacidade, 0);
      const dem = st.matriculas.filter((m) => m.area_id === ar.id && m.status === 'em_andamento').length;
      if (dem > cap) avisos.push('Área <b>' + esc(nomeComMae(ar, st)) + '</b>: demanda (' + dem + ') maior que a capacidade total (' + cap + ').');
    });

    const resumo = [
      ['Alunos', st.alunos.length, 'users'], ['Docentes', st.docentes.filter((d) => d.ativo).length, 'teacher'],
      ['Preceptores', (st.preceptores || []).filter((p) => p.ativo).length, 'user'],
      ['Locais ativos', st.locais.filter((l) => l.ativo).length, 'building'], ['Afastamentos', st.afastamentos.length, 'calendarOff'],
      ['Eventos', st.eventos.length, 'calendar'], ['Áreas', st.areas.length, 'layers'],
    ].map((r) => '<div class="kpi"><div class="khead"><span class="kicon">' + icon(r[2]) + '</span>' + r[0] + '</div><div class="kval">' + r[1] + '</div></div>').join('');

    return '<div class="stack">' +
      '<div class="grid g-3">' + resumo + '</div>' +
      card('Revisão de completude', 'Avisos não impedem a geração — apenas sinalizam.', '',
        avisos.length ?
          '<div class="stack" style="gap:.6rem">' + avisos.map((a) => '<div class="flex" style="gap:.6rem;color:var(--st-risco)">' + icon('alert') + '<span style="color:var(--text)">' + a + '</span></div>').join('') + '</div>'
          : '<div class="flex" style="gap:.6rem;color:var(--st-concluida)">' + icon('checkCircle') + '<span style="color:var(--text)">Tudo pronto — nenhuma pendência de completude.</span></div>') +
      '<div class="card"><div class="card-body text-c">' +
        '<div class="al-avatar" style="margin:0 auto 1rem;background:linear-gradient(135deg,var(--brand-400),var(--brand-600))">' + icon('sparkles') + '</div>' +
        '<h3>Pronto para gerar a alocação</h3>' +
        '<p class="muted">O motor criará as alocações (aluno × local) e as sessões (datas concretas) na ordem de prioridade.</p>' +
        '<button class="btn btn-primary mt" id="btn-gerar">' + icon('sparkles') + ' Gerar alocação</button>' +
      '</div></div></div>';
  }

  function relatorioBody() {
    const r = relatorio;
    const st = S.get();
    const grupos = st.grupos || [];
    const emAnd = grupos.filter((g) => g.status === 'em_andamento').length;
    const prev = grupos.filter((g) => g.status === 'previsto').length;
    const naFila = r.sem_vaga.length;
    const kpis = [
      ['Grupos em andamento', emAnd, 'layers', ''],
      ['Grupos previstos', prev, 'calendar', ''],
      ['Alocações geradas', r.alocados, 'grid', ''],
      ['Aguardando vaga', naFila, 'clock', naFila > 0 ? 'warn' : ''],
    ].map((k) => '<div class="kpi ' + k[3] + '"><div class="khead"><span class="kicon">' + icon(k[2]) + '</span>' + k[0] + '</div><div class="kval">' + k[1] + '</div></div>').join('');

    // Grupos formados — MESMA view da tela de Estágios (por área → locais → grupos),
    // já com troca de aluno/grupo habilitada (no bootstrap ainda não começou, nada trava).
    const gruposHtml = (window.Views.gruposRender ? window.Views.gruposRender() : '');

    const nota = naFila
      ? '<div class="flex" style="gap:.6rem;color:var(--st-risco);margin-top:.6rem">' + icon('clock') + '<span style="color:var(--text)"><b>' + naFila + '</b> par(es) aluno×área ficam aguardando vaga (entram em ondas seguintes ou por conflito/restrição). Ajuste os grupos aqui mesmo, trocando pessoas ou grupos.</span></div>'
      : '';

    return '<div class="stack">' +
      '<div class="flex between"><div><h2>Escala do ciclo — grupos formados</h2><p class="muted">Mesma visão da tela de Estágios. Como o ciclo ainda não começou, você pode <b>trocar pessoas</b> e <b>trocar grupos</b> aqui — nada trava até o 1º dia de cada grupo.</p></div>' +
        '<span class="badge b-concluida"><span class="dt"></span>Escala gerada</span></div>' +
      '<div class="grid g-4">' + kpis + '</div>' +
      card('Grupos formados por área', 'Filtre por área e ajuste (trocar aluno / trocar grupo) antes de confirmar.', '', gruposHtml + nota) +
      '<div class="wizard-foot">' +
        '<button class="btn btn-secondary" id="btn-refazer">' + icon('chevronLeft') + ' Voltar à revisão</button>' +
        '<button class="btn btn-primary" id="btn-confirmar">' + icon('checkCircle') + ' Confirmar e iniciar operação</button>' +
      '</div></div>';
  }

  // --------- render principal -----------------------------------------------
  window.Views.bootstrap = function () {
    const c = S.cicloAtivo();
    const n = c.passo_bootstrap || 1;
    // SALVAGUARDA: a sub-tela de geração/relatório (sub7) só é válida NO passo final e
    // recém-gerado. Qualquer passo anterior reseta para 'revisao'. Sem isto, voltar à
    // Montagem (que refaz o molde vazio, zerando S.grupos) e avançar mostraria um
    // relatório STALE — todos "na fila" — sem ter clicado em "Gerar alocação".
    if (n !== NPASSOS && sub7 !== 'revisao') sub7 = 'revisao';
    const ano = S.parse(c.data_inicio).getFullYear();
    const temaIc = document.documentElement.getAttribute('data-theme') === 'dark' ? 'sun' : 'moon';

    const footer = n < NPASSOS || sub7 === 'revisao' ?
      '<div class="wizard-foot">' +
        (n > 1 ? '<button class="btn btn-secondary" id="btn-voltar">' + icon('chevronLeft') + ' Voltar</button>' : '<span></span>') +
        (n < NPASSOS ? '<button class="btn btn-primary" id="btn-avancar">Avançar ' + icon('chevronRight') + '</button>' : '<span></span>') +
      '</div>' : '';

    return '<div class="content" style="max-width:960px">' +
      '<div class="flex between mb"><div class="flex" style="gap:.7rem">' +
        '<div class="brand" style="padding:0;border:none"><div class="logo">' + icon('logo') + '</div></div>' +
        '<div><h1 style="font-size:1.3rem">Abertura do Ciclo ' + ano + '</h1><p class="muted" style="margin:0">Bootstrap · passo ' + n + ' de ' + NPASSOS + '</p></div>' +
      '</div>' +
      '<button class="icon-btn" id="btn-tema-bs">' + icon(temaIc) + '</button></div>' +
      stepper(n) +
      '<div class="bootstrap-body" id="bs-body">' + passoBody(n) + '</div>' +
      footer +
      '</div>';
  };

  window.Views.bootstrap_mount = function () {
    const c = S.cicloAtivo();
    const n = c.passo_bootstrap || 1;

    const tb = document.getElementById('btn-tema-bs');
    if (tb) tb.addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme');
      const novo = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', novo);
      try { localStorage.setItem('tema', novo); } catch (e) {}
      window.rerender();
    });

    // navegação do stepper (só para passos já visitados/preenchidos)
    document.querySelectorAll('.step[data-goto]').forEach((el) => {
      el.addEventListener('click', () => {
        const alvo = +el.getAttribute('data-goto');
        if (alvo <= n) { if (alvo < NPASSOS) sub7 = 'revisao'; S.setPassoBootstrap(alvo); window.rerender(); }
      });
    });

    // botões de add/edit/del dos passos
    document.querySelectorAll('[data-add]').forEach((b) => b.addEventListener('click', () => {
      window.Forms[b.getAttribute('data-add')](null, () => window.rerender());
    }));
    // botões "Novo aluno" por fase (passo 5) — pré-preenchem o semestre
    document.querySelectorAll('[data-add-fase]').forEach((b) => b.addEventListener('click', () => {
      const fase = b.getAttribute('data-add-fase');
      window.Forms.aluno(null, () => window.rerender(), { semestre: fase === '7' ? 7 : 9 });
    }));
    // passo 3 (Áreas): editar área (as sub-áreas são geridas dentro da edição)
    document.querySelectorAll('[data-edit-area]').forEach((b) => b.addEventListener('click', () => {
      window.Forms.area(b.getAttribute('data-edit-area'), () => window.rerender());
    }));
    document.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () => {
      const tipo = { 2: 'docente', 3: 'local', 4: 'preceptor', 6: 'afastamento', 7: 'aluno', 8: 'evento' }[n];
      window.Forms[tipo](b.getAttribute('data-edit'), () => window.rerender());
    }));
    document.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => {
      const map = { 3: ['locais', 'Local'], 6: ['afastamentos', 'Afastamento'], 7: ['alunos', 'Aluno'], 8: ['eventos', 'Evento'] }[n];
      window.Forms.remover(map[0], b.getAttribute('data-del'), map[1], null);
    }));
    // passo 6 (Alunos): reordenar por DRAG-AND-DROP — a ordem da lista = prioridade
    // da fase. Cada tabela é uma fase; o drag fica restrito à própria fase.
    document.querySelectorAll('table[data-fase-list]').forEach((tbl) => {
      let dragId = null;
      tbl.querySelectorAll('tr[data-drag-id]').forEach((tr) => {
        tr.addEventListener('dragstart', (e) => { dragId = tr.getAttribute('data-drag-id'); try { e.dataTransfer.setData('text/plain', dragId); } catch (_) {} e.dataTransfer.effectAllowed = 'move'; tr.style.opacity = '0.4'; });
        tr.addEventListener('dragend', () => { tr.style.opacity = ''; });
        tr.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; });
        tr.addEventListener('drop', (e) => {
          e.preventDefault();
          const src = dragId && tbl.querySelector('tr[data-drag-id="' + dragId + '"]');
          if (!src || src === tr) return;
          const rect = tr.getBoundingClientRect();
          const depois = (e.clientY - rect.top) > rect.height / 2;
          tr.parentNode.insertBefore(src, depois ? tr.nextSibling : tr);
          const ids = Array.prototype.slice.call(tbl.querySelectorAll('tr[data-drag-id]')).map((x) => x.getAttribute('data-drag-id'));
          S.reordenarAlunosFase(ids); window.rerender();
        });
      });
    });
    // passo 6 (Alunos): digitar a posição (alternativa ao arrastar)
    document.querySelectorAll('[data-ord-aluno]').forEach((inp) => {
      const aplicar = () => { S.definirPosicaoAluno(inp.getAttribute('data-ord-aluno'), inp.value); window.rerender(); };
      inp.addEventListener('change', aplicar);
      inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); aplicar(); } });
      inp.addEventListener('mousedown', (e) => e.stopPropagation()); // não inicia drag ao focar
    });
    // passo 5 (Configurações de campo): dropdown de DOCENTE responsável por local
    document.querySelectorAll('[data-doc-local]').forEach((sel) => sel.addEventListener('change', () => {
      const local = S.get().locais.find((l) => l.id === sel.getAttribute('data-doc-local'));
      if (!local) return;
      local.docente_id = sel.value || null;
      S.save();
    }));
    // passo 5 (Configurações de campo): dropdown de PRECEPTOR de campo por local
    document.querySelectorAll('[data-prec-local]').forEach((sel) => sel.addEventListener('change', () => {
      const local = S.get().locais.find((l) => l.id === sel.getAttribute('data-prec-local'));
      if (!local) return;
      if (sel.value === '__novo__') {
        window.Forms.preceptor(null, (novoId) => {
          if (novoId) { window.Forms.aplicarPreceptor(local, 'externo:' + novoId); S.save(); }
          window.rerender();
        });
        window.rerender(); // reseta o select enquanto o modal de cadastro está aberto
        return;
      }
      window.Forms.aplicarPreceptor(local, sel.value);
      S.save();
    }));

    // passo 7 (Alunos): checkbox de PRIORIDADE
    document.querySelectorAll('[data-prio-aluno]').forEach((cb) => cb.addEventListener('change', () => {
      S.togglePrioridade(cb.getAttribute('data-prio-aluno'), cb.checked); window.rerender();
    }));
    // passo 9 (Montagem): drag-and-drop dos alunos de prioridade nas caixas
    let _dragAluno = null;
    document.querySelectorAll('[data-drag-aluno]').forEach((ch) => {
      ch.addEventListener('dragstart', (e) => { _dragAluno = ch.getAttribute('data-drag-aluno'); try { e.dataTransfer.setData('text/plain', _dragAluno); } catch (_) {} e.dataTransfer.effectAllowed = 'move'; ch.style.opacity = '0.4'; });
      ch.addEventListener('dragend', () => { ch.style.opacity = ''; });
    });
    document.querySelectorAll('[data-dropzone-grupo]').forEach((dz) => {
      dz.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; dz.style.outline = '2px solid var(--brand-400)'; });
      dz.addEventListener('dragleave', () => { dz.style.outline = ''; });
      dz.addEventListener('drop', (e) => {
        e.preventDefault(); dz.style.outline = '';
        const alunoId = _dragAluno || (e.dataTransfer && e.dataTransfer.getData('text/plain'));
        if (!alunoId) return;
        const motivo = S.colocarAlunoNoGrupo(alunoId, dz.getAttribute('data-dropzone-grupo'));
        if (motivo) window.UI.toast('Não coube: ' + motivo, 'warn');
        window.rerender();
      });
    });
    document.querySelectorAll('[data-rm-aluno]').forEach((b) => b.addEventListener('click', () => {
      S.removerAlunoDoGrupo(b.getAttribute('data-rm-aluno'), b.getAttribute('data-rm-grupo')); window.rerender();
    }));

    // avançar
    const av = document.getElementById('btn-avancar');
    if (av) av.addEventListener('click', () => {
      if (n === 1) {
        const ini = document.getElementById('ci').value, fim = document.getElementById('cf').value;
        const err = document.getElementById('err1');
        if (!ini || !fim || fim <= ini) { err.textContent = 'Datas inválidas: o fim deve ser posterior ao início.'; err.style.display = 'block'; return; }
        c.data_inicio = ini; c.data_fim = fim; S.save();
      }
      S.setPassoBootstrap(n + 1); window.rerender();
    });
    const vt = document.getElementById('btn-voltar');
    if (vt) vt.addEventListener('click', () => { S.setPassoBootstrap(n - 1); window.rerender(); });

    // passo final
    const gerar = document.getElementById('btn-gerar');
    if (gerar) gerar.addEventListener('click', rodarGeracao);
    // relatório: reutiliza a view de Grupos → aciona o mesmo mount (filtro por área + trocas)
    if (n === NPASSOS && sub7 === 'relatorio' && window.Views.gruposMount) window.Views.gruposMount();
    const refazer = document.getElementById('btn-refazer');
    if (refazer) refazer.addEventListener('click', () => { sub7 = 'revisao'; window.rerender(); });
    const confirmar = document.getElementById('btn-confirmar');
    if (confirmar) confirmar.addEventListener('click', () => {
      c.status = 'em_andamento'; c.passo_bootstrap = null;
      S.registrarAtividade('Ciclo iniciado — escala confirmada', 'ciclo');
      S.save();
      window.UI.toast('Ciclo em andamento! Bem-vindo ao painel.', 'success');
      location.hash = '#/painel';
    });
  };

  function rodarGeracao() {
    sub7 = 'gerando';
    window.rerender();
    // spinner + log animado, depois gera de fato
    const logs = [
      'Ordenando alunos por prioridade…',
      'Verificando capacidade dos locais…',
      'Resolvendo conflitos de dia/turno/horário…',
      'Descontando afastamentos e eventos bloqueantes…',
      'Prevendo datas de conclusão por área…',
    ];
    const box = document.getElementById('gen-log');
    logs.forEach((l, i) => setTimeout(() => {
      if (box) { const d = document.createElement('div'); d.className = 'ln'; d.style.animationDelay = '0s';
        d.innerHTML = window.UI.icon('check') + '<span>' + l + '</span>'; box.appendChild(d); }
    }, 350 * (i + 1)));
    setTimeout(() => {
      relatorio = S.gerarEscala();
      S.save();
      sub7 = 'relatorio';
      window.rerender();
    }, 350 * (logs.length + 1) + 400);
  }
})();
