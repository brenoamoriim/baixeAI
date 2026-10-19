"use client";

import { useSiteConfig } from "@/lib/siteConfig";
import { Alert } from "./ui";

export function ContactInfo() {
  const config = useSiteConfig();
  if (!config) return <p>Carregando…</p>;
  if (!config.support_email)
    return <Alert kind="info">O e-mail de suporte ainda não foi definido (depende do domínio próprio).</Alert>;
  return (
    <p className="text-lg">
      E-mail: <a href={`mailto:${config.support_email}`} className="font-semibold text-blue-700 underline">{config.support_email}</a>
    </p>
  );
}
