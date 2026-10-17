# 03 — Estrutura do repositório

> Fase 1 · 17/10/2026. Árvore proposta; diretórios são criados conforme cada fase precisar deles.

```
baixeAI/
├── CLAUDE.md                     # regras permanentes
├── README.md
├── .env.example                  # template sem segredos
├── .gitignore / .gitattributes   # LF obrigatório (scripts rodam em Linux)
├── docker-compose.yml            # dev (Fase 2)
├── docker-compose.prod.yml       # overrides de produção (Fase 6)
│
├── frontend/                     # Next.js + TS + Tailwind
│   ├── src/app/                  # rotas (App Router): (public)/, (auth)/, dashboard/, admin/, ferramentas/
│   ├── src/components/
│   ├── src/lib/api/              # cliente HTTP tipado (gerado do OpenAPI)
│   ├── src/lib/i18n/             # textos pt-BR, formatação R$ e datas
│   ├── tests/                    # unit (Vitest) + e2e (Playwright)
│   └── Dockerfile
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/               # Alembic
│   ├── app/
│   │   ├── main.py               # app FastAPI
│   │   ├── api/                  # routers HTTP finos (v1/auth, v1/jobs, v1/credits, v1/payments, v1/admin, webhooks)
│   │   ├── core/                 # config (pydantic-settings), logging, tempo/fuso, erros
│   │   ├── models/               # SQLAlchemy ORM
│   │   ├── schemas/              # Pydantic (entrada/saída)
│   │   ├── repositories/         # acesso a dados; locks (FOR UPDATE) concentrados aqui
│   │   ├── services/             # regras de negócio: credits, plans, jobs, users, guests
│   │   ├── workers/              # app Celery, roteamento de filas, tarefas agendadas
│   │   ├── tools/                # registry + um pacote por ferramenta
│   │   │   ├── registry.py
│   │   │   ├── base.py           # interface ToolHandler
│   │   │   ├── converter/        # documents.py, images.py, audio.py, video.py
│   │   │   ├── background_remover/
│   │   │   ├── object_remover/
│   │   │   └── video_downloader/ # adapter yt-dlp
│   │   ├── payments/             # provider abstrato + mercadopago/ (client, webhook, reconcile)
│   │   ├── storage/              # StorageProvider: local.py, s3.py (futuro)
│   │   └── security/             # passwords (argon2id), sessions, csrf, ssrf, file_sniffing, rate_limit, sandbox (subprocess com timeout/rlimit)
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/          # Postgres/Redis reais via Compose
│   │   ├── concurrency/          # corrida de fichas
│   │   ├── security/             # SSRF, uploads maliciosos, webhooks falsos
│   │   └── fixtures/             # arquivos de teste pequenos e gerados
│   └── Dockerfile                # multi-stage; alvos: api, worker-light, worker-media, worker-ai, worker-download
│
├── infrastructure/
│   ├── caddy/Caddyfile
│   ├── postgres/                 # init, configuração
│   ├── redis/redis.conf          # ACL, AOF
│   ├── firewall/                 # regras DOCKER-USER (bloqueio de IPs privados para a rede egress)
│   └── backup/                   # scripts pg_dump + criptografia + envio
│
├── scripts/                      # utilitários (PowerShell .ps1 e bash .sh quando exigir WSL/Linux)
│
└── docs/
    ├── PRD.md
    ├── CHECKLIST.md
    ├── CUSTOS-GRATIS-VS-PAGO.md  # rascunho original; versão verificada em architecture/02
    └── architecture/             # 01 a 13
```

## Convenções

- Uma imagem base de backend (`python:3.12-slim`, Debian) com **alvos multi-stage** por worker: cada worker instala só os motores de que precisa (LibreOffice não vai para o `worker-ai`, por exemplo).
- Todas as imagens precisam ser **multi-arquitetura (amd64 + arm64)**: o desenvolvimento é x86_64 (Docker Desktop) e a hospedagem recomendada é ARM (Oracle Ampere A1). Ver `02` e `10`.
- `api/` só traduz HTTP ↔ serviço. Regra de negócio fica em `services/`. Locks de banco ficam em `repositories/`.
- Nomes de código/tabelas em inglês; textos de interface em pt-BR em `frontend/src/lib/i18n/`.
