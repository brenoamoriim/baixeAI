# BaixeAI — Checklist do projeto

> Memória do projeto entre sessões. Atualizado a cada entrega. Última atualização: **17/10/2026** (Fase 1).

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

## Fase 2 — Fundação (`phase-2-fundacao`)
- [ ] Compose (api, worker, postgres, redis, frontend, beat) sobe com um comando no Windows
- [ ] ⚠️ Na máquina de dev, as portas **5432, 5433 e 6379 já estão em uso** por outros projetos → não publicar Postgres/Redis no host (ou usar 5434/6380)
- [ ] ⚠️ Python local é 3.10; backend roda em contêiner Python 3.12
- [ ] Modelos + migrações Alembic (`architecture/04`)
- [ ] Auth (cadastro, login, logout, verificação de e-mail, recuperação, sessões, Argon2id, rate limit, CSRF)
- [ ] Papéis `user`/`admin` + CLI do primeiro admin
- [ ] Registry de ferramentas/capacidades
- [ ] Núcleo de fichas (visitante, diária, plano, avulsas, vitalício, reserva/confirmação/devolução, expiração)
- [ ] Jobs + Celery + ferramenta "eco" (só dev/test)
- [ ] `StorageProvider` local + links assinados + limpeza
- [ ] Segurança base (headers, CORS, erros genéricos, logs, health checks)
- [ ] Frontend shell (pt-BR)
- [ ] Testes executados (incl. concorrência de `architecture/09` §2)

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
