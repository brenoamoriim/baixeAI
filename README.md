# BaixeAI

Plataforma web brasileira de utilitários online (freemium, moeda interna "ficha"):
baixador de vídeos, conversores, removedor de fundo e removedor de objetos.

> **Estado atual:** Fase 3A — **Conversores disponíveis** (174 combinações testadas com arquivos reais).
> Baixador de vídeos, removedor de fundo e removedor de objetos ainda aparecem como "Em breve".
> Veja [`docs/CHECKLIST.md`](docs/CHECKLIST.md) para o progresso.

## Rodar tudo (Windows 11 + Docker Desktop, PowerShell)

```powershell
docker compose up --build
```

Isso sobe: `db` (PostgreSQL), `redis`, `migrate` (aplica migrações + seed e encerra), `api`
(FastAPI), `worker`, `worker-light` (LibreOffice/libvips), `worker-media` (FFmpeg), `beat`
(Celery), `frontend` (Next.js) e `proxy` (Caddy). A primeira construção demora (baixa LibreOffice e FFmpeg).

| O quê | Endereço |
|---|---|
| **Site (use este)** | **http://localhost:8080** — mesmo roteamento da produção (`/api` direto para a API) |
| Next.js direto (só para desenvolvimento de interface; uploads > 10 MB falham aqui) | http://localhost:3000 |
| API (docs OpenAPI, só fora de produção) | http://localhost:8000/api/docs |
| Saúde | http://localhost:8000/healthz · http://localhost:8000/readyz |

PostgreSQL e Redis **não** são publicados no host (evita conflito com outros projetos nas
portas 5432/6379). Sem `.env`, o Compose usa valores de desenvolvimento. Para personalizar,
copie `.env.example` para `.env` (nunca versione o `.env`).

### E-mails em desenvolvimento

Não há envio real: o conteúdo (com o link de confirmação/recuperação) aparece no log da API:

```powershell
docker compose logs api | Select-String "token="
```

### Comandos de administração

```powershell
# primeiro admin (sem credencial embutida no código; a senha é pedida sem eco)
docker compose exec api python -m app.cli create-admin --email voce@exemplo.com

# concessões manuais até a Fase 4 (pagamentos):
docker compose exec api python -m app.cli grant-plan --email x@y.com --plan pro
docker compose exec api python -m app.cli set-next-plan --email x@y.com --plan premium
docker compose exec api python -m app.cli renew-plan --email x@y.com
docker compose exec api python -m app.cli grant-package --email x@y.com --tool converter
docker compose exec api python -m app.cli grant-lifetime --email x@y.com
```

> Para `create-admin` sem terminal interativo, use `--password` (fica no histórico do shell; evite em produção).

### Testes

```powershell
# backend: Postgres e Redis reais, banco separado `baixeai_test`
docker compose up -d db redis
docker compose run --rm --build migrate pytest

# testes com motores reais (conversões, negativos, fluxo completo)
docker compose run --rm --build --no-deps worker-light pytest tests/engines -o addopts=""
docker compose run --rm --build --no-deps worker-media pytest tests/engines -o addopts=""

# frontend
cd frontend; npm ci; npm test; npm run lint; npm run typecheck
```

### Conversores: o que fica disponível

Uma combinação só aparece no site se estiver em `backend/app/tools/converter/verified.json`, gerado
por conversão real dentro das imagens dos workers:

```powershell
docker compose run --rm --no-deps worker-light python -m app.tools.converter.verify --categories document,image
docker compose run --rm --no-deps worker-media python -m app.tools.converter.verify --categories audio,video
docker compose run --rm migrate python -m app.cli seed   # aplica o resultado ao banco
```

## Documentação

| Documento | Conteúdo |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Regras permanentes de trabalho |
| [`docs/PRD.md`](docs/PRD.md) | Regras de negócio (fonte da verdade) |
| [`docs/CHECKLIST.md`](docs/CHECKLIST.md) | Estado do projeto por fase |
| [`docs/architecture/`](docs/architecture/) | Arquitetura, custos, banco, fichas, pagamentos, segurança, testes, deploy, riscos, roadmap |

## Stack

- Frontend: Next.js 16 + React 19 + TypeScript + Tailwind CSS 4
- Backend: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 17
- Fila/cache/rate limit: Redis 8 + Celery 5
- Infra: Docker + Docker Compose

O backend roda em contêiner (Python 3.12); não é preciso instalar Python 3.12 no Windows.
