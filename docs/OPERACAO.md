# Operação em produção — runbook

> Fase 6 · 19/10/2026. Uma VM (Oracle Cloud Always Free, Ampere A1 ARM64, São Paulo), Docker Compose, Caddy com HTTPS automático.
> Comandos executados **na VM**, na pasta `/opt/baixeai`, salvo indicação. Abreviação usada abaixo:
>
> ```bash
> C="docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env"
> ```

## 1. Primeiro deploy

1. **Conta Oracle** (sócios): região de origem `sa-saopaulo-1` (não muda depois). Criar instância *Ampere A1* com Ubuntu 24.04, até 4 OCPU / 24 GB (limite Always Free conforme `02-hospedagem-e-custos.md`), chave SSH sua.
2. **Rede (console Oracle)**: na *Security List* da VCN, liberar entrada TCP 80 e 443 (e UDP 443). Só 22 já vem aberto.
3. **Subdomínio gratuito**: criar `algo.duckdns.org` em duckdns.org apontando para o IP público da VM. (`duckdns.org` está na Public Suffix List — consultada em 19/10/2026 — então cada subdomínio tem seus próprios limites no Let's Encrypt.) Emissão real do certificado por HTTP-01 nesse subdomínio: **NÃO VERIFICADO** até o primeiro deploy.
4. Na VM:
   ```bash
   sudo apt-get update && sudo apt-get install -y git
   sudo git clone https://github.com/brenoamoriim/baixeAI.git /opt/baixeai && sudo chown -R "$USER" /opt/baixeai
   cd /opt/baixeai && less scripts/vm-setup.sh      # leia antes de executar
   sudo bash scripts/vm-setup.sh
   # sair e entrar de novo (grupo docker), depois: cd /opt/baixeai
   cp .env.production.example .env && chmod 600 .env && nano .env      # preencher TUDO
   ```
5. **Chave de backup** (no computador de um sócio, nunca na VM): `age-keygen -o baixeai-backup.key` → guardar o arquivo no gerenciador de senhas; copiar só a linha `public key: age1...` para `BACKUP_AGE_RECIPIENT`.
6. Subir: `scripts/deploy.sh main` (constrói, faz backup, migra, sobe e confere `https://SEU-DOMINIO/healthz`).
7. Criar o admin: `$C exec api python -m app.cli create-admin --email SEU-EMAIL` (digita a senha sem eco).
8. Conferir o isolamento **na VM real** (ver §6) e fazer um teste de restauração (§4).

## 2. Atualizar (deploy) e reverter (rollback)

- Atualizar: crie uma tag no GitHub depois do CI verde (`git tag v1.2.0 && git push --tags`), e na VM: `scripts/deploy.sh v1.2.0`.
  O script: build → **backup** → migração → reinício → health check. Se o health check falhar, **volta sozinho** para a versão anterior.
- Reverter manualmente: `scripts/deploy.sh <tag-anterior>` (lista em `deploy-history.log`).
- Migrações precisam ser compatíveis com a versão anterior (expandir → migrar → contrair). Se uma migração destrutiva precisar ser desfeita: restaurar o backup feito pelo próprio deploy (§4).
- Fila durante o deploy: os workers usam `acks_late`; um job interrompido é reentregue e o resultado é aplicado uma única vez. Jobs que travarem são falhados e **a ficha é devolvida** pela varredura de jobs presos.

## 3. Rotacionar segredos

| Segredo | Como | Efeito |
|---|---|---|
| `SECRET_KEY` | trocar no `.env` → `$C up -d` | todos os usuários precisam entrar de novo |
| `SIGNED_URL_SECRET` | idem | links de download em aberto deixam de valer (15 min) |
| `GUEST_ID_HMAC_SECRET` | idem | visitantes ganham nova identidade anônima (custo: no máx. 1 ficha de visitante a mais por IP/dia) |
| `POSTGRES_PASSWORD` | `$C exec db psql -U baixeai -c "ALTER USER baixeai PASSWORD 'nova'"` → `.env` → `$C up -d` | — |
| `REDIS_PASSWORD` | `.env` → `$C up -d` (Redis e todos os workers reiniciam) | fila em memória é preservada (AOF) |
| `MP_ACCESS_TOKEN` / `MP_WEBHOOK_SECRET` | gerar no painel do Mercado Pago → `.env` → `$C up -d` | conferir um pagamento de teste |
| SMTP | gerar nova senha/API key no provedor → `.env` → `$C up -d` | — |
| Chave de backup (`age`) | nova chave → novo `BACKUP_AGE_RECIPIENT`; **guardar a antiga** enquanto existirem backups feitos com ela | — |

Depois de qualquer rotação: `$C ps` (todos `running`/`healthy`) e abrir o site.

## 4. Backups

- Automático: serviço `backup`, 1×/dia, `pg_dump` criptografado com `age` (a VM só tem a chave **pública**: consegue criar, não consegue ler). Mantém 14 dias no volume `backups`; cópia fora da VM se `BACKUP_RCLONE_REMOTE` estiver configurado (Cloudflare R2: 10 GB grátis — conferir limites atuais antes).
- Backup manual: `$C run --rm backup once`.
- **Teste de restauração (mensal e após mudança de schema)** — num computador com Docker e a chave privada:
  ```bash
  scripts/restore-test.sh baixeai-AAAAMMDDTHHMMSSZ.dump.age baixeai-backup.key
  ```
  Ele restaura num Postgres novo e isolado e confere tabelas, triggers append-only e a reconciliação do livro-razão de fichas. Executado com sucesso na Fase 6 (19/10/2026) com o banco de desenvolvimento: 26 tabelas, 0 divergências, contagens idênticas.
- Restaurar em produção (desastre): parar app (`$C stop api worker beat`), `pg_restore --clean` do dump descriptografado no `db`, `$C up -d`, rodar `$C exec worker celery -A app.workers.celery_app call maintenance.ledger_reconciliation`.
- Arquivos de usuários **não** têm backup (são temporários por desenho, apagados em poucas horas).

## 5. Monitoramento

- **Health**: `https://SEU-DOMINIO/healthz` (público, sem detalhes). Cadastrem um monitor externo gratuito (ex.: UptimeRobot — limites do plano grátis **NÃO VERIFICADO**) com alerta por e-mail: um servidor fora do ar não consegue avisar sozinho.
- **Alertas automáticos por e-mail** (`ALERT_EMAIL`, no máximo 1 por hora por tipo): disco ≥ 80%, fila ≥ 50 tarefas, ≥ 20 falhas de sistema/hora, erro 500 na API, falha inesperada de motor, divergência no livro-razão.
- **Admin → Visão geral**: disco, filas, falhas, pagamentos pendentes.
- **Recursos por contêiner** (CPU/RAM): `docker stats --no-stream` na VM. Limites: worker-light 3 GB/1,5 CPU, media 3 GB/2, ai 3 GB/2, download 1 GB/1, api 1 GB, db 2 GB.
- **Logs** (JSON, rotação 5×10 MB por contêiner): `$C logs --since 1h api worker`; IPs mascarados no Caddy.
- **Recuperação de instância ociosa da Oracle**: a Oracle pode recuperar VMs Always Free ociosas (CPU, rede e memória < 20% por 7 dias). Acompanhar uso de memória nas primeiras semanas (ver `10-deploy.md`).

## 6. Conferir o isolamento na VM

```bash
for w in worker-light worker-media worker-ai worker-download; do
  $C exec -T -e TESTS_NO_DB=1 $w python -m pytest tests/engines/test_engine_isolation.py -o addopts="" -p no:cacheprovider -q
done
$C exec -T -e TESTS_NO_DB=1 worker-download python -m pytest tests/engines/test_downloader.py -k "reach or egress or secrets" -o addopts="" -p no:cacheprovider -q
```
Na VM real isso confirma que nenhum worker de motor alcança Postgres, API, internet ou o metadata da Oracle (`169.254.169.254`). **Executar no primeiro deploy** (na Fase 6 foi executado apenas no Docker Desktop).

## 7. Atualizar o extrator de vídeos (yt-dlp)

Plataformas mudam com frequência; quando a taxa de sucesso cair (Admin → `download-stats`):
1. Ver a versão nova em https://github.com/yt-dlp/yt-dlp/releases (esperar ~2 semanas após o lançamento, salvo correção urgente).
2. Atualizar `yt-dlp[default,deno]==X` em `backend/requirements-download.txt` / `constraints.txt`.
3. Rodar os testes do baixador (README) e a verificação real (`app.tools.downloader.verify`).
4. Commit, CI verde, tag, `scripts/deploy.sh <tag>`.

## 8. Incidentes

| Situação | O que fazer |
|---|---|
| **Site fora do ar** | `$C ps` → `$C logs --tail 200 proxy api frontend` → `$C up -d`. Disco cheio? `df -h` e `docker system df` (limpar: `docker image prune -a` de imagens antigas). Se foi um deploy: `scripts/deploy.sh <tag-anterior>` |
| **Certificado HTTPS falhou** | `$C logs proxy`: porta 80 precisa estar aberta (Security List + iptables + ufw) e o DNS do DuckDNS apontar para o IP atual |
| **Fila parada** | Admin → filas. `$C restart worker-<fila>`. Jobs presos são falhados com devolução de ficha automaticamente |
| **Abuso / ataque** | rate limits já ativos; suspender contas no Admin; desligar uma ferramenta (Admin → Ferramentas); para DoS volumétrico: colocar o domínio atrás do Cloudflare (exige domínio próprio) |
| **Notificação de direitos autorais** | registrar, desativar o baixador se necessário (Admin → Ferramentas), responder pelo e-mail de suporte; seguir a orientação jurídica |
| **Suspeita de vazamento de segredo** | rotacionar **imediatamente** (§3), revisar Admin → Auditoria e `$C logs`, avaliar comunicação à ANPD/usuários (LGPD, prazo de comunicação: verificar com advogado) |
| **Pagamento aprovado sem fichas** | Admin → Pagamentos → "Reconciliar"; a reconciliação automática roda a cada 10 min |
| **Divergência no livro-razão** (alerta) | **não editar** o banco; investigar pelo Admin → Auditoria e corrigir com lançamento compensatório |
