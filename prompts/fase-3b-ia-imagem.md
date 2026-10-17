# FASE 3B — Ferramentas de imagem com IA: Removedor de fundo e Remover objeto indesejado

Leia `CLAUDE.md`, `docs/PRD.md` (seções 6.3 e 6.4), `docs/CHECKLIST.md` e `docs/architecture/02-hospedagem-e-custos.md`. Crie a branch `phase-3b-ia-imagem`.

## Objetivo
Entregar duas ferramentas funcionando, com motores gratuitos e locais, atrás de uma abstração de provedor.

## Escopo
### Comum
- Interface `ImageAIProvider` para cada ferramenta, para trocar o motor sem mexer em fichas/contas.
- Worker de IA separado do worker de conversão; modelo **carregado uma vez por processo**, reutilizado entre jobs; limite de concorrência baseado em memória disponível (medido, não chutado).
- Limites configuráveis de tamanho/dimensão da imagem. Validação de conteúdo real. Timeouts.
- Meça latência e uso de memória em CPU e registre em `docs/architecture/` (números reais medidos, com a máquina usada).
- Confirme e registre a **licença comercial** do modelo e do código escolhidos antes de adotá-los.

### Removedor de fundo
Upload, preview, PNG transparente, cor sólida opcional, comparação antes/depois, download, status, erros. Candidato: rembg (confirme licença do modelo).

### Remover objeto indesejado
Editor com pincel/seleção de área para criar a máscara, inpainting, preview, antes/depois, controles de qualidade, download. Candidato: LaMa ou alternativa de licença permissiva (confirme).
- Exigir aceite: "Declaro que tenho direito de editar esta imagem." Registrar aceite.
- Texto honesto: o resultado depende da imagem; sem promessa de perfeição; sem incentivo a burlar autoria, licença ou proveniência.
- Se uma solicitação não puder ser atendida de forma adequada, explique a limitação.

### Frontend
Páginas `/removedor-de-fundo` e `/remover-objeto`, custo em fichas visível, progresso real, estados de erro, acessíveis e responsivas.

### Testes executados de verdade
- Jobs reais com imagens de amostra (resultado não vazio, canal alfa presente no PNG, dimensões preservadas).
- Negativos: arquivo não-imagem, imagem enorme, máscara inválida, timeout.
- Fichas: cobrança só em sucesso, devolução em falha, idempotência.
- Propriedade de download.

## Regras
- Se o desempenho em CPU for inviável, diga com números e proponha alternativa (limites menores, fila mais restrita, modelo menor) em vez de maquiar.
- Atualize `docs/CHECKLIST.md`.

## Ao terminar
Relatório com métricas medidas, licenças confirmadas, testes e limitações. **PARE e pergunte: "Posso seguir para a Fase 3C — Baixador de vídeos?"**
