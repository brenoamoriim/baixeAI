# BaixeAI — PRD (decisões de negócio)

Fonte da verdade das regras de negócio. Se algo aqui conflitar com outro documento, **este arquivo vence**. Itens marcados 🔶 são interpretações que precisam de confirmação dos sócios.

## 1. Produto
BaixeAI é uma plataforma web brasileira de utilitários online, modelo freemium, com 4 ferramentas:

| ID técnico | Nome na interface | Nome do pacote avulso |
|---|---|---|
| `video_downloader` | Baixador de vídeos | Baixador de vídeos |
| `converter` | Conversores (documento, imagem, áudio, vídeo) | Conversores |
| `background_remover` | Removedor de fundo | Removedor de fundo |
| `object_remover` | Remover objeto indesejado | Removedor de marca d'água |

Mercado: Brasil. Idioma da interface: pt-BR. Moeda: R$. Pagamento: Mercado Pago (conta de pessoa física já existente).

## 2. Moeda: a ficha
- Cada uso bem-sucedido de uma ferramenta consome fichas.
- 🔶 Custo padrão: **1 ficha por operação concluída**, em todas as ferramentas. O custo fica na tabela de configuração por ferramenta (alterável pelo admin), nunca fixo no código.
- Ficha reservada ao iniciar o trabalho, confirmada ao concluir com sucesso, devolvida se o processamento falhar por erro do sistema. Não devolve em cancelamento pelo usuário nem em arquivo/URL inválido, salvo se a validação ocorrer antes da reserva (então nem chega a cobrar).

## 3. Tipos de conta e planos

| Conta | Preço | Fichas | Uso |
|---|---|---|---|
| Visitante (sem cadastro) | grátis | **1 ficha, uma única vez** | qualquer ferramenta |
| Gratuita (cadastrada) | grátis | **5 fichas por dia** | qualquer ferramenta |
| Pro | R$ 24,90 / mês | **300 fichas por ciclo** | qualquer ferramenta |
| Premium | R$ 39,90 / mês | **800 fichas por ciclo** | qualquer ferramenta |
| Vitalícia | R$ 120,00 pagamento único | **sem contabilização de fichas** | todas as ferramentas, uso ilimitado* |

\* Ilimitado em fichas, mas sujeito a limites técnicos de uso justo (🔶 ver seção 8).

### Fichas avulsas (por ferramenta)
Pacote de **10 fichas**, válidas **somente na ferramenta comprada**:

| Ferramenta | Preço |
|---|---|
| Baixador de vídeos | R$ 9,90 |
| Conversores | R$ 4,90 |
| Removedor de marca d'água | R$ 4,90 |
| Removedor de fundo | R$ 4,90 |

Catálogo de pacotes e preços editável pelo admin (sem deploy).

## 4. Validade e consumo das fichas
- **Não acumulativas.** Fichas do plano são zeradas ao fim de cada ciclo (30 ou 31 dias conforme o mês). 🔶 Interpretação: o ciclo é ancorado na data de início/renovação da assinatura (ciclo de cobrança), não no mês-calendário. Renovou → saldo do plano volta ao total do plano; sobra não acumula.
- **Gratuita:** 5 fichas renovadas todos os dias às 00:00 (America/Sao_Paulo); sobra do dia não acumula.
- **Visitante:** 1 ficha total, nunca renova. Controle anti-abuso do lado do servidor (combinação de rate limit por IP e identificador anônimo), sem fingerprinting invasivo. Reconhecer na documentação que identidade anônima não é garantida entre dispositivos.
- **Avulsas:** expiram **90 dias** após a confirmação do pagamento, e valem só para a ferramenta comprada. 🔶 Interpretação: avulsas NÃO são zeradas no ciclo mensal do plano; seguem apenas a regra de 90 dias.
- **Vitalícia:** sem saldo de fichas.
- 🔶 **Ordem de consumo** (a que expira primeiro, gasta primeiro): fichas diárias gratuitas → fichas do plano → fichas avulsas da ferramenta. Cada débito do ledger registra a origem.
- Todo evento (concessão, reserva, consumo, devolução, expiração, estorno) vira linha no ledger append-only.

## 5. Pagamentos (Mercado Pago)
- Para **planos e fichas avulsas**: Pix, cartão de crédito e cartão de débito.
- Planos mensais com **recorrência também no Pix**. A Fase 1 deve verificar na documentação oficial atual do Mercado Pago o que é suportado (Pix recorrente/automático, débito recorrente, assinaturas por cartão) e se conta de pessoa física tem restrições. O que não for suportado deve ser documentado com a melhor alternativa (ex.: cobrança Pix a cada ciclo com lembrete).
- Vitalício: pagamento único (Pix ou cartão).
- Conta é pessoa física: registrar na Fase 1 limites/riscos (limites de recebimento, necessidade futura de CNPJ).
- Webhook verificado e idempotente. Crédito só após confirmação autoritativa. Estados tratados: pendente, aprovado, recusado, cancelado, expirado, estornado.
- 🔶 Troca de plano (Pro↔Premium): padrão sem pro-rata, vale a partir do próximo ciclo. Cancelamento: acesso até o fim do ciclo pago.

## 6. Ferramentas

### 6.1 Baixador de vídeos
- Caminho decidido: **o usuário cola uma URL de vídeo de qualquer plataforma** e o sistema tenta oferecer o download, independentemente de a plataforma ter API oficial. Sem lista fixa de plataformas; o motor de extração é o limite.
- Motor open source e gratuito (candidato: yt-dlp) atrás de um adaptador substituível. Extração real: nunca fabricar qualidade/arquivo.
- Escopo permitido: conteúdo **público** acessível sem login. Fora de escopo: DRM, conteúdo privado, paywall, login do usuário em redes sociais, receber senhas ou cookies de contas.
- Aviso obrigatório antes do download: o usuário declara ter direito de baixar o conteúdo e assume a responsabilidade pelo uso (registrar aceite).
- Fluxo: validar URL → identificar → consultar opções reais → mostrar custo → job assíncrono → progresso real → link temporário assinado.
- SSRF completo (ver CLAUDE.md).
- Riscos a documentar (sem esconder): termos das plataformas, bloqueio de IP de datacenter pelas plataformas, impacto potencial em AdSense/Mercado Pago/provedor de hospedagem, e que o motor quebra quando a plataforma muda.

### 6.2 Conversores — conjunto de LANÇAMENTO
Formatos irreais ou de cauda longa foram retirados. Só entra em "Available" o que for testado.

- **Documentos:** PDF, DOCX, DOC (entrada), ODT, RTF, TXT, HTML, XLSX, XLS (entrada), CSV. Combinações alvo: DOCX/DOC/ODT/RTF/TXT/HTML → PDF; PDF → DOCX/TXT (com aviso de limitação de layout); XLS/XLSX ↔ CSV; DOC → DOCX. Engine: LibreOffice headless e Pandoc.
- **Imagens:** JPG/JPEG, PNG, WEBP, AVIF, GIF, BMP, TIFF, ICO, HEIC/HEIF (entrada), SVG (entrada, sanitizado, rasteriza). Engine: libvips/Pillow (+ ImageMagick só se necessário).
- **Áudio:** MP3, WAV, OGG, M4A/AAC, FLAC, OPUS. Opções: bitrate, taxa de amostragem, canais. Engine: FFmpeg.
- **Vídeo:** MP4 (H.264/AAC), WEBM (VP9/Opus), MKV, MOV, AVI; extrair áudio; vídeo→GIF. Opções: resolução, qualidade/bitrate, fps. Engine: FFmpeg.
- **Retirados do escopo (não prometer):** DJVU, XPS, DBK, DOCM, DOTX/DOT, e a cauda longa de formatos legados de imagem (SGI, PCX, XWD, XPM, SIXEL, PICT, VIFF etc.) e de áudio (8SVX, CVSD, TXW, SMP, VOX, IRCAM etc.). Codecs (HEVC, XVID, DIVX, AV1) tratados como codecs, não como formatos; avaliar depois como `planned`.
- Limites iniciais sugeridos (configuráveis em `system_settings`): imagem 20 MB, documento 25 MB, áudio 50 MB, vídeo 200 MB e 10 min. 🔶 Revisar após medir desempenho na hospedagem gratuita.

### 6.3 Removedor de fundo
Upload, preview, PNG transparente, fundo de cor sólida opcional, antes/depois, download. Motor local gratuito (candidato: rembg com modelo de licença comercial verificada), atrás de um provedor abstrato. Modelo carregado uma vez por worker.

### 6.4 Remover objeto indesejado (pacote "Removedor de marca d'água")
Pincel/seleção de área + inpainting, preview, antes/depois, download. Motor local gratuito (candidato: LaMa ou equivalente, **licença a verificar**). Regras: usuário declara ter direito de editar a imagem; sem promessa de resultado perfeito; a comunicação do produto não incentiva burlar autoria, licença ou proveniência de terceiros. Tratar o recurso como remoção de elementos visuais indesejados em imagem do próprio usuário/autorizada.

## 7. Contas e autenticação
Cadastro, login, logout, verificação de e-mail, recuperação de senha, sessões, configurações, histórico de uso/processamento/compras, exclusão de conta e exportação de dados (LGPD). Argon2id.

## 8. Vitalício — uso justo (🔶 decisão dos sócios)
Sem fichas não significa sem limites técnicos. Padrão proposto: teto técnico por dia/concorrência (ex.: no máximo N jobs simultâneos e um teto diário alto, definidos em `system_settings`), os mesmos limites de tamanho dos outros planos, e cláusula de uso justo nos Termos. Definir o que "vitalício" significa (vida útil do produto) nos Termos.

## 9. Infraestrutura — restrição
**Orçamento zero**: apenas camadas gratuitas e open source. Todos os limites/preços de provedores devem ser verificados na Fase 1 com data e fonte. Domínio próprio provavelmente é o único custo praticamente inevitável (verificar). Ver `docs/CUSTOS-GRATIS-VS-PAGO.md`.

## 10. Fora do escopo do MVP
Processamento em lote, API pública, app mobile, outros idiomas, GPU, formatos da cauda longa, adaptadores específicos por plataforma de vídeo.

## 11. Decisões em aberto
1. Custo em fichas por ferramenta/tamanho (hoje: 1 ficha para tudo).
2. Interpretação do ciclo (ancorado na assinatura) e das avulsas (só 90 dias).
3. Ordem de consumo das fichas.
4. Uso justo do vitalício (limites concretos).
5. Troca de plano e pro-rata; política de reembolso em dias.
6. Nome final da ferramenta de objetos na interface e no pacote.
7. Suporte real do Mercado Pago a Pix recorrente para pessoa física.
8. Domínio e e-mail de suporte.
