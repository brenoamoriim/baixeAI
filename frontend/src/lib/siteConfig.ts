"use client";

import { useEffect, useState } from "react";
import { api } from "./api";

export type SiteConfig = {
  ads: { enabled: boolean; client: string | null; slots: Record<string, string> };
  ads_txt_client?: string | null;
  support_email: string | null;
};

let cached: Promise<SiteConfig> | null = null;

export function loadSiteConfig(): Promise<SiteConfig> {
  cached ??= api<SiteConfig>("/site-config").catch(() => ({ ads: { enabled: false, client: null, slots: {} }, support_email: null }));
  return cached;
}

export function useSiteConfig(): SiteConfig | null {
  const [config, setConfig] = useState<SiteConfig | null>(null);
  useEffect(() => {
    let active = true;
    loadSiteConfig().then((c) => active && setConfig(c));
    return () => {
      active = false;
    };
  }, []);
  return config;
}

export const CONSENT_KEY = "baixeai_consent";
export type Consent = "ads" | "essential" | null;

export function readConsent(): Consent {
  try {
    const value = window.localStorage.getItem(CONSENT_KEY);
    return value === "ads" || value === "essential" ? value : null;
  } catch {
    return null; // storage blocked: behave as "no consent"
  }
}

export function writeConsent(value: "ads" | "essential"): void {
  try {
    window.localStorage.setItem(CONSENT_KEY, value);
  } catch {
    // ignore: the banner will simply show again next time
  }
  window.dispatchEvent(new Event("baixeai-consent"));
}

/** Pure rule, unit-tested: may an ad render on this path? */
export function adsAllowed(path: string, config: SiteConfig | null, consent: Consent, blocked: string[]): boolean {
  if (!config?.ads.enabled || !config.ads.client || consent !== "ads") return false;
  // plain prefix match on purpose: over-blocking (e.g. "/painel-x") is the safe direction
  return !blocked.some((prefix) => path.startsWith(prefix));
}
