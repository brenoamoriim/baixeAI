# Grátis vs. pago — o que esperar (orçamento zero)

> Este documento é um **ponto de partida qualitativo**. Nenhum preço ou limite abaixo foi verificado. A Fase 1 deve pesquisar a documentação oficial atual de cada provedor e substituir tudo marcado "NÃO VERIFICADO" por dados com fonte e data.

## Resumo honesto
Dá para lançar um MVP com custo zero **se** aceitarmos limites: máquina fraca, poucos usuários simultâneos, vídeo pesado lento, sem GPU. O que normalmente força a pagar primeiro é: **CPU/RAM para conversão de vídeo e IA**, **banda/armazenamento** dos arquivos e **domínio**. Não tenho como afirmar valores sem pesquisa — eles mudam.

## Por componente

| Componente | Opção gratuita (a verificar) | Quando passa a pagar | Observação |
|---|---|---|---|
| Hospedagem do app e workers | Camadas gratuitas de nuvem/PaaS, ou o próprio PC/servidor caseiro | CPU/RAM insuficientes, serviço "dorme" por inatividade, disco não persistente | Conversão de vídeo e IA são os maiores consumidores. Planos gratuitos costumam ter CPU/RAM muito baixos. NÃO VERIFICADO. |
| Banco PostgreSQL | Postgres no Docker Compose (grátis, na mesma máquina) ou camada gratuita de Postgres gerenciado | Backup automático, alta disponibilidade, volume de dados | Gerenciado dá backup pronto; auto-hospedado exige você configurar. NÃO VERIFICADO. |
| Redis | Redis em contêiner (grátis) ou camada gratuita gerenciada | Persistência, memória, alta disponibilidade | No MVP, contêiner basta. |
| Armazenamento de arquivos | Disco local com limpeza automática | Volume de arquivos e banda de saída | Arquivos são temporários, o que ajuda muito a manter grátis. S3-compatível com camada gratuita é opção futura. NÃO VERIFICADO. |
| E-mail transacional (verificação, recuperação) | Camadas gratuitas de serviços de e-mail | Volume de envio | Necessário para cadastro. NÃO VERIFICADO. |
| Domínio | — | Já no início | Provavelmente o único custo inevitável. NÃO VERIFICADO. |
| HTTPS / CDN / proteção | Certificado gratuito (ex.: Let's Encrypt) e CDN/proxy gratuito de provedores | Planos avançados de WAF/DDoS | NÃO VERIFICADO. |
| Monitoramento de erros | Camadas gratuitas ou logs próprios | Volume de eventos | NÃO VERIFICADO. |
| Mercado Pago | Sem mensalidade conhecida, mas **cobra taxa por transação** | Sempre que houver venda | A taxa reduz a margem: precisa entrar no modelo de custo. Taxa exata: NÃO VERIFICADO. |
| Remoção de fundo (IA) | Modelo open source rodando local em CPU (ex.: rembg) | GPU ou API paga se a latência/volume exigir | Em CPU funciona, porém mais lento. Verificar licença do modelo para uso comercial. |
| Remoção de objeto (IA) | Modelo open source local (ex.: LaMa) | Idem | Mais pesado que remoção de fundo. Verificar licença. |
| Download de vídeos | yt-dlp (open source) | Proxies/IPs residenciais se plataformas bloquearem o IP do servidor | **Risco real:** plataformas costumam bloquear IPs de datacenter. Sem proxy, a taxa de sucesso pode cair. |
| Conversão de documentos/imagens/áudio/vídeo | LibreOffice, Pandoc, libvips, FFmpeg (todos gratuitos) | CPU para vídeo | O custo é a máquina, não a licença. |
| AdSense | Gratuito para entrar | — | Aprovação não é garantida; conteúdo de download de vídeos é uma área sensível nas políticas. Verificar políticas atuais. |

## Pontos de decisão para a Fase 1
1. Onde rodar de graça de forma realista (nuvem gratuita vs. máquina própria) e o que isso limita.
2. Se vale começar **sem vídeo pesado** (por exemplo, limites baixos de tamanho/duração) para caber em hardware gratuito.
3. Margem real depois da taxa do Mercado Pago: Pro (R$ 24,90) e Premium (R$ 39,90) só fazem sentido se o custo por ficha ficar abaixo do que cada ficha rende.
4. Risco do plano vitalício (R$ 120) com custo recorrente de infraestrutura.
