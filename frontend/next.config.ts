import type { NextConfig } from "next";

// The browser only talks to this origin; /api/* is proxied to the FastAPI service, so session
// cookies stay first-party and no CORS is needed. Evaluated when the server starts/builds.
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

// Content Security Policy (production builds only: `next dev` needs eval for Fast Refresh).
// 'unsafe-inline' scripts are required by statically prerendered Next.js pages (nonces need dynamic
// rendering). The Google domains are only for AdSense, which loads only after consent; the exact list
// AdSense needs must be re-checked when ads are switched on (docs/VALIDACOES-DOS-SOCIOS.md, Fase 5).
const ADS = "https://pagead2.googlesyndication.com https://*.googlesyndication.com https://*.adtrafficquality.google";
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' ${ADS} https://www.googletagservices.com`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src 'self' ${ADS} https://*.google.com`,
  `frame-src ${ADS} https://*.doubleclick.net https://*.google.com`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  ...(process.env.NODE_ENV === "production" ? [{ key: "Content-Security-Policy", value: csp }] : []),
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  // `next dev` only: let remote testers reach the dev server through the Cloudflare quick tunnel
  // (docker compose --profile tunnel). Has no effect on production builds.
  allowedDevOrigins: ["*.trycloudflare.com"],
  output: "standalone",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
