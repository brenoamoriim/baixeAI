# 09 — Estratégia de testes

> Fase 1 · 17/10/2026. Regra do projeto: nenhum "passou" sem a saída real colada no relatório.

## 1. Camadas

| Camada | Ferramenta | Roda contra | Exemplos |
|---|---|---|---|
| Unitário (backend) | pytest | código puro, sem I/O | cálculo de ciclo (31/01 → 28/02), ordem de consumo, classificação de erros, validação SSRF de IPs, parser de assinatura de webhook, sniffing de arquivo |
| Integração (backend) | pytest + Postgres/Redis reais (Compose de teste) | banco real, migrações Alembic aplicadas | reserva/confirmação/devolução, constraints, trigger append-only, webhook ponta a ponta com MP mockado (respx) |
| **Concorrência de fichas** | pytest + `asyncio.gather`/threads com conexões separadas | Postgres real | ver §2 |
| Motores (conversão) | pytest marcado `engines`, dentro da imagem do worker | FFmpeg/LibreOffice/libvips reais | uma prova por combinação `available` (ver `07`) |
| Segurança / abuso | pytest marcado `security` | API + workers | SSRF (lista de URLs hostis, DNS rebinding simulado, redirect para IP privado), polyglots, bombas de pixels/ZIP, webhooks com assinatura errada/replay, idempotência, rate limit |
| Frontend unitário | Vitest + Testing Library | componentes | formatação R$/data pt-BR, estados de job |
| E2E | Playwright | stack completa no Compose | cadastro → verificação de e-mail (provedor `console`) → conversão → download; compra no sandbox do MP (Fase 4) |
| Migrações | `alembic upgrade head` + `downgrade -1` + `upgrade head` | banco vazio | toda migração reversível ou marcada como irreversível |

## 2. Testes de concorrência obrigatórios (Fase 2)

1. Saldo 1, **20 reservas paralelas** com chaves diferentes → exatamente 1 sucesso, 19 "saldo insuficiente"; `available=0`, `reserved=1`; ledger com 1 `reserve`.
2. **20 reservas paralelas com a mesma chave** → 1 reserva, todas as respostas apontam para o mesmo job.
3. Commit e release concorrentes da mesma reserva → só uma transição vence.
4. Concessão diária concorrente (10 primeiros acessos do dia em paralelo) → 1 bucket.
5. Webhook duplicado em paralelo (5×) → 1 concessão.
6. Após cada teste: invariante `bucket = Σ ledger` verificada.

## 3. Critérios

- Comandos reais (backend por imagem, frontend e E2E): `README.md` → "Testes". E2E: `e2e/run.ps1` (Playwright 1.63.0 + axe 4.13.0 + Lighthouse 13.5.0, imagem `mcr.microsoft.com/playwright:v1.63.0-noble`), contra o build de produção atrás de um Caddy igual ao de dev. O cadastro no E2E é confirmado pelo comando de CLI `verify-email`, que recusa rodar com `APP_ENV=production`.
- Cobertura mínima nos módulos `services/credits`, `payments`, `security`: 90% de linhas (meta, medida com `coverage`); o restante sem meta numérica.
- Uma combinação de formato só vira `available` com teste de motor verde + arquivo de saída validado (assinatura e abertura pelo próprio motor/`ffprobe`).
- Testes de segurança fazem parte da suíte normal, não são opcionais.

## 4. Dados de teste

Arquivos de teste gerados por script (FFmpeg `testsrc`, libvips `black`, documentos mínimos) para não versionar binários grandes nem conteúdo de terceiros.
