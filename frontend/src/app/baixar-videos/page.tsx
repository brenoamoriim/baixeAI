import type { Metadata } from "next";
import { ToolInfo } from "@/components/ToolInfo";
import Client from "./Client";

export const metadata: Metadata = {
  title: "Baixar vídeos públicos online (MP4, MP3)",
  description: "Cole o link de um vídeo público e baixe em MP4 ou só o áudio em MP3/M4A. Mostramos as qualidades reais disponíveis antes de cobrar.",
  alternates: { canonical: "/baixar-videos" },
  openGraph: { title: "Baixar vídeos públicos online (MP4, MP3)", description: "Cole o link de um vídeo público e baixe em MP4 ou só o áudio em MP3/M4A. Mostramos as qualidades reais disponíveis antes de cobrar.", url: "/baixar-videos", locale: "pt_BR", type: "website" },
};

export default function Page() {
  return (
    <>
      {/* min-h: the tool UI renders on the client; reserving the viewport keeps the info below from shifting */}
      <div className="min-h-screen">
        <Client />
      </div>
      <ToolInfo
        path="/baixar-videos"
        name="Baixador de vídeos"
        description="Cole o link de um vídeo público e baixe em MP4 ou só o áudio em MP3/M4A. Mostramos as qualidades reais disponíveis antes de cobrar."
        sections={[{"title": "O que dá para baixar", "body": ["Somente conteúdo público, acessível sem login. Não baixamos vídeos privados, pagos, exclusivos para membros ou protegidos por DRM, e nunca pedimos senha ou cookies de redes sociais.", "Antes de baixar, você declara que tem direito sobre o conteúdo (por exemplo, é seu, está em domínio público ou tem autorização do titular) e assume a responsabilidade pelo uso."]}, {"title": "Por que às vezes não funciona", "body": ["As plataformas mudam com frequência e podem bloquear o acesso a partir dos nossos servidores. Quando isso acontece, a ficha é devolvida e o erro é mostrado com clareza."]}]}
        faq={[{"q": "A consulta do link custa ficha?", "a": "Não. A consulta é gratuita e mostra as opções reais; a ficha só é usada quando você confirma o download."}, {"q": "Quanto custa?", "a": "1 ficha; vídeos com mais de 2 minutos custam 2 fichas."}, {"q": "Quais plataformas funcionam?", "a": "Não mantemos uma lista fixa: depende do conteúdo ser público e da plataforma permitir o acesso naquele momento."}]}
      />
    </>
  );
}
