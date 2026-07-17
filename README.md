# Gestão de Estágios — Fonoaudiologia UFCSPA

Sistema web para a **comissão de estágios da Fonoaudiologia da UFCSPA** planejar a
**escala de estágios** dos alunos ao longo do ciclo (ano letivo). Substitui o antigo
fluxo em planilha Excel por um motor de escalonamento determinístico, com ajustes
manuais validados e visualização para professores e alunos.

- **Quem edita:** apenas a comissão (~5 coordenadores).
- **Quem visualiza:** professores e alunos (somente leitura).

---

## Stack

| Camada        | Tecnologia                                              |
|---------------|--------------------------------------------------------|
| API / servidor| **FastAPI** + Uvicorn                                  |
| ORM / banco   | **SQLAlchemy 2.x** (síncrono, `psycopg2`) + **PostgreSQL** |
| Migrações     | **Alembic**                                            |
| Config        | Pydantic + pydantic-settings (lê o `.env`)             |
| Frontend      | **Jinja2 + HTMX** (server-rendered, sem SPA)           |
| Testes        | **pytest** (contra um PostgreSQL real)                 |

---

## Como rodar

Pré-requisitos: **Python 3.11+** e um **PostgreSQL** acessível.

```bash
# 1. Ambiente virtual + dependências
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configuração
cp .env.example .env          # depois edite: DATABASE_URL + SECRET_KEY

# 3. Banco de dados
alembic upgrade head          # aplica as migrações
python scripts/seed.py        # (re)carrega catálogos a partir de docs/seed_v2.sql

# 4. Servidor de desenvolvimento
uvicorn app.main:app --reload # http://localhost:8000
```

> ⚠️ **`scripts/seed.py` faz TRUNCATE ... RESTART IDENTITY CASCADE** nas tabelas de
> catálogo. O CASCADE em `ciclos` também apaga alunos/matrículas/eventos. **Rode apenas
> contra um banco de catálogo/desenvolvimento.**

### Variáveis de ambiente (`.env`)

```env
DATABASE_URL=postgresql+psycopg2://postgres:SUA_SENHA@localhost:5432/estagios_fono
SECRET_KEY=troque-por-uma-chave-aleatoria-longa
APP_ENV=dev
```

`DATABASE_URL` não tem valor padrão — o app falha rápido se não estiver definida.

---

## Testes

```bash
pytest                                       # tudo
pytest tests/test_motor_escala.py            # um arquivo
pytest tests/test_motor_escala.py::test_nome -x   # um teste, para no 1º erro
pytest -k "restricoes"                        # por padrão de nome
```

Os testes **usam um PostgreSQL real** (o banco de `DATABASE_URL`), não um em memória.
Antes de rodar: o banco deve existir, as migrações aplicadas (`alembic upgrade head`) e o
seed carregado (`python scripts/seed.py`). Cada teste roda dentro de uma transação
externa revertida no teardown, então nada persiste.

---

## O motor de escala (`app/services/motor/`)

É o coração do sistema. A **spec autoritativa é [`docs/REGRAS_MOTOR_ESCALA.md`](docs/REGRAS_MOTOR_ESCALA.md)**
(referenciada por seção, ex. §5.3) — leia antes de mexer no motor.

**Ideia central — _grade-primeiro_ ("grid-first"):** a escala **não** é orientada pela
demanda. Primeiro o sistema materializa o *molde* inteiro (todos os grupos possíveis =
"caixas", para todos os locais, com datas reais) e só depois preenche com alunos. As
datas são função **apenas** da infraestrutura (calendário + afastamentos + nº de
encontros); trocar quem está na fila muda o *conteúdo* das caixas, nunca redesenha as
caixas. Há uma única fonte de verdade para as datas.

**Pipeline** (orquestrado por `motor/escala.py::gerar_escala`):

1. **`molde.py`** — puro (sem DB): fatia as datas viáveis por (local, dia) em blocos
   consecutivos de N encontros; cada bloco completo vira uma `Caixa`. Bloco final
   incompleto é descartado (§8.1).
2. **`preenchimento.py`** — preenche o molde. Objetivo lexicográfico:
   (1) COBERTURA (máximo de alunos concluindo suas áreas), depois (2) OCUPAÇÃO (empacotar
   caixas). Resolve as áreas de cada aluno _most-constrained-first_ (§5.3).
3. **`consolidacao.py`** — "sempre tentar fechar" (§6): move ocupantes de caixas fracas
   para caixas quase cheias da mesma área sem reduzir a cobertura. Ocupantes fixados não
   se movem.

**Módulos de apoio:**

- **`restricoes.py`** — as **4 restrições rígidas** (§3) + escassez. Invioláveis, sem
  override, mesmo no ajuste manual. `MAX_HORAS_SEMANAIS = 30`, `INTERVALO_MIN_HORAS = 2`.
- **`ajuste.py`** — ajuste manual (§9). A saída do motor é uma *sugestão editável*; cada
  operação recomputa as 4 restrições ANTES de aplicar e recusa se violar.
- **`montagem.py`** — pré-montagem manual (AR-8): coordenador marca alunos `prioridade` e
  os arrasta para caixas vazias; cada colocação é um PIN validado ao vivo.
- **`estado.py`** — ponte entre a escala persistida (grupos/alocações) e a `Caixa` em
  memória.
- **`calendario.py`**, **`encontros.py`**, **`eventos_ciclo.py`** — datas, ocorrências de
  sessão e eventos de meio de ciclo (§10). **`persistencia.py`** — grava o molde/escala.

---

## Estrutura do projeto

```
app/
├── main.py            # montagem do app: routers, CORS, estáticos, exception handlers
├── core/              # config, database (engine/SessionLocal/get_db), errors, templates
├── models/            # modelos SQLAlchemy — enums.py mapeia 1:1 com os CREATE TYPE do Postgres
├── schemas/           # schemas Pydantic (request/response)
├── services/          # regras de negócio (independentes do FastAPI, testáveis isoladas)
│   └── motor/         # o motor de escala (ver acima)
├── routers/           # routers REST JSON (thin), delegam para os services
│   └── ui/            # páginas server-rendered + parciais HTMX (gate por estado do ciclo)
├── templates/         # páginas Jinja2 + partials/ (fragmentos HTMX)
└── static/            # CSS/JS/img

alembic/               # migrações (env.py lê DATABASE_URL do .env)
docs/                  # REGRAS_MOTOR_ESCALA.md, seed_v2.sql, modelagem_dados/
scripts/               # seed.py
tests/                 # pytest (conftest, factories, testes do motor e da API/UI)
```

### Conceitos do domínio

- **Ciclo** = um ano letivo de estágio; o aluno tem um ano para cumprir a carga de todas
  as suas áreas. `StatusCiclo`: `rascunho` → `em_andamento` → `encerrado`.
- **Slot**: o que se oferta não é o campo físico, mas o *slot* (1 local = 1 campo + dia +
  turno). Cada local é uma família de caixas.
- **FaseArea**: `_7` = mini-ciclo (7º semestre, Audiologia I); `_9_10` = 9º/10º semestre
  (demais áreas).
- **`StatusMatricula.incompleta`** = período encerrado com encontros concluídos < N →
  carrega para o próximo ciclo (§10.5).

---

## Migrações

O Alembic lê `DATABASE_URL` do `.env` (nada hardcoded no `alembic.ini`). A convenção de
nomes fica em `core/database.py` (`NAMING_CONVENTION`) — mantenha em sincronia.

```bash
alembic upgrade head                                   # aplicar
alembic revision --autogenerate -m "descricao"         # nova migração
```

---

## Documentação

- **[`docs/REGRAS_MOTOR_ESCALA.md`](docs/REGRAS_MOTOR_ESCALA.md)** — spec autoritativa do motor.
- **`docs/modelagem_dados/`** — schema canônico (`modelagem_dados_v2.sql`, DBML e
  `DOCUMENTACAO_MODELO_DADOS_V2.md`).
- **`docs/seed_v2.sql`** — seed fonte da verdade (derivado do ESPELHO 2026).
- **`CLAUDE.md`** — guia de trabalho no repositório.

---

## Idioma

Domínio, comentários, docstrings, identificadores e UI são em **Português (pt-BR)**.
Mensagens de erro exibidas ao usuário também.
