# 08 — Segurança e modelo de ameaças

> Fase 1 · 17/10/2026. Defesa em profundidade. **Não existe segurança absoluta**: a seção 4 lista riscos residuais aceitos.

## 1. Ativos e atacantes

| Ativo | Por que importa |
|---|---|
| Saldo de fichas / planos | Valor monetário direto |
| Contas (e-mail, senha) | LGPD, sequestro de conta |
| Credenciais (MP, banco, e-mail) | Comprometimento total |
| Máquina gratuita (CPU/RAM/banda) | Único servidor; DoS derruba tudo |
| Rede interna (Postgres, Redis, metadata da nuvem) | Alvo de SSRF |
| Arquivos de usuários | Privacidade |

Atacantes: usuário abusivo (quer fichas grátis), bot (abuso do visitante, scraping), atacante oportunista (uploads maliciosos, SSRF), fraudador de pagamento (webhook falso, chargeback).

## 2. Ameaças e controles

| # | Ameaça | Controles |
|---|---|---|
| T1 | **SSRF** pelo baixador (URL → `169.254.169.254`, `localhost`, `10.x`, Redis) | Só `http/https`; portas 80/443; resolver DNS no servidor e **bloquear** loopback, privados (RFC 1918), CGNAT `100.64/10`, link-local, `0.0.0.0/8`, multicast, IPv6 ULA/link-local/mapeado; **fixar o IP resolvido** na conexão (anti DNS rebinding); validar **cada redirect** com a mesma regra; limite de redirects, timeout e tamanho. Como o yt-dlp faz suas próprias requisições, a camada de rede é a defesa principal: `worker-download` numa rede Docker própria, sem rota para a rede interna, com regras `DOCKER-USER` (iptables) bloqueando faixas privadas e o endpoint de metadata da nuvem |
| T2 | **Upload malicioso** (polyglot, extensão falsa, nome com `../`) | Validar assinatura real (magic bytes) contra a combinação pedida; nome gerado no servidor (UUID); original só como metadado sanitizado; limite de tamanho no Caddy **e** na API (streaming, aborta ao exceder) |
| T3 | **Exploração de motores** (FFmpeg, LibreOffice, libvips, librsvg, libheif) | Argumentos de template no servidor, `subprocess` **sem shell** (lista de argumentos), nunca entrada do usuário como opção (`-` inicial bloqueado, caminhos sempre gerados); contêiner não-root, `read_only` + `tmpfs` de trabalho, `cap_drop: ALL`, `no-new-privileges`, seccomp padrão, limites de CPU/memória/PIDs por contêiner; `timeout` + `prlimit` (CPU, memória, tamanho de arquivo) por processo; workers sem rede externa; imagens atualizadas (patches de segurança do Debian) |
| T4 | FFmpeg lendo recursos externos (playlists HLS/concat apontando para URLs/arquivos locais) | `-protocol_whitelist file,pipe` em conversões; demuxer forçado conforme formato detectado; sem `concat`/`hls` de entrada do usuário |
| T5 | LibreOffice: macros, links externos, OLE | Perfil isolado por job, macros desabilitadas (padrão headless sem execução), sem rede no worker; um processo por job, morto ao fim |
| T6 | SVG com XXE / referências externas / scripts | Rasterização em worker sem rede; sanitização (remover `<script>`, `foreignObject`, `href` externos) antes de rasterizar; saída sempre raster |
| T7 | **Bombas de descompressão** (imagem 50000×50000, DOCX/ZIP gigante, vídeo com resolução absurda) | Limite de pixels (Pillow `MAX_IMAGE_PIXELS`, checagem de dimensões via cabeçalho antes de decodificar com libvips); limite de tamanho descompactado e número de entradas de ZIP para OOXML/ODF; `ffprobe` antes de converter (duração, resolução, nº de streams) contra limites; `prlimit` de memória como última barreira |
| T8 | **Manipulação de fichas** (preço/saldo pelo cliente, corrida, replay) | Custo e saldo só no backend; lock por usuário + CHECKs + idempotência (`04` §4); ledger append-only com trigger; reconciliação diária |
| T9 | **Webhook falso / replay** | HMAC-SHA256 do MP com janela de `ts`; dedup por `x-request-id`; **sempre consulta a API do MP**; conferência de valor/moeda/`external_reference` |
| T10 | Redirect forjado do checkout ("paguei") | Redirect nunca concede (`06` §4) |
| T11 | **Abuso do visitante** | Cookie anônimo + limite por IP/dia + rate limit + Turnstile/CAPTCHA opcional (feature flag); custo de 1 operação aceito |
| T12 | **Abuso do vitalício** | Concorrência máxima, teto diário, limites de tamanho, cláusula de uso justo, suspensão manual pelo admin |
| T13 | **DoS** (jobs caros, flood de requests) | Cloudflare Free na frente; rate limit por IP/usuário em auth e endpoints caros; filas com concorrência fixa por worker (fila cresce, máquina não cai); limite de jobs pendentes por usuário; rejeição antecipada quando a fila passa de um limite |
| T14 | Credential stuffing / força bruta | Argon2id; rate limit por IP e por conta; atraso progressivo; mensagens genéricas; verificação de e-mail |
| T15 | Sequestro de sessão / CSRF / XSS | Cookies `HttpOnly; Secure; SameSite=Lax`; token CSRF (double submit) em mutações; CSP restritiva; React escapa por padrão; nada de HTML do usuário renderizado |
| T16 | Vazamento de arquivos de outros usuários | Links assinados (HMAC, expiração curta, vinculados ao job/dono); chaves de storage aleatórias; limpeza após `FILE_RETENTION_HOURS` |
| T17 | Vazamento de segredos | Só variáveis de ambiente; `.env` fora do Git; segredos distintos por finalidade; logs sem tokens/PII |
| T18 | Admin comprometido | Papel `admin` separado; ações de admin em `audit_events`; 2FA (TOTP) recomendado na Fase 5 |
| T19 | Redis exposto | Sem porta publicada; senha + ACLs (usuário do `worker-download` só acessa as chaves da sua fila) |
| T20 | Cadeia de dependências | Versões fixadas (lockfiles), `pip-audit`/`npm audit` no CI, imagens base oficiais |

## 3. Controles específicos por ferramenta

- **Baixador:** só conteúdo público; sem cookies/login; aceite de direitos registrado; limite de duração e tamanho consultados **antes** de baixar (metadados do yt-dlp) e reforçados durante (`--max-filesize`); saída recodificada/remuxada pelo FFmpeg em sandbox.
- **IA:** modelos embutidos na imagem (sem download em runtime); entrada redimensionada a um teto de pixels antes da inferência; um modelo carregado por processo.

## 3.1 Achados da Fase 2 (implementação)

| Achado | Situação |
|---|---|
| O proxy de rewrites do Next.js **não acrescenta** o IP ao `X-Forwarded-For`: só preenche se vier vazio (`??=` em `next/dist/server/base-server.js`). Um cliente que envie o cabeçalho poderia falsificar o IP visto pela API (rate limit e limite de visitante por IP) | Em dev aceitável. **Produção (Fase 6):** o Caddy na frente deve **sobrescrever** `X-Forwarded-For` com o IP real; `TRUSTED_PROXY_HOPS` ajustado e testado |
| O usuário do Postgres no Compose de dev é superusuário: poderia contornar o trigger append-only (`session_replication_role`) | Os testes usam isso só para limpar tabelas. **Produção:** a API conecta com papel **sem** superusuário, sem `UPDATE/DELETE` no ledger (Fase 6) |
| E-mail em modo `console` registra links com token no log | Só em dev; provedor real antes do deploy |
| `npm audit`: 5 "high" em dependências de **desenvolvimento** (`braces` via `eslint-config-next`); 0 em produção | A correção automática rebaixa o `eslint-config-next` para 14 (incompatível). Reavaliar a cada atualização do Next |
| Rate limit em Redis por janela fixa | Simples; permite rajada na virada da janela. Aceito no MVP |

## 3.2 Achados e controles da Fase 3A (conversores)

| Achado / controle | Situação |
|---|---|
| `X-Forwarded-For` falsificável via proxy do Next (achado da Fase 2) | **Resolvido no desenho:** Caddy na frente encaminha `/api/*` direto à API e substitui o cabeçalho enviado pelo cliente. Testado em dev (4 visitantes com XFF falso → o 4º recebe 429). As portas 3000/8000 publicadas só em `127.0.0.1` continuam aceitando XFF do cliente: **uso exclusivo de desenvolvimento** |
| Proxy do Next limita corpo a 10 MB e **bufferiza em memória** | Uploads não passam pelo Next (Caddy → API, gravação em disco em streaming). Limite 96 MB no Caddy + `Content-Length` checado na API antes de ler o corpo + contagem durante a cópia |
| libvips do Debian inclui ImageMagick (`vips-magick.so`) | `VIPS_BLOCK_UNTRUSTED=1` em toda chamada; teste automatizado comprova o bloqueio |
| SVG: XXE, scripts, referências externas | `defusedxml` (sem DTD/entidades), remoção de scripts/`foreignObject`/eventos/`href` externos/CSS; rasterização por `rsvg-convert` no sandbox, sem rede |
| Bomba de pixels | dimensões lidas só do cabeçalho na inspeção, antes de cobrar; limite 40 MP; Pillow com `MAX_IMAGE_PIXELS` |
| ZIP/OOXML bomba | limites de entradas, tamanho descompactado e razão de compressão na detecção |
| FFmpeg lendo arquivos locais via playlist/concat | demuxer forçado pelo formato detectado + `-protocol_whitelist file`; teste com playlist disfarçada |
| Macros (LibreOffice) | perfil por job com macros desativadas + worker sem rede. **Limitação do teste:** o controle com a proteção desligada também não executou a macro (o `--convert-to` headless parece não disparar o evento de abertura), então o teste é uma salvaguarda de regressão, não prova da configuração |
| Injeção em opções | listas fechadas validadas no backend antes de cobrar; argumentos montados no servidor; sem shell (teste) |
| Segredos no ambiente dos motores | o sandbox passa ambiente mínimo (teste). **Risco residual:** o processo do worker tem `DATABASE_URL`/`REDIS_URL` no próprio ambiente; um exploit no motor, rodando com o mesmo usuário, poderia ler `/proc/<pai>/environ`. Mitigação planejada (Fase 6): papel de banco com privilégio mínimo para os workers e/ou motor sob outro UID |
| Workers | rede `internal` (sem internet), rootfs só leitura, `/tmp` em tmpfs, `cap_drop: ALL`, `no-new-privileges`, limites de memória e PIDs; rlimits por processo |

## 3.3 Controles da Fase 3B (IA de imagem)

| Ameaça / controle | Situação |
|---|---|
| Download de modelo em runtime (cadeia de suprimento) | modelos baixados **só no build**, conferidos por SHA-256 (build falha se mudar); worker sem internet |
| Uso para remover marca d'água/autoria de terceiros (R8) | aceite obrigatório e registrado por job; texto do produto não incentiva; nome "Removedor de objetos" (D6). Risco residual: a declaração não impede o abuso |
| Máscara de outro usuário | máscara é upload com dono; 404 para dono diferente (teste) |
| Máscara maliciosa/enorme | passa pela mesma detecção e inspeção de imagem (limite de pixels) e precisa ter o tamanho da imagem |
| Privacidade | EXIF/GPS removidos da saída (teste); imagem processada localmente, sem terceiros |
| Esgotamento de memória | concorrência 1 + `mem_limit 3g`; falha do modelo → erro do sistema → ficha devolvida (teste) |

## 3.4 Controles da Fase 3C (baixador)

```
API (rede internal)  --valida URL (SSRF)-->  Redis  <--  worker-download (rede dlnet: só Redis + proxy)
                                                             |
                                                       egress-proxy (dlnet + egress)
                                                             | revalida CADA conexão, disca o IP validado
                                                          internet pública (80/443)
```

| Controle | Evidência |
|---|---|
| Validação na API: esquema http/https, sem credenciais, portas 80/443, DNS com **todos** os IPs públicos (bloqueia loopback, RFC1918, CGNAT, link-local/metadata, ULA, IPv4-mapeado, IP decimal) | `tests/unit/test_ssrf.py` (25 URLs hostis) |
| Proxy de egresso: revalida cada conexão (redirects, URLs de mídia/segmentos) e conecta no IP validado (anti DNS rebinding) | testes do proxy (rebinding simulado, redirect para IP privado) |
| `worker-download` sem rota para Postgres, sem internet direta, sem metadata, sem `DATABASE_URL`/segredos no ambiente | testes **de dentro do contêiner** (`tests/engines/test_downloader.py`) |
| yt-dlp: API Python (sem shell), sem cookies/netrc/config, sem playlists/ao vivo, limites de tamanho e duração, saída conferida pela assinatura real antes da entrega | testes com servidor local + verificação real |
| Aceite de direitos registrado na mesma transação da cobrança | teste de API |

Riscos residuais:
- `worker-download` alcança o **Redis** (necessário para a fila). Se um componente ignorasse o proxy e um conteúdo malicioso induzisse uma requisição ao Redis, ele ainda exigiria senha; o Redis também descarta comandos com cara de HTTP. Mitigação extra planejada (Fase 6): usuário ACL do Redis restrito às filas do download.
- O yt-dlp executa o JavaScript do player do YouTube no **deno** (yt-dlp-ejs) — código de terceiros, isolado pelo sandbox do deno e pelo contêiner sem rede direta.
- Dependência **mutagen (GPL-2.0+)** carregada pelo yt-dlp no processo: sem distribuição (SaaS), sem obrigação de publicar código; se as imagens forem distribuídas, rever.
- O proxy de egresso é código próprio (~150 linhas), não um proxy auditado; coberto por testes, sem auditoria externa.

## 3.5 Controles da Fase 4 (pagamentos)

| Ameaça | Controle | Evidência |
|---|---|---|
| Preço adulterado no navegador | o cliente só envia o código do produto; preço lido do banco e gravado no pagamento; campos extras ignorados | teste |
| Webhook falso / replay / troca de id | HMAC com segredo, janela de 300 s, manifesto inclui `data.id` e `x-request-id`; inválidos registrados e respondidos com 401 | testes |
| Concessão dupla | dedup do evento + lock de linha + `fulfilled_at` + UNIQUE em `provider_payment_id` e no bucket | teste com 5 processamentos simultâneos |
| "Paguei" pelo redirect | página de retorno só lê nosso estado; nunca concede | teste |
| Valor/moeda diferentes do esperado | sem concessão; `payment_mismatch` auditado | teste |
| Dados de cartão | nunca passam pelo nosso servidor (Checkout Pro e assinatura hospedados pelo MP) | desenho |
| Credenciais | só em variáveis de ambiente; `sandbox_check` recusa rodar em produção | — |
| Abuso de checkout | rate limit 10/10 min por usuário; e-mail verificado obrigatório | — |

Riscos residuais: a validação no sandbox real ainda não foi feita (sem credenciais); o comportamento exato de `init_point` em assinatura pendente e de `/authorized_payments` precisa ser confirmado; chargeback depois do consumo das fichas gera prejuízo (apenas auditado).

## 3.6 Revisão de segurança da Fase 6 (19/10/2026)

### Achados e correções

| # | Achado | Gravidade | Correção | Evidência |
|---|---|---|---|---|
| R1 | Workers de motor (LibreOffice, libvips, FFmpeg, ONNX) recebiam **todo** o ambiente do backend (`DATABASE_URL`, `SECRET_KEY`, `MP_ACCESS_TOKEN`) e estavam na rede do Postgres. Um exploit num motor poderia ler `/proc/1/environ` e alterar fichas no banco | **Alta** | Motores agora seguem o padrão do baixador: rede `enginenet` (só Redis), papel `PROCESS_ROLE=engine` sem segredos nem URL de banco; recebem os dados do job como argumentos e devolvem o resultado como tarefa ao worker `default`, que valida o resultado (chave de saída precisa ser `jobs/<id do job>/…`, classe de erro conhecida, formato conhecido) e aplica uma única vez | `tests/engines/test_engine_isolation.py` executado **dentro** dos 4 workers (dev e stack de produção); `test_security_review.py` (resultados forjados) |
| R2 | Em produção, o `worker-download` (sem segredos por desenho) **não subiria**: a validação exigia os 3 segredos em qualquer processo | Alta (bloqueio de deploy) | `PROCESS_ROLE=engine` dispensa os segredos e os deixa vazios; funções HMAC recusam chave vazia | `tests/unit/test_production_config.py` |
| R3 | Envio de e-mail só existia em modo console: em produção ninguém confirmaria o e-mail | Alta (bloqueio de lançamento) | Provedor SMTP (TLS verificado; STARTTLS ou SSL), envio pela fila com novas tentativas; produção **recusa subir** sem SMTP ou sem `COOKIE_SECURE=true` | testes unitários + stack de produção local (cadastro responde 202 com SMTP fora do ar; tarefa re-tentada) |
| R4 | Sem CSP no frontend | Média | CSP no build de produção do Next.js (sem `unsafe-eval`; `unsafe-inline` necessário para páginas pré-renderizadas) | E2E falha em qualquer violação de CSP; 14 páginas sem violação |
| R5 | `pip` 25.0.1 da imagem base (12 CVEs) e bibliotecas antigas vendorizadas pelo pip/npm (Trivy) | Média | Base fixada em `python:3.12.15-slim-trixie`; **pip e npm removidos das imagens finais** | Trivy: 0 HIGH/CRITICAL com correção disponível em todas as imagens próprias |
| R6 | Logs do Caddy gravariam IP completo (contradiz a política de privacidade) | Baixa (LGPD) | IPs mascarados (/16 IPv4, /32 IPv6) no log de acesso | `Caddyfile.prod` validado |
| R7 | Rotas novas poderiam nascer sem proteção | Processo | Teste de política: toda rota precisa estar classificada (pública / usuário ou visitante / usuário / admin) e a dependência de autorização é conferida | `test_every_route_is_classified_and_guarded_accordingly` (59 rotas) |

### Verificações sem achados

- Autorização: 59 rotas inventariadas a partir da própria aplicação; todas as `/admin/*` exigem papel admin; IDOR (upload, inspeção de link, job, download, pagamento) responde 404 igual a "não existe"; mass assignment no cadastro (`role`, `email_verified_at`) ignorado; admin suspenso perde acesso na hora; CSRF exigido também para admin.
- Abuso (já cobertos desde as fases 2–4 e re-executados): concorrência de fichas, corrida e replay de webhook, preço adulterado, uploads maliciosos (polyglots, bombas de pixels/ZIP, SVG com XXE/script, macros), nomes com path traversal, SSRF (25 URLs hostis + rebinding), rate limit, enumeração de e-mail, força bruta.
- Segredos: gitleaks no **histórico completo** (40 commits): 2 falsos positivos revisados (senha fixa dos testes e o título da API), registrados por impressão digital em `.gitleaksignore`; `.env` e `cookies.txt` ignorados e ausentes do histórico.
- Produção: docs/OpenAPI desligados, `/readyz` não exposto publicamente, mensagens de erro genéricas (detalhes de validação só fora de produção), HSTS, cookies `Secure`.
- Dependências: `pip-audit` sem achados nas dependências da aplicação; `npm audit --omit=dev` sem achados. `npm audit` completo aponta 5 HIGH em `eslint-config-next` (ferramenta de lint, só desenvolvimento; a "correção" sugerida é rebaixar para Next 14) — aceito.

## 4. Riscos residuais (aceitos e documentados)

1. **Zero-day** em FFmpeg/LibreOffice/libvips: mitigado por isolamento, não eliminado.
2. **Uma única máquina**: um DoS volumétrico acima do que o Cloudflare Free absorve derruba o serviço.
3. **Identidade do visitante** não é garantida entre dispositivos/IPs.
4. **yt-dlp acessa a internet**: a filtragem de rede depende de regras de firewall corretas no host; erro de configuração reabre o SSRF. Teste automatizado na Fase 3C e checagem no deploy (Fase 6).
5. **Chargebacks** podem ocorrer depois do consumo das fichas.
6. Sem auditoria externa de segurança (orçamento zero).
7. **Workers de motor ainda alcançam o Redis** (necessário para a fila). Um motor comprometido poderia enfileirar tarefas falsas (ex.: marcar um job em andamento como concluído ou falho). Impacto limitado: não cria fichas, não lê segredos, não alcança o banco; o resultado é validado. Correção completa (assinatura de mensagens do Celery ou ACL por fila) fica para depois do MVP.
8. **CVEs sem correção publicada no Debian** dentro das imagens dos motores (ex.: `libopenexr`, `libxml2`, FFmpeg): 119–208 HIGH/CRITICAL "unfixed" por imagem segundo o Trivy. Mitigado pelo isolamento (sem rede, sem banco, sem segredos, sem root, read-only, limites de recursos); reavaliar a cada rebuild semanal do CI.
9. **Caddy 2.11.7 e Postgres 17.11** (versões mais recentes publicadas em 19/10/2026) contêm Go stdlib com CVEs (no Postgres, só no `gosu`, usado na inicialização). Atualizar assim que houver nova versão — o Caddy fica exposto à internet.
10. **CSP com `unsafe-inline`** em scripts (exigência das páginas estáticas do Next.js). XSS continua mitigado pelo React (escape por padrão) e por não renderizarmos HTML de usuários.
11. **Sem 2FA para admin**. Mitigado por senha forte (Argon2id), reautenticação nas ações sensíveis, rate limit e auditoria.
12. Isolamento de rede verificado no Docker Desktop (Windows) e no stack de produção local; **na VM Oracle real ainda precisa ser executado** no primeiro deploy (`docs/OPERACAO.md` §6).
