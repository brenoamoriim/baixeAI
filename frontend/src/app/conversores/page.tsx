import type { Metadata } from "next";
import { AdSlot } from "@/components/AdSlot";
import { ToolInfo } from "@/components/ToolInfo";
import Client from "./Client";

export const metadata: Metadata = {
  title: "Conversor de arquivos online: PDF, Word, imagens, áudio e vídeo",
  description: "Converta PDF, DOCX, imagens (JPG, PNG, WEBP, AVIF, HEIC), áudio (MP3, WAV, OPUS) e vídeo (MP4, WEBM) online. Só oferecemos conversões testadas com arquivos reais.",
  alternates: { canonical: "/conversores" },
  openGraph: { title: "Conversor de arquivos online: PDF, Word, imagens, áudio e vídeo", description: "Converta PDF, DOCX, imagens (JPG, PNG, WEBP, AVIF, HEIC), áudio (MP3, WAV, OPUS) e vídeo (MP4, WEBM) online. Só oferecemos conversões testadas com arquivos reais.", url: "/conversores", locale: "pt_BR", type: "website" },
};

export default function Page() {
  return (
    <>
      {/* min-h: the tool UI renders on the client; reserving the viewport keeps the info below from shifting */}
      <div className="min-h-screen">
        <Client />
      </div>
      <ToolInfo
        path="/conversores"
        name="Conversores"
        description="Converta PDF, DOCX, imagens (JPG, PNG, WEBP, AVIF, HEIC), áudio (MP3, WAV, OPUS) e vídeo (MP4, WEBM) online. Só oferecemos conversões testadas com arquivos reais."
        sections={[{"title": "Documentos", "body": ["Transforme DOCX, DOC, ODT, RTF, TXT e HTML em PDF para enviar ou imprimir sem perder a formatação. Também convertemos DOC antigo em DOCX, planilhas XLSX e XLS em CSV e CSV em XLSX.", "PDF para DOCX funciona para recuperar o texto, mas o layout (colunas, fontes e posições) pode mudar: avisamos antes. PDF escaneado não tem texto e por isso não vira documento editável — não fazemos OCR."]}, {"title": "Imagens", "body": ["Converta entre JPG, PNG, WEBP, AVIF, GIF, TIFF, BMP e ICO, e abra fotos HEIC do iPhone ou SVG. Os metadados (como a localização GPS da foto) são removidos do arquivo final.", "Para JPG, WEBP e AVIF você escolhe a qualidade. Imagens com transparência viram fundo branco ao salvar em JPG, que não suporta transparência."]}, {"title": "Áudio e vídeo", "body": ["Converta MP3, WAV, OGG, M4A, FLAC e OPUS ajustando taxa de bits, taxa de amostragem e canais. Vídeos MP4, WEBM, MKV, MOV e AVI podem mudar de formato, de resolução e de quadros por segundo, ter o áudio extraído ou virar GIF curto.", "Limites atuais: documentos até 25 MB, imagens até 20 MB, áudio até 50 MB e vídeo até 95 MB e 10 minutos. Conversões de vídeo custam 2 fichas; as demais, 1."]}]}
        faq={[{"q": "Meus arquivos ficam guardados?", "a": "Não. Os arquivos enviados e os resultados são apagados automaticamente em poucas horas, e só você consegue baixar o resultado."}, {"q": "Quanto custa converter?", "a": "Cada conversão concluída usa 1 ficha (vídeo: 2). Visitantes têm 1 ficha para testar e contas gratuitas recebem 5 por dia."}, {"q": "Por que um formato não aparece?", "a": "Só mostramos combinações que passaram em testes com arquivos reais. Se uma conversão não está na lista, ela ainda não é oferecida."}, {"q": "A conversão falhou. Perco a ficha?", "a": "Se a falha for nossa (erro interno ou tempo esgotado), a ficha volta. Se o arquivo estiver corrompido, a ficha é consumida."}]}
      />
      <AdSlot slot="tool_bottom" />
    </>
  );
}
