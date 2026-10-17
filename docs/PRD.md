# BaixeAI — PRD (decisões de negócio)

Fonte da verdade das regras de negócio. Se algo aqui conflitar com outro documento, **este arquivo vence**. Itens marcados 🔶 são interpretações que precisam de confirmação dos sócios. Itens marcados ✅ foram decididos pelos sócios em 17/10/2026 (código da decisão entre parênteses, ver `docs/architecture/12-riscos-e-decisoes-abertas.md`).

## 1. Produto
BaixeAI é uma plataforma web brasileira de utilitários online, modelo freemium, com 4 ferramentas:

| ID técnico | Nome na interface | Nome do pacote avulso |
|---|---|---|
| `video_downloader` | Baixador de vídeos | Baixador de vídeos |
| `converter` | Conversores (documento, imagem, áudio, vídeo) | Conversores |
| `background_remover` | Removedor de fundo | Removedor de fundo |
| `object_remover` | Removedor de objetos | Removedor de objetos |

✅ (D6) Nome "Removedor de objetos" na interface e no pacote (substitui "Removedor de marca d'água").

Mercado: Brasil. Idioma da interface: pt-BR. Moeda: R$. Pagamento: Mercado Pago (conta de pessoa física já existente; ✅ (D15) CNPJ será aberto depois).

## 2. Moeda: a ficha
- Cada uso bem-sucedido de uma ferramenta consome fichas.
- ✅ (D1) Custo padrão: **1 ficha por operação**, com exceções configuráveis: **2 fichas** para conversão de vídeo (categoria vídeo dos Conversores) e para download de vídeo com duração **acima de 2 minutos**. Os custos ficam em tabela de configuração (alterável pelo admin), nunca fixos no código.
- Ficha reservada ao iniciar o trabalho, confirmada ao concluir com sucesso, devolvida se o processamento falhar por erro do sistema ou por **timeout** (✅ D11). Não devolve em arquivo/URL inválido, salvo se a validação ocorrer antes da reserva (então nem chega a cobrar).
- ✅ (D12) **Não existe cancelamento de job pelo usuário**: iniciou a ação, a ficha é consumida (salvo falha do sistema/timeout).

## 3. Tipos de conta e planos

| Conta | Preço | Fichas | Uso |
|---|---|---|---|
| Visitante (sem cadastro) | grátis | **1 ficha, uma única vez** | qualquer ferramenta |
| Gratuita (cadastrada) | grátis | **5 fichas por dia** | qualquer ferramenta |
| Pro | R$ 24,90 / mês | **300 fichas por ciclo** | qualquer ferramenta |
| Premium | R$ 39,90 / mês | **800 fichas por ciclo** | qualquer ferramenta |
| Vitalícia | R$ 120,00 pagamento único | **sem contabilização de fichas** | todas as ferramentas, uso ilimitado* |

\* Ilimitado em fichas, mas sujeito a limites técnicos de uso justo (ver seção 8).

✅ (D3b) Assinantes Pro/Premium **não** recebem as 5 fichas diárias; recebem só as do plano. Sem assinatura ativa, a conta volta a receber as diárias.

### Fichas avulsas (por ferramenta)
Pacote de **10 fichas**, válidas **somente na ferramenta comprada**:

| Ferramenta | Preço |
|---|---|
| Baixador de vídeos | R$ 9,90 |
| Conversores | R$ 4,90 |
| Removedor de objetos | R$ 4,90 |
| Removedor de fundo | R$ 4,90 |

Catálogo de pacotes e preços editável pelo admin (sem deploy).

## 4. Validade e consumo das fichas
- **Não acumulativas.** Fichas do plano são zeradas ao fim de cada ciclo. ✅ (D2) O ciclo é ancorado na data de início/renovação da assinatura: `fim = início + 1 mês de calendário` (ajustado ao último dia do mês quando necessário, ex.: 31/01 → 28 ou 29/02). Renovou → saldo do plano volta ao total do plano; sobra não acumula. **Única exceção:** troca de plano (ver §5).
- **Gratuita:** 5 fichas renovadas todos os dias às 00:00 (America/Sao_Paulo); sobra do dia não acumula.
- **Visitante:** 1 ficha total, nunca renova. Controle anti-abuso do lado do servidor (combinação de rate limit por IP e identificador anônimo), sem fingerprinting invasivo. Reconhecer na documentação que identidade anônima não é garantida entre dispositivos.
- **Avulsas:** expiram **90 dias** após a confirmação do pagamento, e valem só para a ferramenta comprada. ✅ (D2) Avulsas NÃO são zeradas no ciclo mensal do plano; seguem apenas a regra de 90 dias.
- **Vitalícia:** sem saldo de fichas.
- ✅ (D3) **Ordem de consumo:** fichas diárias gratuitas → fichas do plano → fichas avulsas da ferramenta (entre avulsas, a que vence primeiro). Como assinantes não têm diárias (D3b), na prática: conta gratuita = diárias → avulsas; assinante = plano → avulsas. Cada débito do ledger registra a origem.
- Todo evento (concessão, reserva, consumo, devolução, expiração, estorno) vira linha no ledger append-only.

## 5. Pagamentos (Mercado Pago)
- Para **planos e fichas avulsas**: Pix, cartão de crédito e cartão de débito.
- ✅ (D7) Recorrência: **cartão de crédito com cobrança automática**. Pix e débito: **renovação manual** a cada ciclo (pagamento avulso com lembrete por e-mail), porque o Pix Automático exige CNPJ (verificado na Fase 1). Ao abrir CNPJ, avaliar Pix Automático.
- Vitalício: pagamento único (Pix ou cartão).
- Conta é pessoa física: limites/riscos registrados em `docs/architecture/06-pagamentos-mercado-pago.md`.
- Webhook verificado e idempotente. Crédito só após confirmação autoritativa. Estados tratados: pendente, aprovado, recusado, cancelado, expirado, estornado.
- ✅ (D5) **Troca de plano** (Pro↔Premium): permitida, sem pro-rata, **vale a partir do próximo ciclo**. Na virada para o novo plano, as fichas do plano que sobraram do ciclo anterior **são somadas** às do novo plano (ex.: sobraram 120 do Pro → novo ciclo Premium com 800 + 120 = 920). As fichas somadas seguem a validade do novo ciclo.
- ✅ (D5) **Cancelamento:** acesso até o fim do ciclo pago.
- ✅ (D5) **Reembolso:** em até **7 dias** da compra, devolvendo o valor proporcional às fichas **não usadas** (aplica-se a planos e avulsas). Regra exata para o vitalício e texto final dos Termos: revisão jurídica (direito de arrependimento do CDC, art. 49).

## 6. Ferramentas

### 6.1 Baixador de vídeos
- Caminho decidido: **o usuário cola uma URL de vídeo de qualquer plataforma** e o sistema tenta oferecer o download, independentemente de a plataforma ter API oficial. Sem lista fixa de plataformas; o motor de extração é o limite.
- Motor open source e gratuito (candidato: yt-dlp) atrás de um adaptador substituível. Extração real: nunca fabricar qualidade/arquivo.
- Escopo permitido: conteúdo **público** acessível sem login. Fora de escopo: DRM, conteúdo privado, paywall, login do usuário em redes sociais, receber senhas ou cookies de contas.
- Aviso obrigatório antes do download: o usuário declara ter direito de baixar o conteúdo e assume a responsabilidade pelo uso (registrar aceite).
- Fluxo: validar URL → identificar → consultar opções reais → mostrar custo → job assíncrono → progresso real → link temporário assinado.
- SSRF completo (ver CLAUDE.md).
- Riscos a documentar (sem esconder): termos das plataformas, bloqueio de IP de datacenter pelas plataformas, impacto potencial em AdSense/Mercado Pago/provedor de hospedagem, e que o motor quebra quando a plataforma muda.
- ✅ (D13) **Sem anúncios (AdSense) nas páginas do baixador**; AdSense primeiro nas demais páginas.

### 6.2 Conversores — conjunto de LANÇAMENTO
Formatos irreais ou de cauda longa foram retirados. Só entra em "Available" o que for testado.

- **Documentos:** PDF, DOCX, DOC (entrada), ODT, RTF, TXT, HTML, XLSX, XLS (entrada), CSV. Combinações alvo: DOCX/DOC/ODT/RTF/TXT/HTML → PDF; PDF → DOCX/TXT (com aviso de limitação de layout); XLS/XLSX ↔ CSV; DOC → DOCX. Engine: LibreOffice headless e Pandoc. ✅ (D9) PDF → DOCX via **LibreOffice** (sem bibliotecas AGPL), com aviso claro de perda de layout; só fica `available` se o teste passar.
- **Imagens:** JPG/JPEG, PNG, WEBP, AVIF, GIF, BMP, TIFF, ICO, HEIC/HEIF (entrada), SVG (entrada, sanitizado, rasteriza). Engine: libvips/Pillow (+ ImageMagick só se necessário).
- **Áudio:** MP3, WAV, OGG, M4A/AAC, FLAC, OPUS. Opções: bitrate, taxa de amostragem, canais. Engine: FFmpeg.
- **Vídeo:** MP4 (H.264/AAC), WEBM (VP9/Opus), MKV, MOV, AVI; extrair áudio; vídeo→GIF. Opções: resolução, qualidade/bitrate, fps. Engine: FFmpeg.
- **Retirados do escopo (não prometer):** DJVU, XPS, DBK, DOCM, DOTX/DOT, e a cauda longa de formatos legados de imagem (SGI, PCX, XWD, XPM, SIXEL, PICT, VIFF etc.) e de áudio (8SVX, CVSD, TXW, SMP, VOX, IRCAM etc.). Codecs (HEVC, XVID, DIVX, AV1) tratados como codecs, não como formatos; avaliar depois como `planned`.
- Limites iniciais (configuráveis em `system_settings`): imagem 20 MB, documento 25 MB, áudio 50 MB, ✅ (D10) **vídeo 95 MB e 10 min** (limite de 100 MB por requisição do proxy gratuito da Cloudflare). 🔶 Revisar após medir desempenho na hospedagem gratuita.

### 6.3 Removedor de fundo
Upload, preview, PNG transparente, fundo de cor sólida opcional, antes/depois, download. Motor local gratuito (candidato: rembg com modelo de licença comercial verificada), atrás de um provedor abstrato. Modelo carregado uma vez por worker.

### 6.4 Removedor de objetos
Pincel/seleção de área + inpainting, preview, antes/depois, download. Motor local gratuito (candidato: LaMa ou equivalente, **licença a verificar**). Regras: usuário declara ter direito de editar a imagem; sem promessa de resultado perfeito; a comunicação do produto não incentiva burlar autoria, licença ou proveniência de terceiros. Tratar o recurso como remoção de elementos visuais indesejados em imagem do próprio usuário/autorizada.

## 7. Contas e autenticação
Cadastro, login, logout, verificação de e-mail, recuperação de senha, sessões, configurações, histórico de uso/processamento/compras, exclusão de conta e exportação de dados (LGPD). Argon2id.

## 8. Vitalício — uso justo
✅ (D4) Sem fichas não significa sem limites técnicos:
- No máximo **2 jobs simultâneos** e **50 operações por dia** (configuráveis em `system_settings`).
- Os mesmos limites de tamanho dos outros planos.
- Venda em **lote limitado** (quantidade definida pelos sócios antes do lançamento).
- Cláusula de uso justo nos Termos; os **limites de uso justo podem ser revisados a cada 6 meses**, com aviso prévio. O acesso continua vitalício (vida útil do produto, definida nos Termos).

## 9. Infraestrutura — restrição
**Orçamento zero**: apenas camadas gratuitas e open source. Ver `docs/architecture/02-hospedagem-e-custos.md`.
- ✅ (D14 / D8) Hospedagem: **tudo na Oracle Cloud Always Free (São Paulo)**, inclusive o ambiente de teste em produção. A Vercel gratuita foi descartada porque o plano Hobby proíbe uso comercial (pagamentos e anúncios), conforme verificado em 17/10/2026.
- ✅ (D8) Lançar primeiro com **subdomínio gratuito** para testes em produção; comprar o domínio próprio (`.com.br`, ~R$ 40/ano) antes de ir ao mercado.

## 10. Fora do escopo do MVP
Processamento em lote, API pública, app mobile, outros idiomas, GPU, formatos da cauda longa, adaptadores específicos por plataforma de vídeo, cancelamento de job pelo usuário.

## 11. Decisões em aberto
Todas as decisões originais (1–8) foram respondidas em 17/10/2026 (ver marcações ✅). Ainda em aberto:
1. Quantidade de vagas do lote do vitalício.
2. Provedor de subdomínio gratuito para a fase de testes (verificar na Fase 6).
3. E-mail de suporte (depende do domínio).
