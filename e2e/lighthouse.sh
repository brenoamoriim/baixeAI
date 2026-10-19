#!/bin/sh
# Runs inside the Playwright image (uses its Chromium). Writes JSON reports to /work/reports.
set -eu
CHROME=$(find /ms-playwright -type f -name chrome -path "*/chromium-*/chrome-linux*" | head -n 1)
[ -n "$CHROME" ] || { echo "Chromium não encontrado na imagem"; exit 1; }
export CHROME_PATH="$CHROME"
mkdir -p /work/reports
for page in / /conversores /precos; do
  name=$(echo "$page" | tr '/' '_')
  [ "$name" = "_" ] && name="_home"
  for preset in mobile desktop; do
    extra=""
    [ "$preset" = "desktop" ] && extra="--preset=desktop"
    npx lighthouse "$BASE_URL$page" $extra --quiet \
      --chrome-flags="--headless=new --no-sandbox --disable-dev-shm-usage" \
      --only-categories=performance,accessibility,best-practices,seo \
      --output=json --output-path="/work/reports/lh${name}-${preset}.json"
  done
done
node -e '
const fs = require("fs");
for (const f of fs.readdirSync("/work/reports").filter((f) => f.startsWith("lh")).sort()) {
  const r = JSON.parse(fs.readFileSync("/work/reports/" + f));
  const c = r.categories, a = r.audits;
  console.log(f.padEnd(28),
    "perf", Math.round(c.performance.score * 100), "a11y", Math.round(c.accessibility.score * 100),
    "bp", Math.round(c["best-practices"].score * 100), "seo", Math.round(c.seo.score * 100),
    "| LCP", a["largest-contentful-paint"].displayValue, "CLS", a["cumulative-layout-shift"].displayValue,
    "TBT", a["total-blocking-time"].displayValue);
}'
