# Backlog — Acesso (Fases B e C)

A **Fase A está entregue**: perfis, sessão, gate de rota em três alcances, rede de
segurança e a bateria de autorização. Ver `CLAUDE.md` § *Access control* e o README
§ *Acesso e perfis*.

Este documento é a fila do que ficou para depois. A intenção é que, ao ser chamado, cada
item seja **execução** — a decisão já está tomada e escrita aqui, com os arquivos, o
porquê e as armadilhas conhecidas. Se ao pegar um item a decisão parecer errada, revise-a
aqui primeiro; o pior desfecho é implementar o que este arquivo diz sem concordar com ele.

---

## FASE B — SSO institucional (login pelo e-mail da UFCSPA)

**Objetivo.** Trocar a porta de entrada: aluno e docente passam a entrar pelo e-mail
institucional, sem senha no nosso banco. Senha local permanece **só** como acesso de
exceção da coordenação/admin (SSO fora do ar, e os testes).

**Estimativa:** ~1 dia de código. **Bloqueio externo:** o registro do cliente OAuth.

### ⚠️ Verificar ANTES de escrever código

1. **`@ufcspa.edu.br` e `@aluno.ufcspa.edu.br` são Google Workspace ou Microsoft/Entra?**
   O botão que já existe no `login.html` é do Google, mas isso é herança do protótipo, não
   evidência. Se for Microsoft, o fluxo é o mesmo (OpenID Connect) e só muda o provedor —
   por isso o módulo nasce isolado em um arquivo só.
2. **Pedir o cliente OAuth ao TI da UFCSPA já** (redirect URI + tela de consentimento): é o
   item de maior tempo de espera. Dá para desenvolver e testar tudo com um cliente de
   desenvolvimento apontando para `localhost` enquanto o institucional não sai.
3. **Os dois domínios são o mesmo tenant?** Isso decide se `DOMINIOS_PERMITIDOS` é uma
   lista ou se são dois clientes OAuth.

### O que construir

**`app/services/sso_google.py`** (nome muda se o provedor for outro) — usa `httpx` e
`python-jose`, ambos já no `requirements.txt`; **nenhuma dependência nova**.

- `GET /login/google` → redireciona ao provedor com `scope=openid email profile` e um
  `state` guardado em cookie assinado (proteção CSRF: o `state` que volta tem que bater).
- `GET /login/google/callback` → troca o `code` por token no endpoint do provedor, via
  TLS server-side, e valida do `id_token`: `aud`, `iss`, `exp`, `email_verified` e o
  domínio (`hd`, conferido contra `DOMINIOS_PERMITIDOS`). Sucesso → `gravar_sessao`.
- Manter a chamada de rede **num lugar só**, para os testes conseguirem substituí-la
  (`monkeypatch`) sem encenar o provedor.

**Resolução de perfil**, nesta ordem — é o coração da fase:

1. `usuarios.email` existe e `ativo` → usa **aquele** perfil. Esta é a lista de exceção da
   comissão: é como se promove alguém a coordenação e como se revoga acesso.
2. casa com `docentes.email` → provisiona na hora (*just-in-time*) como `docente`.
3. casa com `alunos.email` do ciclo ativo — ou o começo do e-mail casa com a matrícula no
   domínio de aluno → provisiona como `aluno`, **gravando `usuarios.matricula`**.
4. nada casou → 403 pt-BR: "e-mail não vinculado a nenhum cadastro; procure a comissão".

O provisionamento automático é o que evita a comissão cadastrar ~60 alunos à mão por
ciclo. A tabela `usuarios` deixa de ser o cadastro e vira a lista de exceções.

**Configuração** (`core/config.py` + `.env.example`): `GOOGLE_CLIENT_ID`,
`GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `DOMINIOS_PERMITIDOS`,
`LOGIN_SENHA_LOCAL` (liga/desliga o formulário de senha).

**Tela:** reabilitar o botão do `login.html` (hoje `disabled`, com o título "em
implantação") e apontá-lo para `/login/google`.

### Armadilha conhecida: aluno sem e-mail não entra

Com SSO, a identidade **é** o e-mail — e `alunos.email` é `NULL`-ável (o modelo só
documenta o padrão `matricula@aluno.ufcspa.edu.br`). Aluno sem e-mail cadastrado
simplesmente não consegue entrar, e isso só apareceria no primeiro dia de aula.

**Providência:** uma checagem visível no passo *Revisão* do bootstrap — "N alunos sem
e-mail: não conseguirão acessar" — no mesmo espírito do resto do sistema (a tela avisa o
que impede). Onde: `services/analise_grade.py` alimenta a Revisão;
`templates/partials/revisao.html` exibe. Hoje, no banco de dev, os 10 alunos têm e-mail —
o problema é silencioso justamente por isso.

### Testes

- `monkeypatch` na troca do `code` por token: callback com e-mail de aluno conhecido cria
  a conta com perfil `aluno` e a matrícula certa.
- E-mail de domínio não permitido → 403; `state` divergente → 403; `email_verified=false`
  → 403.
- E-mail que está em `usuarios` como `coordenacao` **não** é rebaixado para `aluno` mesmo
  se também estiver em `alunos` (a ordem de resolução importa, e é o que protege a
  comissão de perder o próprio acesso).

---

## FASE C — Gestão de contas e auditoria

**Estimativa:** ~1 dia. Sem bloqueio externo. Pode ser feita antes da B se preferir.

### C1 · Tela "Usuários" (comissão)

Reaproveitar a maquinaria de `routers/ui/cadastros.py` (mesmo padrão de tabela + modal dos
outros recursos): listar, convidar/criar, trocar perfil, desativar, ver `ultimo_acesso`.
O service já existe inteiro em `app/services/usuario.py` — falta só a tela.

Guarda a implementar: **não deixar o sistema sem nenhuma coordenação ativa**. O service já
tem `existe_algum_editor()` para isso; a tela precisa recusar o último rebaixamento ou
desativação com mensagem pt-BR.

### C2 · "Esqueci minha senha"

Hoje é link morto: `login.html` tem `href="#"` e `static/js/app.js:68` mostra um toast
"não disponível na demonstração". Duas saídas, e **a segunda é a recomendada**:

- reset por e-mail (token de uso único, validade curta) — exige servidor de e-mail;
- com SSO no ar, a resposta honesta é "entre pelo e-mail institucional", e o reset de
  senha local vira ação da coordenação na tela C1. Menos código, menos superfície.

Decidir junto com a Fase B; enquanto o link existir sem função, ele promete o que o
sistema não faz.

### C3 · Trocar a própria senha

Tela simples para quem usa senha local (coordenação/admin). `usuario_service.trocar_senha`
já existe e já valida tamanho.

### C4 · Auditoria: quem fez

Hoje `Atividade` (`models/operacao.py`) grava `ciclo_id`, `quando`, `texto` e `tipo` —
**não grava quem**. Com contas nominais isso passa a ser respondível e é a pergunta óbvia
quando a escala mudar sem aviso ("quem gerou?", "quem aplicou o remanejo?").

Trabalho: migration acrescentando `atividade.usuario_id` (FK `usuarios`, `NULL`-ável para
o histórico já existente), e passar a sessão aos pontos que registram —
`services/common.registrar_atividade` e quem chama. Exibir o nome no feed do painel.

Cuidado: os services são independentes do FastAPI de propósito (§ *Application structure*).
Passe o `usuario_id` como **parâmetro**, não leia a sessão dentro do service.

---

## Fora do escopo destas fases, mas aberto

**`analise_grade.sugerir_dias` não é determinístico.** Quando duas áreas empatam em
tamanho de fila, qual delas recebe as sugestões varia com `PYTHONHASHSEED` — a tabela pode
nomear outra área entre dois carregamentos da mesma tela, contra o invariante documentado
do motor. Descoberto em 08/08/2026, durante a Fase A. Reproduz sempre:

```bash
PYTHONHASHSEED=3 pytest tests/test_bootstrap_oferta.py::test_painel_nao_diz_que_todos_fecham_quando_a_simulacao_reprova   # falha
PYTHONHASHSEED=0 …                                                                                                        # passa
```

Já descartados: orçamento de tempo (teto de 40 s; a suíte inteira roda em ~9 s) e a ordem
de `aguardando`/`fila_areas` (ambas estáveis). A suspeita é desempate por iteração de
`set`/`dict` dentro de `_atribuir_busca`/`_qualidade`, mudando **em qual área** cada aluno
fica esperando. Na suíte aparece como falha intermitente (~1 em 11 execuções).

**Não mascarar fixando `PYTHONHASHSEED` no pytest** — isso esconde o bug em vez de
resolvê-lo, e o bug é visível para a comissão.
