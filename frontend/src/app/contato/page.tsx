import type { Metadata } from "next";
import { ContactInfo } from "@/components/ContactInfo";

export const metadata: Metadata = { title: "Contato e suporte", alternates: { canonical: "/contato" } };

export default function ContactPage() {
  return (
    <article className="mx-auto flex max-w-3xl flex-col gap-4 text-slate-800">
      <h1 className="text-3xl font-bold text-slate-900">Contato e suporte</h1>
      <p>Use este canal para dúvidas, pedidos de reembolso, pedidos sobre seus dados (LGPD) e notificações de titulares de direitos.</p>
      <ContactInfo />
      <p className="text-sm text-slate-600">
        Ao escrever, informe o e-mail da sua conta. Nunca enviamos pedidos de senha ou de dados de cartão.
      </p>
    </article>
  );
}
