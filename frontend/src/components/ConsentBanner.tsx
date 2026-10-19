"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { readConsent, useSiteConfig, writeConsent } from "@/lib/siteConfig";
import { Button } from "./ui";

/** Shown only when ads are actually enabled: otherwise the site uses essential cookies only
 * (session, CSRF, anonymous visitor id), which do not require consent. */
export function ConsentBanner() {
  const config = useSiteConfig();
  const [decided, setDecided] = useState(true);

  useEffect(() => {
    setDecided(readConsent() !== null); // eslint-disable-line react-hooks/set-state-in-effect -- read browser storage after mount
  }, []);

  if (!config?.ads.enabled || decided) return null;
  return (
    <div role="dialog" aria-label="Preferências de cookies"
         className="fixed inset-x-0 bottom-0 z-50 border-t border-slate-200 bg-white p-4 shadow-lg">
      <div className="mx-auto flex max-w-5xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-700">
          Usamos cookies essenciais para login e segurança. Com sua permissão, também usamos cookies de publicidade do
          Google AdSense. <Link href="/cookies" className="underline">Saiba mais</Link>.
        </p>
        <div className="flex shrink-0 gap-2">
          <Button type="button" variant="secondary" onClick={() => { writeConsent("essential"); setDecided(true); }}>
            Só essenciais
          </Button>
          <Button type="button" onClick={() => { writeConsent("ads"); setDecided(true); }}>
            Aceitar anúncios
          </Button>
        </div>
      </div>
    </div>
  );
}
