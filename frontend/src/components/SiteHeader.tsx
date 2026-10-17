"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useMe } from "@/lib/useMe";

export function SiteHeader() {
  const { me } = useMe();

  async function logout() {
    await api("/auth/logout", { method: "POST" });
    // Full reload on purpose: route state is preserved across navigations (cacheComponents),
    // so a client push would keep the previous user's header/session view.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/");
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <nav aria-label="Principal" className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-xl font-bold text-blue-800">
          BaixeAI
        </Link>
        <ul className="flex items-center gap-4 text-sm">
          {me === undefined ? null : me ? (
            <>
              <li>
                <Link href="/painel" className="font-medium text-slate-800 hover:underline">
                  Meu painel
                </Link>
              </li>
              <li>
                <button type="button" onClick={logout} className="text-slate-600 hover:underline">
                  Sair
                </button>
              </li>
            </>
          ) : (
            <>
              <li>
                <Link href="/entrar" className="font-medium text-slate-800 hover:underline">
                  Entrar
                </Link>
              </li>
              <li>
                <Link href="/cadastrar" className="rounded-md bg-blue-700 px-3 py-1.5 font-semibold text-white hover:bg-blue-800">
                  Criar conta grátis
                </Link>
              </li>
            </>
          )}
        </ul>
      </nav>
    </header>
  );
}
