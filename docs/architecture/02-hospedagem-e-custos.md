# 02 — Hospedagem e custos

> Fase 1 · todas as fontes acessadas em **17/10/2026**. Limites de camadas gratuitas mudam sem aviso: reconfirmar antes do deploy (Fase 6). O que não foi confirmado em fonte oficial está marcado **NÃO VERIFICADO**.

## 1. Comparação de hospedagem

### (A) VPS gratuita com Docker — Oracle Cloud Always Free
Fonte: [docs Oracle – Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

| Item | Valor verificado |
|---|---|
| CPU/RAM | Ampere A1 (ARM64): **2 OCPU + 12 GB** no total (1.500 OCPU-h e 9.000 GB-h/mês); ou até 2× AMD E2.1.Micro (1/8 OCPU, 1 GB, 50 Mbps) |
| Disco | **200 GB** de block volume (boot + dados), 5 backups de volume |
| Object storage | 20 GB (após o trial) |
| Banda de saída | **10 TB/mês** |
| Suspensão | Não "dorme", mas instância pode ser **recuperada se ociosa** 7 dias (CPU p95, rede e memória < 20%) |
| Workers longos | Sim (VM completa) |
| Backup | 5 backups de volume; backup lógico do Postgres por nossa conta |
| Ressalvas | Capacidade A1 na região escolhida não garantida (**NÃO VERIFICADO** para São Paulo); conta exige cartão para verificação; ARM64 exige imagens multi-arch |

Outras VMs gratuitas verificadas: Google Cloud `e2-micro` (só regiões dos EUA, 30 GB de disco, **1 GB de saída/mês**) — [docs Google](https://docs.cloud.google.com/free/docs/free-cloud-features). Inviável (RAM de micro e 1 GB de banda).

### (B) PaaS com camada gratuita

| Provedor | Situação verificada | Viável? |
|---|---|---|
| Render | Web service dorme após 15 min sem tráfego (~1 min para acordar); 750 h/mês; sistema de arquivos perdido no restart; **background workers não têm plano grátis**; Postgres grátis 1 GB e **apagado após 30 dias + 14 de carência**; Key Value só em memória — [render.com/docs/free](https://render.com/docs/free) | Não (sem workers, banco expira) |
| Hugging Face Spaces | CPU Basic 2 vCPU/16 GB grátis, disco não persistente, dorme sem uso; **Spaces Docker/Gradio exigem plano pago (PRO)** para criar — [docs HF](https://huggingface.co/docs/hub/spaces-overview) | Não |
| Fly.io | Sem camada gratuita permanente para contas novas (fontes de terceiros 2026; **NÃO VERIFICADO** na página oficial) | Não |
| Koyeb | Camada gratuita fechada para novos usuários desde fev/2026 segundo terceiros (**NÃO VERIFICADO** oficialmente); instância grátis não roda workers | Não |
| Railway | Crédito de teste; depois US$ 1/mês de crédito, 0,5 GB RAM (terceiros, **NÃO VERIFICADO**) | Não |
| Neon (Postgres) | 1 GB/projeto, 100 CU-h/projeto, *scale to zero* após 5 min, PITR 6 h — [neon.com/pricing](https://neon.com/pricing) | Só como banco; não resolve workers |

### (C) Híbrido
Exemplo: frontend em PaaS estático + API/workers numa VM. Ganho pequeno (o frontend Next.js é leve) e mais pontos de falha. Outra variante — workers numa máquina própria em casa — dá IP residencial (melhor para o yt-dlp), mas expõe a rede doméstica, depende de energia/internet residencial e da máquina pessoal ligada 24 h.

### Recomendação
**(A) Oracle Always Free (A1 2 OCPU / 12 GB)** com tudo em Docker Compose + **Cloudflare Free** (DNS, proxy, TLS na borda) + **R2** para backups criptografados + **Resend** para e-mail. É a única opção verificada com CPU/RAM/disco/banda suficientes e workers longos sem custo. Plano B se a Oracle negar capacidade ou recuperar a VM: uma máquina própria com Cloudflare Tunnel (Tunnel gratuito: **NÃO VERIFICADO** nesta fase) até migrar para uma VPS paga (preços **não pesquisados** nesta fase).

## 2. Grátis vs. pago — versão verificada (substitui `docs/CUSTOS-GRATIS-VS-PAGO.md`)

| Componente | Opção gratuita | Limite verificado | Quando passa a pagar |
|---|---|---|---|
| App + workers | Oracle A1 | 2 OCPU, 12 GB, 200 GB, 10 TB/mês | Volume de vídeo/IA acima da CPU (ver §3) |
| PostgreSQL | No Compose (mesma VM) | limitado pelo disco/RAM da VM | — |
| Redis | No Compose | idem | — |
| Arquivos | Disco local + limpeza (retenção de horas) | 200 GB total da VM | — |
| Backup externo | Cloudflare R2 | 10 GB-mês, 1 M ops classe A, 10 M classe B, **saída grátis** — [docs R2](https://developers.cloudflare.com/r2/pricing/) | > 10 GB de dumps |
| E-mail transacional | Resend Free | **3.000/mês, 100/dia**, 3 domínios — [resend.com/pricing](https://resend.com/pricing) | > 100 cadastros/recuperações por dia |
| E-mail (alternativa) | Brevo Free | 300/dia (só fontes de terceiros — **NÃO VERIFICADO**) | — |
| Domínio | — | **R$ 40/ano** `.com.br` (Registro.br, valor citado em fontes de 2026; conferir no site) | Desde o início — **único custo inevitável** |
| HTTPS/CDN/proxy | Cloudflare Free + Let's Encrypt | **corpo de requisição ≤ 100 MB** no plano Free — [docs Cloudflare](https://developers.cloudflare.com/workers/platform/limits/) | Uploads > 100 MB (Business: 200 MB) |
| Monitoramento de erros | Sentry Developer | 5 mil erros, 1 usuário, 30 dias — [sentry.io/pricing](https://sentry.io/pricing/) | — |
| Mercado Pago | Sem mensalidade | Pix 0,99%; crédito 3,98–4,98% (ver `06`) | Toda venda |
| IA (fundo/objeto) | Modelos locais em CPU (ONNX) | licenças em `07` | GPU se a latência exigir |
| Download de vídeos | yt-dlp | — | Proxies se plataformas bloquearem IP de datacenter (custo **NÃO VERIFICADO**) |
| AdSense | Gratuito | Política proíbe sites que permitem download não autorizado de conteúdo protegido (ver `12`) | — |

## 3. Modelo de capacidade (hipóteses explícitas)

O custo em R$ da infraestrutura é **zero** até o limite da VM; o limite real é **CPU**. Tempos por operação ainda **não foram medidos** — são hipóteses a validar na Fase 3 na VM real:

| Hipótese | Tipo de operação | Custo estimado (core-segundos/op) |
|---|---|---|
| H1 | Imagem / documento pequeno | 3 |
| H2 | Áudio | 5 |
| H3 | Vídeo (média de vídeos curtos, H.264 `veryfast`) | 120 |
| H4 | IA (fundo ~ 1 MP / inpainting 512 px) | 8 |
| H5 | Download + remux | 20 |
| H6 | Mix: 50% H1, 15% H2, 15% H3, 10% H4, 10% H5 → **≈ 23 core-s/op** | |
| H7 | 1 dos 2 cores reservado para web/API/banco → **86.400 core-s/dia** para workers | |

Capacidade teórica ≈ 86.400 / 23 ≈ **3.700 ops/dia** com 100% de uso contínuo; com picos concentrados (uso real em horário comercial/noite), estimativa prática **1.500–2.000 ops/dia**. **Vídeo responde por ~78% do custo** do mix.

| Nível | Hipótese de tráfego | Ops/dia | Cabe na Oracle Free? |
|---|---|---|---|
| 1 | 100 usuários ativos/dia, 3 ops cada | 300 | Sim, com folga |
| 2 | 1.000 usuários/dia, 3 ops | 3.000 | No limite; filas longas em pico; reduzir vídeo |
| 3 | 10.000 usuários/dia, 3 ops | 30.000 | Não — exige máquina paga ou vários workers |

Banda: 3.000 ops/dia × 10 MB médio de saída ≈ 900 GB/mês — dentro dos 10 TB.

## 4. Margem após taxas do Mercado Pago

Taxas: [página oficial de checkout](https://www.mercadopago.com.br/ferramentas-para-vender/check-out), 17/10/2026. **Não inclui impostos** (IR/carnê-leão ou DAS do MEI — **NÃO VERIFICADO**, consultar contador).

| Produto | Preço | Líquido Pix (0,99%) | Líquido crédito na hora (4,98%) | Líquido crédito 30 d (3,98%) | Receita por ficha (crédito na hora) |
|---|---|---|---|---|---|
| Pro (300 fichas) | R$ 24,90 | R$ 24,65 | R$ 23,66 | R$ 23,91 | R$ 0,079 |
| Premium (800) | R$ 39,90 | R$ 39,50 | R$ 37,91 | R$ 38,31 | R$ 0,047 |
| Vitalício | R$ 120,00 | R$ 118,81 | R$ 114,02 | R$ 115,22 | — (sem fichas) |
| Avulso Baixador (10) | R$ 9,90 | R$ 9,80 | R$ 9,41 | R$ 9,51 | R$ 0,94 |
| Avulso Conversores / Fundo / Objeto (10) | R$ 4,90 | R$ 4,85 | R$ 4,66 | R$ 4,70 | R$ 0,47 |

Leitura:
- Na camada gratuita o custo marginal por ficha é R$ 0 — a margem é quase toda receita. O problema não é dinheiro, é **capacidade**: um Premium que usa 800 fichas de vídeo consome ~96.000 core-s — **mais que um dia inteiro de toda a capacidade de workers** (H7).
- Como hoje 1 ficha = 1 operação qualquer, uma ficha de vídeo custa ~40× uma de imagem. Recomendação em `12`: custo em fichas por ferramenta/tamanho, ou limites de vídeo mais baixos.
- **Vitalício** (R$ 114–119 líquido, uma vez): com teto de 100 ops/dia no mix H6, um único usuário vitalício pode usar ~2.300 core-s/dia (~2,7% da capacidade). **~37 vitalícios intensos saturam a máquina** sem nenhuma receita recorrente (com teto de 50/dia: ~74). Recomendação em `12` (D4).

## 5. Limites reais para vídeo e IA (a medir)

| Limite | Valor proposto no PRD | Restrição verificada | Proposta para o lançamento |
|---|---|---|---|
| Upload de vídeo | 200 MB / 10 min | Cloudflare Free: corpo ≤ 100 MB | **95 MB / 10 min** (ou upload fora do proxy — ver `12`) |
| Upload de áudio | 50 MB | — | 50 MB |
| Imagem | 20 MB | — | 20 MB + teto de 40 MP decodificados |
| IA | — | CPU apenas | entrada redimensionada a ≤ 2 MP (fundo) / ≤ 1 MP na região de inpainting; 1 job de IA por vez |
| Concorrência | — | 2 OCPU | `worker-media` 1 processo, `worker-ai` 1, `worker-light` 2, `worker-download` 2 (I/O) |

## 6. Medições reais (Fase 3A, 18/10/2026)

Máquina: **Intel Core i5-8265U (8 threads), Docker Desktop/WSL2, x86_64** — máquina de desenvolvimento, **não** a VM Oracle ARM (medir lá na Fase 6). Motores limitados a 2 threads (FFmpeg) ou 1 (libvips). Dados brutos: `measurements/phase-3a-converters.json` (`python -m app.tools.converter.benchmark`).

| Caso | Entrada | Tempo | Pico de memória do motor |
|---|---|---|---|
| DOCX → PDF (~15 páginas) | 10 KB | 1,9 s | 218 MB |
| PDF → DOCX (mesmo doc) | 150 KB | 9,1 s | 258 MB |
| XLSX → CSV (50 mil linhas) | 1 MB | 1,7 s | 218 MB |
| JPG 12 MP → WEBP | 6,6 MB | 2,5 s | 211 MB |
| JPG 12 MP → AVIF (effort=2) | 6,6 MB | 7,8 s | 288 MB |
| JPG 12 MP → PNG | 6,6 MB | 3,9 s | 49 MB |
| WAV 5 min → MP3 | 50 MB | 4,3 s | 58 MB |
| MP4 720p 60 s → MP4 480p | 20 MB | 9,2 s | 178 MB |
| MOV 720p 60 s → MP4 (H.264) | 20 MB | 12,8 s | 274 MB |
| MP4 720p 60 s → WEBM (VP9 realtime) | 20 MB | 16,9 s | 286 MB |
| MP4 720p 60 s → MP3 (extrair áudio) | 20 MB | 0,8 s | 59 MB |
| MP4 720p 60 s → GIF (15 s) | 20 MB | 8,2 s | 436 MB |

Revisão das hipóteses do §3:
| Hipótese | Antes | Medido (dev) |
|---|---|---|
| H1 imagem/documento | 3 core-s | 2–8 core-s (AVIF e PDF→DOCX no topo) |
| H2 áudio | 5 core-s | ~4–5 s para 5 min de áudio |
| H3 vídeo | 120 core-s por vídeo curto | **~26 core-s por minuto de 720p** (13 s × 2 threads); vídeo de 10 min ≈ 130 s de relógio (~260 core-s) |

Leitura: com vídeos de 1–2 min, o custo real fica abaixo da H3; com vídeos de 10 min em 720p, fica ~2× acima. A recomendação de **2 fichas para vídeo (D1)** se mantém. Memória: nenhum caso passou de ~450 MB por motor, o que cabe com folga nos 12 GB da Oracle. ARM pode ser mais lento por núcleo: **NÃO VERIFICADO** até a Fase 6.

## 7. Medições de IA (Fase 3B, 18/10/2026)

Mesma máquina de dev (i5-8265U, Docker Desktop), ONNX Runtime CPU com 2 threads. Dados: `measurements/phase-3b-ai.json` (`python -m app.tools.ai.benchmark`).

| Caso | Carga do modelo (1×/worker) | Tempo por imagem | Pico de memória do processo |
|---|---|---|---|
| Fundo, 1 MP | 1,6 s | 3,4 s | 1,57 GB |
| Fundo, 12 MP | 1,1 s | 3,7–4,0 s | 1,71 GB |
| Objeto, 1 MP (máscara 120 px) | 16,4 s | 6,0–6,2 s | 1,00 GB |
| Objeto, 12 MP (máscara 900 px) | 16,3 s | 6,0–7,0 s | 1,18 GB |
| **Os dois modelos no mesmo processo, 12 MP** | — | — | **2,32 GB** |

Decisões derivadas da medição:
- `worker-ai` com **concorrência 1** e `mem_limit: 3g` (dois jobs simultâneos precisariam de ~4,6 GB).
- Tempo por imagem quase independente da resolução (o fundo roda em 1024 px; o inpainting em recorte de 512 px).
- Capacidade aproximada de 1 worker: ~900 remoções de fundo/hora ou ~550 remoções de objeto/hora na máquina de dev. Na Oracle ARM: **NÃO VERIFICADO** (medir na Fase 6).
- Hipótese H4 (8 core-s por operação de IA) ficou próxima: ~7 core-s (fundo) e ~12 core-s (objeto).
