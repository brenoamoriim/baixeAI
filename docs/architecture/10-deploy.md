# 10 — Plano de deploy (gratuito)

> Fase 1 · 17/10/2026. Executado na Fase 6. Base: Oracle Cloud Always Free (ver `02`).
>
> ✅ Decisão D8/D14: o teste em produção também roda na Oracle, com **subdomínio gratuito** até a compra do domínio. A Vercel Hobby foi descartada (proíbe uso comercial: pagamentos e anúncios — [fair use](https://vercel.com/docs/limits/fair-use-guidelines), 17/10/2026). Provedor de subdomínio gratuito e emissão de certificado sem domínio próprio: **NÃO VERIFICADO**, pesquisar na Fase 6. Com subdomínio de terceiros, o proxy da Cloudflare não se aplica até haver domínio próprio (limite de 100 MB deixa de existir, mas também a proteção DDoS).

## 1. Topologia

```
Internet → Cloudflare (DNS + proxy, Free) → VM Oracle Ampere A1 (ARM64, Ubuntu LTS)
             └─ Caddy :443 → frontend / api
                docker compose: db, redis, api, frontend, beat, worker-light, worker-media, worker-ai, worker-download
```

- **Região:** escolher `sa-saopaulo-1` como *home region* no cadastro (latência para o Brasil). A região de origem **não pode ser trocada** depois e os recursos Always Free só valem nela. Disponibilidade de capacidade A1 em São Paulo: **NÃO VERIFICADO** (relatos de "out of capacity" são comuns; tentar em horários diferentes).
- **Arquitetura ARM64:** imagens multi-arch obrigatórias. Verificado em 17/10/2026 (emulação): em `python:3.12-slim` (Debian 13) arm64, FFmpeg e libvips instalam e convertem; LibreOffice e Pandoc **não testados** em arm64 (ver `07` §2.1). Wheels de `onnxruntime` para Linux aarch64: **NÃO VERIFICADO** nesta fase (checar na Fase 3B).
- **Recuperação de instância ociosa:** a Oracle pode recuperar instâncias Always Free se, em 7 dias, CPU p95 **e** rede **e** memória (A1) ficarem abaixo de 20% ([docs Oracle](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), 17/10/2026). Hipótese: com Postgres + modelos de IA carregados, a memória fica acima de 20% de 12 GB (2,4 GB). Medir na Fase 6. Converter a conta para *Pay As You Go* (exige cartão; sem cobrança dentro dos limites gratuitos) é citado como forma de evitar a recuperação, mas **NÃO VERIFICADO** em documentação atual.

## 2. HTTPS

- Cloudflare em modo **Full (strict)**; Caddy emite certificado Let's Encrypt (ou certificado de origem da Cloudflare).
- HSTS, CSP, `X-Content-Type-Options`, `Referrer-Policy` no Caddy.
- Firewall da VM (Security List da Oracle + `ufw`): só 80/443 abertos; 443 idealmente restrito aos IPs da Cloudflare; SSH só por chave, porta não padrão opcional, `fail2ban`.
- **Limite de upload:** o proxy da Cloudflare Free aceita corpo de até **100 MB** ([docs Cloudflare](https://developers.cloudflare.com/workers/platform/limits/), 17/10/2026). Vídeo de 200 MB (PRD §6.2) não passa pelo proxy. Opções em `12` (recomendado: limite de vídeo 95 MB no lançamento).

## 3. Segredos

- `.env` só na VM (`chmod 600`, dono root), nunca no Git; `.env.example` documenta as chaves.
- Segredos distintos por finalidade (sessão, links assinados, HMAC de visitante, webhook).
- Rotação documentada: trocar no `.env` + `docker compose up -d` (sessões são invalidadas ao trocar `SECRET_KEY`).

## 4. Backup

| O quê | Como | Frequência | Retenção |
|---|---|---|---|
| Postgres | `pg_dump -Fc` → criptografado (`age` ou `gpg` com passphrase do `.env`) → **Cloudflare R2** (10 GB-mês grátis, saída grátis) | diário | 14 diários + 8 semanais |
| `.env` | cópia criptografada fora da VM, guardada pelos sócios (gerenciador de senhas) | a cada mudança | — |
| Arquivos de usuário | **não** fazem backup (temporários por design) | — | — |
| Volume de boot | 1 backup de volume Always Free (limite de 5) | semanal | 1–2 |

Teste de restauração mensal (restaurar dump num Postgres local e rodar a reconciliação do ledger). Backup sem teste de restauração não conta.

## 5. Monitoramento

- `/healthz` (processo vivo) e `/readyz` (banco + Redis) na API.
- Monitor externo gratuito de uptime (ex.: UptimeRobot; limites do plano **NÃO VERIFICADO**).
- Erros: Sentry Developer (gratuito: 5 mil erros, 1 usuário, 30 dias — [sentry.io/pricing](https://sentry.io/pricing/), 17/10/2026) ou só logs estruturados se preferir não enviar dados a terceiros.
- Métricas mínimas no admin: tamanho das filas, jobs falhos por classe, disco livre, divergências de ledger, pagamentos pendentes.
- Alerta de disco > 80% (o `storage` temporário é o maior risco de encher).

## 6. Deploy e rollback

1. CI (GitHub Actions, gratuito para repositório público; minutos para privado **NÃO VERIFICADO**) constrói imagens multi-arch e publica no GitHub Container Registry com tag = SHA do commit.
2. Na VM: `docker compose pull && docker compose up -d` com a nova tag.
3. Migrações: `alembic upgrade head` roda **antes** de trocar a API; migrações devem ser compatíveis com a versão anterior (expandir → migrar → contrair).
4. **Rollback:** voltar a tag anterior no `.env` (`APP_VERSION`) e `up -d`. Migração destrutiva só com backup do mesmo dia.
5. Janela de manutenção: workers drenam a fila (`celery control shutdown` com `acks_late`) antes de reiniciar.

## 7. Checklist de go-live (Fase 6)

- [ ] SSRF testado em produção (worker-download não alcança `169.254.169.254`, IPs privados, Postgres, Redis)
- [ ] Webhook do MP em produção com assinatura validada
- [ ] Restauração de backup testada
- [ ] Limites de tamanho medidos na VM real
- [ ] Termos, Privacidade e aviso de direitos publicados
