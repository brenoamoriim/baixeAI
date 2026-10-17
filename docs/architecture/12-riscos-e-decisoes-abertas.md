# 12 — Riscos e decisões abertas

> Fase 1 · 17/10/2026. As decisões são **dos sócios**; aqui vai a recomendação técnica. Até a confirmação, a Fase 2 implementa os padrões recomendados como **configuração** (`system_settings`), para mudar sem reescrever código.

## 1. Riscos

| # | Risco | Tipo | Prob. | Impacto | Mitigação |
|---|---|---|---|---|---|
| R1 | **Baixador de vídeos × políticas**: o AdSense proíbe "sites… que permitem streaming, compartilhamento, cópia ou download não autorizados de conteúdo protegido por direitos autorais" ([política Google Ads](https://support.google.com/adspolicy/answer/6018015?hl=en), 17/10/2026); os Termos do YouTube proíbem baixar conteúdo sem autorização expressa ([youtube.com/terms](https://www.youtube.com/terms)) | Negócio/legal | Alta | Alta — reprovação/banimento no AdSense; possíveis notificações de plataformas | Separar a monetização por anúncios das páginas do baixador (sem AdSense nelas) ou não usar AdSense; aviso de direitos com aceite; sem DRM/login/privados; canal de remoção (contato para titulares) |
| R2 | **Mercado Pago × baixador**: o MP tem programa de proteção de marca para denúncias de titulares contra vendedores que usam o MP ([FAQ](https://www.mercadolivre.com.br/brandprotection/enforcement/faqs)). Termos exatos de atividades proibidas da conta MP: **NÃO VERIFICADO** | Negócio | Média | Alta — bloqueio de conta/saldo retido | Ler os termos da conta MP antes do lançamento; vender "fichas de utilitários", não "downloads de vídeos de terceiros"; ter plano B de pagamento |
| R3 | **Oracle**: política de uso aceitável sobre conteúdo infrator (página retornou 403; **NÃO VERIFICADO**); capacidade A1 indisponível; recuperação de VM ociosa | Técnico/negócio | Média | Alta — única máquina | Backup diário fora da Oracle; deploy reproduzível (Compose) para migrar em horas |
| R4 | **Plataformas bloqueiam IP de datacenter** (yt-dlp) e o motor quebra quando a plataforma muda | Técnico | Alta | Média — baixador falha | Atualizar yt-dlp com frequência; erro honesto ("não foi possível"), devolução quando for falha do sistema; não prometer plataformas |
| R5 | **Capacidade de CPU** (vídeo ≈ 78% do custo estimado; `02` §3) | Técnico | Alta com crescimento | Média | Limites de vídeo, fila com prioridade, custo em fichas por ferramenta |
| R6 | **Vitalício** sem receita recorrente: ~37 usuários intensos saturam a VM (`02` §4) | Negócio | Média | Alta | Teto de uso justo + limite de vagas/lote de lançamento |
| R7 | **Conta PF**: sem Pix Automático (exige CNPJ); risco fiscal; limites de recebimento **NÃO VERIFICADO** | Negócio/legal | Certa | Média | Renovação manual para Pix; abrir CNPJ antes de escalar; contador |
| R8 | **Remover objeto** usado para apagar marcas d'água de terceiros (o nome do pacote "Removedor de marca d'água" incentiva isso) | Legal/reputação | Alta | Média | Ver decisão D6; aceite de direitos; comunicação sem incentivar remoção de autoria |
| R9 | **AGPL** (PyMuPDF, via pdf2docx) em PDF → DOCX | Legal | Certa se usado | Média | Ver decisão D9 |
| R10 | **Patentes de codecs** (H.264/HEVC/AAC) em uso comercial | Legal | Baixa | Média | **NÃO VERIFICADO** — consulta jurídica antes de escalar; VP9/Opus/AV1 como alternativas |
| R11 | **Cloudflare Free 100 MB** por requisição × vídeo de 200 MB | Técnico | Certa | Baixa | Ver decisão D10 |
| R12 | **Dataset do LaMa** (Places2) com termos não verificados | Legal | Baixa | Baixa | Pesos publicados como Apache-2.0; registrar; trocar de modelo se surgir problema |
| R13 | LGPD: arquivos de usuários e dados de conta | Legal | Média | Alta | Retenção curta, exclusão/exportação de conta (Fase 5), política de privacidade revisada por advogado |
| R14 | Uma única máquina, sem alta disponibilidade | Técnico | Média | Alta | Backup + restauração testada + runbook de migração |

## 2. Decisões do PRD §11 — recomendações

| # | Decisão | Recomendação técnica |
|---|---|---|
| D1 | Custo em fichas por ferramenta/tamanho | Lançar com **1 ficha** para tudo (PRD), mas com `credit_cost` por ferramenta já no banco. Recomendo **2 fichas para vídeo > 2 min ou conversão de vídeo**, por causa da CPU (`02` §3). Decidir antes da Fase 3A |
| D2 | Ciclo ancorado na assinatura; avulsas só 90 dias | **Confirmar ambos** como estão no PRD. Ciclo = +1 mês de calendário com ajuste no fim do mês (`05` §1) |
| D3 | Ordem de consumo | Manter **diária → plano → avulsa** (PRD), com avulsas ordenadas por vencimento. Alternativa "puramente por vencimento" é mais justa em casos raros, mas mais difícil de explicar na UI |
| D3b | Assinantes também recebem as 5 diárias? | **Sim** (é o que a ordem de consumo do PRD implica) — confirmar |
| D4 | Uso justo do vitalício | `lifetime_max_concurrent_jobs = 2`, `lifetime_daily_cap = 50` (mais conservador que os 100 de `05`), mesmos limites de tamanho; **limitar a venda a um lote** (ex.: primeiras 50 vagas) e definir nos Termos "vida útil do produto" |
| D5 | Troca de plano / pro-rata / reembolso | Sem pro-rata, troca no próximo ciclo (PRD). Reembolso: **7 dias** de arrependimento (CDC art. 49 para compra fora do estabelecimento — **NÃO VERIFICADO** se aplica a fichas já consumidas; consultar advogado), devolvendo só fichas não usadas |
| D6 | Nome da ferramenta de objetos | Interface: **"Remover objeto"**. Pacote: trocar "Removedor de marca d'água" por **"Remover objeto"** — reduz R8 e risco em AdSense/MP |
| D7 | Pix recorrente para PF | **Não suportado** (Pix Automático exige CNPJ). Usar renovação manual (Pix/débito) + cartão automático (`06` §2) |
| D8 | Domínio e e-mail de suporte | Registrar `.com.br` (R$ 40/ano) e usar encaminhamento de e-mail gratuito (`11`) |

## 3. Novas decisões levantadas na Fase 1

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D9 | PDF → DOCX | (a) pdf2docx + PyMuPDF (AGPL): isolar num worker e publicar o código-fonte desse componente; (b) LibreOffice (qualidade ruim); (c) deixar `planned` no lançamento | **(c)** no lançamento; reavaliar (a) com orientação jurídica |
| D10 | Vídeo de 200 MB com Cloudflare Free (100 MB) | (a) limite 95 MB no lançamento; (b) subdomínio de upload sem proxy (expõe o IP da VM); (c) upload em partes (chunks < 100 MB) | **(a)** agora; **(c)** quando houver demanda |
| D11 | Devolução em timeout | Devolver ou não | **Devolver** (falha nossa em limite que nós definimos) |
| D12 | Cancelamento pelo usuário antes de o job começar | PRD: não devolve | Permitir cancelar **com devolução** enquanto `queued` (custo zero para nós); sem devolução depois de `processing` |
| D13 | AdSense | Usar em todo o site / só fora do baixador / não usar | Só em páginas sem baixador, ou adiar até ter tráfego e revisar a política |
| D14 | Hospedagem | Oracle Free / máquina própria | **Oracle Free (São Paulo)**; criar a conta já para garantir capacidade |
| D15 | CNPJ | PF agora / MEI já | PF no MVP; MEI antes de escalar (Pix Automático, fiscal) |
