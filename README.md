# BaixeAI

Plataforma web brasileira de utilitários online (freemium, moeda interna "ficha"):
baixador de vídeos, conversores, removedor de fundo e remoção de objetos em imagens.

> **Estado atual:** Fase 1 — arquitetura e plano. Ainda não há código de aplicação.
> Veja [`docs/CHECKLIST.md`](docs/CHECKLIST.md) para o progresso.

## Documentação

| Documento | Conteúdo |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Regras permanentes de trabalho |
| [`docs/PRD.md`](docs/PRD.md) | Regras de negócio (fonte da verdade) |
| [`docs/CHECKLIST.md`](docs/CHECKLIST.md) | Estado do projeto por fase |
| [`docs/architecture/`](docs/architecture/) | Arquitetura, custos, banco, fichas, pagamentos, segurança, testes, deploy, riscos, roadmap |

## Stack (planejada)

- Frontend: Next.js + React + TypeScript + Tailwind CSS
- Backend: Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL
- Fila/cache/rate limit: Redis + Celery
- Infra: Docker + Docker Compose

## Ambiente de desenvolvimento

Windows 11 + VS Code + Docker Desktop (WSL 2). O backend roda em contêiner
(Python 3.12), então não é necessário instalar Python 3.12 no Windows.
Instruções de execução serão adicionadas na Fase 2.

## Segredos

Copie `.env.example` para `.env` e preencha localmente. **Nunca versione `.env`.**
