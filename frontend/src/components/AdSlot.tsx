"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { adsAllowed, type Consent, readConsent, useSiteConfig } from "@/lib/siteConfig";
import { NO_ADS_PATHS } from "@/lib/site";

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

/** Ad placement. Renders NOTHING unless: ads enabled by admin + AdSense client configured + the
 * visitor accepted ad cookies + the page is not in NO_ADS_PATHS. Placed only at the bottom of
 * content, never next to upload/download/payment buttons. */
export function AdSlot({ slot }: { slot: string }) {
  const config = useSiteConfig();
  const path = usePathname();
  const [consent, setConsent] = useState<Consent>(null);

  useEffect(() => {
    const update = () => setConsent(readConsent());
    update();
    window.addEventListener("baixeai-consent", update);
    return () => window.removeEventListener("baixeai-consent", update);
  }, []);

  const slotId = config?.ads.slots[slot];
  const show = adsAllowed(path, config, consent, NO_ADS_PATHS) && Boolean(slotId);

  useEffect(() => {
    if (!show || !config?.ads.client) return;
    const src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(config.ads.client)}`;
    if (!document.querySelector(`script[src="${src}"]`)) {
      const script = document.createElement("script");
      script.src = src;
      script.async = true;
      script.crossOrigin = "anonymous";
      document.head.appendChild(script);
    }
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch {
      // ad blocked or not ready: nothing to show
    }
  }, [show, config]);

  if (!show) return null;
  return (
    <aside aria-label="Publicidade" className="mx-auto mt-12 w-full max-w-3xl">
      <p className="mb-1 text-center text-xs text-slate-500">Publicidade</p>
      <ins className="adsbygoogle block min-h-[100px]" data-ad-client={config!.ads.client!} data-ad-slot={slotId}
           data-ad-format="auto" data-full-width-responsive="true" />
    </aside>
  );
}
