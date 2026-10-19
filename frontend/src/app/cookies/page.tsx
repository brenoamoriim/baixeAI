import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Política de cookies", alternates: { canonical: "/cookies" } };

export default function Page() {
  return <LegalPage title="Política de cookies" updated="19/10/2026" sections={[{"title": "Cookies essenciais (sempre ativos)", "body": ["baixeai_session: mantém você conectado (HttpOnly).", "baixeai_csrf: protege os formulários contra ataques de falsificação de requisição.", "baixeai_guest: identifica anonimamente o visitante sem cadastro para controlar a ficha gratuita (guardado como hash).", "Esses cookies são necessários para o funcionamento e não dependem de consentimento."]}, {"title": "Cookies de publicidade (opcionais)", "body": ["Se os anúncios estiverem ativos e você aceitar, o Google AdSense pode usar cookies para exibir e medir anúncios. Sem o seu aceite, nenhum script de anúncio é carregado. Os anúncios nunca aparecem nas páginas do baixador de vídeos, da conta ou de pagamento."]}]} />;
}
