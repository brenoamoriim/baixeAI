import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Direitos de conteúdo e remoção", alternates: { canonical: "/direitos-de-conteudo" } };

export default function Page() {
  return <LegalPage title="Direitos de conteúdo e remoção" updated="19/10/2026" sections={[{"title": "Nosso compromisso", "body": ["Só permitimos baixar conteúdo público e editar imagens sobre as quais o usuário declara ter direito. Não armazenamos os arquivos por mais de algumas horas e não os publicamos."]}, {"title": "Titulares de direitos", "body": ["Se você é titular de direitos e acredita que o serviço está sendo usado para violá-los, entre em contato pela página de Contato com a descrição do conteúdo e a comprovação da titularidade. Analisaremos e poderemos bloquear contas ou origens abusivas.", "Procedimento formal de notificação e prazos de resposta: a definir com assessoria jurídica."]}]} />;
}
