# 07 — Formatos, motores e registry de ferramentas

> Fase 1 · 17/10/2026. Nenhuma combinação abaixo está `available` ainda: todas são **candidatas**. Viram `available` só com teste de motor verde (Fases 3A–3C).

## 1. Registry de capacidades

- `tool_definitions` (ferramenta, custo em fichas, fila) + `tool_capabilities` (entrada → saída, `status`, motor, `options_schema`).
- Código: `backend/app/tools/registry.py` mapeia `(tool_id, input, output)` → handler. Na inicialização, a API **cruza** banco × código: capacidade `available` sem handler registrado é rebaixada para `planned` e gera alerta (impede expor algo não implementado).
- O frontend lista apenas o que a API devolve como `available`. `planned` pode aparecer como "em breve" (decisão de UI da Fase 5); `unsupported` nunca aparece.
- `options_schema` (JSON Schema) define opções permitidas (bitrate, resolução, fps…) com enums/limites fechados; o handler traduz para argumentos de template. Nenhum valor do usuário vira argumento livre.

## 2. Motores — verificação em 17/10/2026

Verificação empírica: `docker run python:3.12-slim` (Debian 13 "trixie") + `apt-get install` dos pacotes, amd64 (ARM64 em `§2.1`).

| Motor | Versão verificada | Licença | Uso comercial em SaaS | Observação |
|---|---|---|---|---|
| FFmpeg (pacote Debian) | 7.1.5 | build `--enable-gpl` → **GPL** como um todo ([ffmpeg.org/legal](https://ffmpeg.org/legal.html)) | Executado como programa separado no servidor, sem distribuição: obrigações de distribuição da GPL não são acionadas — **interpretação, não parecer jurídico** | Encoders presentes: `libx264`, `libx265`, `libvpx-vp9`, `libvpx`, `libaom-av1`, `libsvtav1`, `aac`, `libmp3lame`, `libopus`, `libvorbis`, `flac`, `alac`, `pcm_s16le`, `gif`, `mpeg4`. Decoders: h264, hevc, vp9, av1 (`libdav1d`). **Patentes** de H.264/HEVC/AAC: risco jurídico não avaliado (**NÃO VERIFICADO**) |
| LibreOffice (headless, `-nogui`) | 25.2.3.2 | MPL-2.0 | Sim | Writer + Calc são suficientes |
| Pandoc | 3.1.11.1 | GPL-2.0+ | Sim (programa separado) | Uso secundário (HTML/TXT) |
| libvips (`libvips-tools`) | 8.16.1 | LGPL-2.1+ | Sim | Testado: salvar AVIF, WEBP, TIFF, GIF, JPG; ler AVIF; **ler HEIC** com `libheif-plugin-libde265` (LGPL). Salvar HEIC **não** (sem encoder HEVC — e não é necessário: HEIC é só entrada) |
| Pillow | — | MIT-CMU (HPND) | Sim | Para ICO/BMP (saída). **Não testado nesta fase** |
| poppler-utils (`pdftotext`) | 25.03.0 | GPL-2.0+ | Sim (programa separado) | PDF → TXT |
| rembg | — | MIT ([GitHub](https://github.com/danielgatis/rembg)) — exige Python ≥ 3.11, < 3.14 | Sim (código) | Pesos têm licença própria (abaixo) |
| Modelos de fundo | U²-Net / `isnet-general-use`: **Apache-2.0** (LICENSE dos repositórios xuebinqin/U-2-Net e xuebinqin/DIS); BiRefNet: **MIT** (repo e HF `ZhengPeng7/BiRefNet`); **BRIA RMBG**: licença própria, **exige acordo pago para uso comercial** → **proibido** | | Usar `isnet-general-use` ou `birefnet-general-lite` (decidir por qualidade × CPU na Fase 3B) | |
| LaMa (inpainting) | — | código **Apache-2.0** (advimman/lama); pesos `smartywu/big-lama` e `Carve/LaMa-ONNX` marcados **apache-2.0** no Hugging Face | Sim pela licença dos pesos | ⚠️ O modelo foi treinado no dataset Places2, cujos termos de uso do dataset **não foram verificados**. Risco residual baixo, mas registrado. Alternativa de execução: ONNX em CPU |
| yt-dlp | — | **Unlicense** (domínio público); binários PyInstaller são GPLv3+ (usaremos via pip, não o binário) | Sim | Python ≥ 3.10; YouTube completo exige `yt-dlp-ejs` + runtime JS (deno recomendado); FFmpeg para juntar áudio/vídeo |
| pdf2docx (PDF → DOCX) | — | MIT, **mas depende de PyMuPDF (AGPL-3.0)** | ⚠️ AGPL em serviço de rede pode obrigar a oferecer o código-fonte do sistema que o incorpora | Ver decisão em `12` |
| ImageMagick | — | — | — | **Fora do MVP** (libvips + Pillow cobrem) |

### 2.1 ARM64 (hospedagem Oracle Ampere)

Resultado do teste emulado (`--platform linux/arm64`): ver relatório final da Fase 1 / `docs/CHECKLIST.md`. Disponibilidade de wheels `onnxruntime` aarch64: **NÃO VERIFICADO** (Fase 3B).

## 3. Combinações candidatas (lançamento, PRD §6.2)

Legenda de status inicial após a Fase 1: todas `planned`. Coluna "Prova" = como o teste da Fase 3 comprova a combinação.

### Documentos (`worker-light`, limite 25 MB)
| Entrada → Saída | Motor | Prova |
|---|---|---|
| DOCX, DOC, ODT, RTF, TXT, HTML → PDF | LibreOffice | saída começa com `%PDF`, `pdfinfo` lê nº de páginas ≥ 1, texto extraído contém marcador do arquivo de teste |
| DOC → DOCX | LibreOffice | ZIP válido com `word/document.xml`; texto marcador preservado |
| PDF → TXT | `pdftotext` | texto marcador presente (aviso: PDF escaneado não tem texto — OCR fora do MVP) |
| PDF → DOCX | pdf2docx (AGPL!) ou LibreOffice (`writer_pdf_import`, qualidade baixa) | **bloqueado até decisão de licença** (`12`) |
| XLSX, XLS → CSV | LibreOffice Calc | CSV com as células do teste (UTF-8, separador definido) |
| CSV → XLSX | LibreOffice Calc | abre no Calc com as mesmas células |

HTML de entrada: renderizado sem acesso à rede (worker isolado); imagens remotas não carregam — documentar.

### Imagens (`worker-light`, limite 20 MB + teto de pixels)
| Entrada | Saída | Motor | Prova |
|---|---|---|---|
| JPG, PNG, WEBP, AVIF, GIF, BMP, TIFF, HEIC/HEIF, SVG | JPG, PNG, WEBP, AVIF, GIF, TIFF | libvips | saída reabre no libvips com mesmas dimensões (ou redimensionadas conforme opção) |
| idem | BMP, ICO | Pillow | reabre no Pillow; ICO com tamanhos padrão (16–256) |
| ICO | (entrada) | Pillow | — |

GIF animado → formatos estáticos usa o 1º quadro (avisar). SVG: sanitizado e rasterizado (`08` T6).

### Áudio (`worker-media`, limite 50 MB)
| Entrada | Saída | Encoder | Prova |
|---|---|---|---|
| MP3, WAV, OGG, M4A/AAC, FLAC, OPUS | MP3 | `libmp3lame` | `ffprobe`: codec, duração ± 0,1 s, canais/taxa pedidos |
| idem | WAV | `pcm_s16le` | idem |
| idem | OGG | `libvorbis` | idem |
| idem | M4A (AAC) | `aac` (nativo) | idem |
| idem | FLAC | `flac` | idem |
| idem | OPUS | `libopus` | idem |

Opções: bitrate (lista fechada), taxa de amostragem (8000–48000 em lista), canais (1/2).

### Vídeo (`worker-media`, limite 200 MB e 10 min 🔶 ver limite do Cloudflare em `12`)
| Entrada | Saída | Codecs | Prova |
|---|---|---|---|
| MP4, WEBM, MKV, MOV, AVI | MP4 | H.264 (`libx264`) + AAC | `ffprobe` codec/resolução/duração |
| idem | WEBM | VP9 (`libvpx-vp9`) + Opus | idem (VP9 é lento em CPU: medir) |
| idem | MKV | H.264 + AAC (ou cópia de streams quando compatível) | idem |
| idem | MOV | H.264 + AAC | idem |
| idem | AVI | MPEG-4 Part 2 (`mpeg4`) + MP3 | idem |
| vídeo → áudio | MP3/M4A/WAV/OGG/OPUS/FLAC | como Áudio | idem |
| vídeo → GIF | GIF | `palettegen`/`paletteuse` | limite de duração (ex.: 15 s) e fps ≤ 15 |

Opções: resolução (lista: 360p/480p/720p/1080p, nunca acima da original), qualidade (CRF em lista fechada), fps (lista). Preset de encoder fixo (`veryfast`) para caber na CPU.

HEVC, AV1, XviD/DivX como **codecs de saída**: `planned` (o FFmpeg verificado tem `libx265`, `libsvtav1`, `mpeg4`, mas custo de CPU e patentes não foram avaliados).

### IA (`worker-ai`)
| Ferramenta | Entrada | Saída | Prova |
|---|---|---|---|
| `background_remover` | JPG, PNG, WEBP | PNG transparente; opcional fundo sólido (JPG/PNG) | PNG com canal alfa; máscara não vazia em imagem de teste sintética |
| `object_remover` | JPG, PNG, WEBP + máscara do pincel | mesmo formato | região mascarada alterada, restante idêntico (diferença fora da máscara ≈ 0) |

### Baixador (`worker-download`)
| Entrada | Saída | Prova |
|---|---|---|
| URL pública (qualquer site suportado pelo yt-dlp) | MP4 (vídeo) / M4A ou MP3 (áudio) conforme opções **reais** retornadas | teste com servidor HTTP de fixture servindo um MP4 gerado (não depende de plataformas externas no CI); como o SSRF bloqueia IPs privados, o fixture usa uma allowlist que **só existe com `APP_ENV=test`** e há teste garantindo que ela é ignorada em `production`; teste manual com plataformas reais documentado |
