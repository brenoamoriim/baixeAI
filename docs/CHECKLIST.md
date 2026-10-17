# BaixeAI — Checklist do projeto

> Memória do projeto entre sessões. Atualizado a cada entrega. Última atualização: **17/10/2026** (Fase 2).

Legenda: `[x]` feito e verificado · `[ ]` pendente · `[~]` parcial (ver nota)

## Fase 1 — Arquitetura e plano (`phase-1-arquitetura`) — ✅ concluída e aprovada (17/10/2026)

- [x] Inspeção do repositório (nada apagado; `COMO-USAR.md` mantido fora do versionamento)
- [x] `.gitignore` ampliado, `.gitattributes` (LF), `.env.example` sem segredos, `README.md`
- [x] Pesquisa Mercado Pago (taxas, Checkout Pro × Transparente, assinaturas, Pix Automático, webhook, reembolso, testes, PF) — `architecture/06`
- [x] Pesquisa de hospedagem gratuita (Oracle, Google, Render, HF, Fly, Koyeb, Railway, Neon) — `architecture/02`
- [x] Licenças dos motores e modelos — `architecture/07`
- [x] Verificação empírica dos motores em Docker (`python:3.12-slim`, Debian 13, amd64): FFmpeg 7.1.5 (GPL; x264, x265, VP9, AV1, Opus, MP3, AAC), libvips 8.16.1 (AVIF/WEBP/TIFF/GIF/JPG; HEIC só leitura), LibreOffice 25.2.3, Pandoc 3.1.11.1, pdftotext 25.03
- [~] Verificação em ARM64 emulado (alvo Oracle): libvips e FFmpeg OK; LibreOffice, Pandoc, leitura de HEIC e onnxruntime **não testados** em ARM64 — `architecture/07` §2.1
- [x] Políticas: AdSense, YouTube ToS, Mercado Pago (parcial), Oracle (página inacessível → NÃO VERIFICADO) — `architecture/12`
- [x] Entregáveis `docs/architecture/01` a `13`
- [x] Decisões dos sócios D1–D15 registradas em `architecture/12` §0 e aplicadas ao `PRD.md` (17/10/2026)
- [ ] Pendentes: vagas do lote vitalício; subdomínio gratuito (Fase 6); e-mail de suporte

## Fase 2 — Fundação (`phase-2-fundacao`) — ✅ concluída, aguardando aprovação

- [x] `docker compose up --build` sobe db, redis, migrate (migrações + seed), api, worker, beat e frontend (Windows + Docker Desktop)
- [x] Postgres/Redis não publicados no host (portas 5432/5433/6379 já usadas por outros projetos nesta máquina)
- [x] Backend em contêiner Python 3.12 (Python local é 3.10)
- [x] Modelos + migração Alembic inicial (upgrade → downgrade → upgrade testados); triggers append-only em `credit_ledger` e `audit_events`
- [x] Auth: cadastro, login, logout, verificação de e-mail, recuperação de senha (revoga sessões), Argon2id, cookies HttpOnly/SameSite, CSRF double-submit, rate limit por IP/e-mail, respostas sem enumeração de e-mail
- [x] Papéis `user`/`admin`; `python -m app.cli create-admin`; endpoint admin protegido
- [x] Registry de ferramentas/capacidades (só `available` + handler registrado é exposto); 4 ferramentas reais "Em breve"
- [x] Fichas: visitante (1 única, limite por IP), diária 5 (reset 00:00 SP, sem acúmulo, só com e-mail verificado e sem assinatura — D3b), plano Pro/Premium por ciclo (+1 mês de calendário), troca de plano com sobra somada (D5), avulsas por ferramenta 90 dias, vitalício sem contagem com teto 2 simultâneos / 50 por dia (D4), regras de custo (D1), reserva → confirmação → devolução (timeout devolve — D11), compensação de 24 h, sem cancelamento (D12), expiração periódica, reconciliação do ledger
- [x] Jobs (`queued, processing, completed, failed, expired`) + Celery + beat; ferramenta "eco" só fora de produção
- [x] `StorageProvider` local (chaves geradas no servidor, anti path traversal), link assinado **e** checagem de dono, limpeza automática
- [x] Segurança base: headers, CORS restrito, erros genéricos com request id, logs JSON, `/healthz` e `/readyz`, recusa iniciar em produção sem segredos fortes
- [x] Frontend pt-BR: início, entrar, cadastrar, recuperar/redefinir senha, verificar e-mail, painel (fichas por origem), componente genérico de ferramenta
- [x] Testes executados: backend 70 (incl. 6 de concorrência real); frontend 9; lint/typecheck ok; imagens de produção construídas a partir de clone limpo
- [ ] Pendências conhecidas → Fase 6: papel de banco sem superusuário para a API; Caddy sobrescrevendo `X-Forwarded-For`; provedor de e-mail real
- [ ] Pendência → Fase 3A: endpoint de **estimativa de custo** antes de confirmar (hoje o painel mostra o custo base; o backend sempre recalcula); workers por fila (`light`, `media`, `ai`, `download`)
- [ ] Pendência → Fase 4: criar assinatura/pacote pelo pagamento (hoje só via CLI)

## Fase 3A — Conversores
- [ ] Matriz real de codecs/filtros (amd64 + arm64)
- [ ] Combinações `available` com teste real cada
- [ ] Negativos de segurança
- [ ] Medição de tempo/memória
- [ ] UI `/conversores`

## Fase 3B — IA de imagem
- [ ] Licenças de código e pesos confirmadas
- [ ] Removedor de fundo
- [ ] Remover objeto (editor de máscara + inpainting)
- [ ] Métricas reais de CPU/memória
- [ ] Testes

## Fase 3C — Baixador de vídeos
- [ ] Adaptador `VideoExtractor` (yt-dlp)
- [ ] SSRF completo + isolamento de rede do worker
- [ ] Aceite de direitos
- [ ] Testes SSRF + integração

## Fase 4 — Monetização
- [ ] `PaymentProvider` + Mercado Pago (Checkout Pro + `/preapproval` cartão + renovação manual)
- [ ] Webhooks verificados e idempotentes
- [ ] Assinaturas, vitalício, estornos, reconciliação
- [ ] Testes no sandbox

## Fase 5 — Site público, dashboard, admin, conformidade
- [ ] Homepage, páginas de ferramenta com SEO
- [ ] Dashboard e admin (RBAC)
- [ ] LGPD/legal (marcado para revisão jurídica)
- [ ] AdSense/SEO técnico conforme decisão D13
- [ ] Lighthouse medido

## Fase 6 — Segurança e deploy
- [ ] Revisão de segurança completa
- [ ] Deploy Oracle + Cloudflare
- [ ] Backup + restauração testada
- [ ] Monitoramento, CI/CD, runbook
