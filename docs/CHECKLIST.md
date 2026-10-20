# BaixeAI — Checklist do projeto

> Memória do projeto entre sessões. Atualizado a cada entrega. Última atualização: **18/10/2026** (Fase 4).

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
- [ ] Pendências conhecidas → Fase 6: papel de banco sem superusuário para a API; provedor de e-mail real (Caddy sobrescrevendo `X-Forwarded-For`: feito em dev na 3A)
- [x] ~~Pendência → Fase 3A: estimativa de custo e workers por fila~~ (feito na 3A; filas `ai` e `download` nas fases 3B/3C)
- [ ] Pendência → Fase 4: criar assinatura/pacote pelo pagamento (hoje só via CLI)

## Fase 3A — Conversores (`phase-3a-conversores`) — ✅ concluída, aguardando aprovação

- [x] Matriz real: FFmpeg 7.1.5, LibreOffice 25.2.3, libvips 8.16.1, poppler, rsvg verificados dentro das imagens `worker-light`/`worker-media` (amd64)
- [x] **174 combinações `available`**, cada uma com conversão real automatizada (`verified.json` + `tests/engines/test_conversions.py`); 0 falhas
- [x] Upload: detecção do formato real (assinatura/estrutura), limites por categoria (doc 25 MB, imagem 20 MB, áudio 50 MB, vídeo 95 MB/10 min), nome gerado no servidor, **inspeção em worker isolado antes de cobrar**
- [x] Motores em sandbox (sem shell, ambiente mínimo, timeout, rlimits, kill do grupo); workers sem internet, rootfs só leitura, sem capabilities
- [x] Segurança: libvips com loaders "untrusted" bloqueados (inclui ImageMagick); SVG sanitizado + `rsvg-convert`; bombas de pixel/ZIP; demuxer forçado no FFmpeg; macros desativadas (ver limitação do teste em `architecture/08` §3.2)
- [x] API: upload, status do upload, estimativa de custo exata, criação de job (só `available`), download assinado + dono
- [x] D1 aplicado: vídeo custa 2 fichas; MP4 só com áudio é tratado como áudio (1 ficha)
- [x] Frontend `/conversores`: arrastar e soltar, catálogo pesquisável, só saídas disponíveis para o formato detectado, opções em listas fechadas, custo antes de confirmar, progresso, download, avisos de limitação
- [x] Proxy Caddy em dev (porta 8080) igual à produção: uploads grandes funcionam e `X-Forwarded-For` falso é ignorado (testado)
- [x] Medição real de tempo/memória (`architecture/02` §6) — máquina de dev x86, não ARM
- [x] Testes: API 114 passed; worker-light 110 passed; worker-media 106 passed; frontend 14 passed
- [ ] ARM64: LibreOffice/HEIC/tempos não medidos em ARM real → Fase 6
- [ ] Workers ainda têm credenciais do banco no ambiente (risco residual) → papel de banco mínimo na Fase 6

## Fase 3B — IA de imagem (`phase-3b-ia-imagem`) — ✅ concluída, aguardando aprovação

- [x] Licenças confirmadas e registradas (`architecture/07` §4): ONNX Runtime MIT; IS-Net Apache-2.0; LaMa ONNX Apache-2.0; BRIA descartado (comercial pago)
- [x] Interfaces `BackgroundRemovalProvider` / `InpaintingProvider`; modelo carregado 1× por processo
- [x] `worker-ai` separado (fila `ai`), modelos no build com SHA-256, sem internet, concorrência 1 derivada da memória medida (2,3 GB)
- [x] Removedor de fundo: PNG/WEBP transparente ou cor sólida, JPG com cor; antes/depois; download
- [x] Removedor de objetos: editor de pincel (desfazer/limpar/tamanho), máscara no tamanho real, margem configurável, recorte + inpainting, antes/depois; aceite de direitos obrigatório e registrado
- [x] 18/18 combinações verificadas com os modelos reais; latência e memória medidas (`architecture/02` §7)
- [x] Testes: worker-ai 38 passed, 27 deles com os modelos (combinações, opções inválidas, máscara vazia/errada/de outro usuário, aceite, falha do modelo com devolução, EXIF girado + GPS removido); API 115, worker-light 111, worker-media 107, frontend 17
- [x] onnxruntime tem wheel oficial aarch64 (pendência da Fase 1 resolvida no papel; execução em ARM real → Fase 6)
- [ ] Termos do dataset Places2 (treino do LaMa): NÃO VERIFICADO
- [ ] Qualidade em fotos reais (cabelo, objetos grandes): avaliada só com imagens sintéticas nos testes automáticos

## Fase 3C — Baixador de vídeos (`phase-3c-baixador`) — ✅ concluída, aguardando aprovação

- [x] `VideoExtractor` + implementação yt-dlp 2026.8.19 (Unlicense), API Python, sem shell/cookies/login/playlists/ao vivo
- [x] SSRF completo: validação na API + **proxy de egresso próprio** que revalida cada conexão e disca o IP validado (redirects, URLs de mídia, DNS rebinding)
- [x] `worker-download` isolado: sem banco, sem internet direta, sem segredos; resultado volta por tarefas no worker padrão (testado de dentro do contêiner)
- [x] Fluxo: consulta gratuita → opções reais → custo (D1 por duração real) → aceite de direitos registrado → job → progresso real → link assinado
- [x] Links diretos medidos com ffprobe via proxy; duração desconhecida → recusado (sem inventar preço)
- [x] Erros honestos e classificados (privado, login, DRM, indisponível, bloqueio da plataforma, endereço proibido…)
- [x] Taxa de sucesso por domínio (sem dados pessoais) em `GET /api/v1/admin/download-stats`
- [x] Integração real: URLs de domínio público da NASA no Wikimedia Commons, 3/3 (MP4 480p, M4A, MP3) pela internet via proxy
- [x] Testes: API 178 passed (inclui 39 de SSRF/proxy e 15 de orquestração); worker-download 63 passed (24 do extrator com yt-dlp real e isolamento de rede + 39 de SSRF/proxy); worker-light 120, worker-media 116, worker-ai 47, frontend 17
- [x] Riscos registrados sem rodeios em `architecture/12` §4
- [ ] Taxa de sucesso a partir de IP de datacenter (Oracle) → medir na Fase 6
- [ ] Revisão jurídica do aviso de direitos e canal de remoção → Fase 5/6
- [ ] ACL do Redis para o `worker-download` → Fase 6

## Fase 4 — Monetização (`phase-4-monetizacao`) — ✅ implementada; ⚠️ validação no sandbox real pendente (sem credenciais)

- [x] Decisões: lote vitalício 50 vagas; tolerância de 3 dias no cartão; reembolso pelo suporte executado pelo admin (PRD atualizado)
- [x] `PaymentProvider` + implementação Mercado Pago (REST/httpx); regra de negócio não conhece o provedor
- [x] Catálogo e preços só do banco; preço enviado pelo navegador é ignorado (teste)
- [x] Checkout Pro (Pix, crédito, débito) para avulsas, ciclo manual e vitalício; assinatura no cartão via `/preapproval` pendente (sem dados de cartão no nosso site)
- [x] Webhook verificado (HMAC + janela de tempo), idempotente, com reconsulta à API; concessão exatamente uma vez (teste com 5 em paralelo)
- [x] Estados: pendente, aprovado, recusado, cancelado, expirado, estornado, chargeback, em disputa
- [x] Assinaturas: ativação, renovação (novo ciclo, sem acúmulo), troca no próximo ciclo com sobra somada, cancelamento até o fim do ciclo, tolerância de 3 dias
- [x] Vitalício sem ledger de fichas; estorno revoga; vagas esgotam
- [x] Estorno/chargeback por lançamento compensatório; reembolso do admin proporcional e em até 7 dias
- [x] Reconciliação (webhook perdido recuperado) e auditoria de divergências
- [x] Frontend: `/precos`, `/pagamento/retorno` (nunca concede), histórico e gestão da assinatura no painel
- [x] Testes: API 221 passed (31 de pagamentos + 12 unitários do provedor)
- [ ] **Credenciais de TESTE do Mercado Pago** (sócios) → `docs/architecture/11` "Fase 4"
- [ ] Rodar `sandbox_check` + compras de teste reais (Pix, crédito, débito, assinatura, reembolso) — confirmar `init_point` da assinatura pendente e o formato de `/authorized_payments`
- [ ] Credenciais de produção + pagamento real de valor mínimo → Fase 6

## Fase 5 — Site público, dashboard, admin, conformidade (`phase-5-site-publico`) — ✅ concluída e aprovada

- [x] Homepage: busca universal ("pdf para word", "tirar fundo"), categorias, ferramentas, resumo de planos (vem da API), FAQ
- [x] Páginas de ferramenta renderizadas no servidor: título/descrição/canonical/OpenGraph, "como usar", formatos, limites, FAQ, JSON-LD (WebApplication + FAQPage)
- [x] SEO técnico: `robots.txt`, `sitemap.xml` (só páginas públicas), `noindex` em painel/admin/login/cadastro/pagamento
- [x] AdSense (D13): só com flag `ads_enabled` + `adsense_client_id` + consentimento; nunca em `/baixar-videos`, conta, admin, auth, pagamento e preços; `ads.txt` gerado do publisher id (existe mesmo com anúncios desligados, para a aprovação). Banner de consentimento só aparece com anúncios ligados
- [x] Páginas legais **em rascunho, com aviso visível de "sem revisão jurídica"**: termos (uso justo e vitalício revisável a cada 6 meses), privacidade, reembolso, cookies, direitos de conteúdo, contato (e-mail de suporte configurável pelo admin)
- [x] Painel: download dos resultados recentes, alterar senha (desconecta outros dispositivos), exportar dados (LGPD, JSON), excluir conta (anonimiza; registros financeiros mantidos)
- [x] Admin (`/admin`, RBAC no servidor): visão geral, ferramentas, combinações (só `available` se verificada), regras de custo, planos/pacotes, configurações e flags, pagamentos com reembolso e reconciliação, assinaturas, usuários (suspender), auditoria. Ações sensíveis pedem a senha de novo; tudo auditado
- [x] Correções achadas pelos testes: páginas de login/cadastro sem `<h1>`; link só por cor (`link-in-text-block`); `crypto.randomUUID` quebrava o botão fora de HTTPS (agora `getRandomValues` + tratamento de erro); CLS 0,75 nas páginas de ferramenta (espaço reservado); 401 no console de visitantes (`/me/session`)
- [x] Testes: frontend 23 (Vitest); E2E Playwright 47 (axe WCAG A/AA sem violações em 14 páginas públicas, desktop e mobile; jornada cadastro → confirmação → conversão PNG→JPG → download com assinatura JPEG → saldo 5→4; admin: senha errada recusada, mudança salva/revertida e auditada); backend API 263 passed
- [x] Lighthouse medido (build de produção, local): ver `docs/architecture/measurements/phase-5-lighthouse.json`
- [ ] **Revisão jurídica** de todas as páginas legais (sócios + advogado) — obrigatória antes do lançamento
- [ ] AdSense: conta, aprovação, IDs de bloco (sócios) → `docs/VALIDACOES-DOS-SOCIOS.md` Fase 5
- [ ] E-mail de suporte (depende de domínio) → configurar em Admin → Configurações

## Fase 6 — Segurança e deploy (`phase-6-seguranca-deploy`) — ✅ revisão e preparação concluídas; ⚠️ deploy real pendente (depende das contas dos sócios)

**Parte A — revisão de segurança** (detalhes: `docs/architecture/08` §3.6)
- [x] Suíte completa executada (resultados no relatório da fase)
- [x] Autorização: 59 rotas classificadas por teste de política; IDOR, mass assignment, admin suspenso, CSRF para admin
- [x] Abusos re-executados (fichas, concorrência, webhooks, replay, preço, uploads maliciosos, path traversal, SSRF, rate limit, enumeração, força bruta)
- [x] **Corrigido (alta):** workers de motor tinham banco e todos os segredos → agora sem banco, sem segredos, rede só com Redis; resultado validado pelo worker `default`
- [x] **Corrigido (bloqueio):** `worker-download` não subiria em produção; e-mail só em console → SMTP real; produção recusa configuração insegura
- [x] Isolamento verificado de dentro dos 4 workers (sem Postgres/API/internet/metadata, sem segredos, sem root, sem capabilities, read-only) + limites de CPU/memória/PIDs
- [x] Varreduras: pip-audit, npm audit, Trivy (0 HIGH/CRITICAL corrigíveis nas imagens próprias após remover pip/npm), gitleaks no histórico (só falsos positivos revisados)
- [x] CSP no frontend, HSTS, docs da API desligadas em produção, erros genéricos, IPs mascarados nos logs
- [x] Modelo de ameaças atualizado com riscos residuais
- [x] **Corrigido (bloqueio):** o pacote `backend/app/storage/` nunca tinha sido versionado (regra `storage/` ampla no `.gitignore`); só o CI num clone limpo revelou — agora versionado e o CI roda a cada push
- [x] Imagens ARM64 (VM Oracle) construídas e com conversões/IA reais por emulação

**Parte B — deploy (preparado e testado localmente)**
- [x] `docker-compose.prod.yml` + `Caddyfile.prod` (HTTPS automático, HSTS, limites, logs com rotação, restart, recursos)
- [x] Stack de produção completo testado localmente com `APP_ENV=production` e HTTPS: páginas, headers, conversão real de visitante, download protegido, backup automático, isolamento
- [x] Backup diário criptografado (age) + **restauração testada** (26 tabelas, 0 divergências no livro-razão, contagens idênticas)
- [x] Monitoramento: `/healthz`, logs JSON, alertas por e-mail (disco, filas, falhas, erro 500, motor, livro-razão), saúde no admin
- [x] CI (GitHub Actions): testes backend/motores/frontend + gitleaks, pip-audit, npm audit, Trivy; rebuild semanal
- [x] Deploy com backup prévio e **rollback automático** (`scripts/deploy.sh`), preparação da VM (`scripts/vm-setup.sh`), runbook (`docs/OPERACAO.md`)
- [ ] **Conta Oracle + VM A1 em São Paulo** (sócios) → primeiro deploy real
- [ ] Subdomínio DuckDNS + certificado real (HTTP-01 NÃO VERIFICADO até o primeiro deploy)
- [ ] SMTP de produção (provedor e limites gratuitos a escolher pelos sócios)
- [ ] Isolamento e limites medidos **na VM real**
- [ ] Webhook do Mercado Pago na URL pública: pagamento de teste e depois pagamento real de valor mínimo combinado (depende das credenciais — Fase 4)
- [ ] Monitor externo de uptime (gratuito) apontando para `/healthz`
- [ ] Revisão jurídica das páginas legais antes de abrir ao público

