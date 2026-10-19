# End-to-end + accessibility (axe) + Lighthouse against the PRODUCTION frontend build.
# Requires the dev stack running (docker compose up -d). Windows PowerShell:
#   powershell -ExecutionPolicy Bypass -File e2e\run.ps1            # e2e + lighthouse
#   powershell -ExecutionPolicy Bypass -File e2e\run.ps1 -SkipLighthouse
param([switch]$SkipLighthouse)
# "Continue": Windows PowerShell 5.1 turns native stderr into errors; exit codes are checked explicitly.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$e2e = Join-Path $root "e2e"
$net = "baixeai_edge"
$image = "mcr.microsoft.com/playwright:v1.63.0-noble"

function Invoke-Checked([string]$what, [scriptblock]$cmd) {
  & $cmd
  if ($LASTEXITCODE -ne 0) { throw "$what falhou (exit $LASTEXITCODE)" }
}
# Throwaway admin for this run only (dev database); a new e-mail each run because create-admin keeps existing passwords.
$adminEmail = "e2e-admin-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())@example.com"
$adminPassword = "e2e-" + [guid]::NewGuid().ToString("N")
function Run-Playwright([string]$cmd) {
  docker run --rm --network $net --ipc=host -e BASE_URL=http://e2e-proxy:8080 `
    -e E2E_ADMIN_EMAIL=$adminEmail -e E2E_ADMIN_PASSWORD=$adminPassword `
    -v "${e2e}:/work" -v baixeai-e2e-node:/work/node_modules -w /work $image sh -c $cmd
}

try {
  Invoke-Checked "build do frontend (produção)" { docker build --target runtime -t baixeai-frontend-prod (Join-Path $root "frontend") }
  docker rm -f baixeai-frontend-prod baixeai-e2e-proxy *> $null
  Invoke-Checked "frontend-prod" { docker run -d --name baixeai-frontend-prod --network $net --network-alias frontend-prod baixeai-frontend-prod }
  Invoke-Checked "e2e-proxy" { docker run -d --name baixeai-e2e-proxy --network $net --network-alias e2e-proxy `
    -v "$(Join-Path $e2e 'Caddyfile.e2e'):/etc/caddy/Caddyfile:ro" caddy:2.11.7-alpine }

  # Dev only: repeated runs from the same container IP hit the real signup rate limit (5/hour). Clear just those keys.
  Invoke-Checked "limpar rate limit de cadastro (dev)" { docker compose -f (Join-Path $root "docker-compose.yml") exec -T api python -c "from app.security.rate_limit import get_redis as g; r = g(); print('rate-limit keys cleared:', sum(r.delete(k) for k in r.scan_iter('rl:register:*')))" }

  Invoke-Checked "instalação das dependências" { Run-Playwright "npm ci --no-audit --no-fund" }
  Invoke-Checked "e2e: páginas públicas + cadastro" { Run-Playwright "npx playwright test --grep '@public|@signup'" }

  $email = (Get-Content (Join-Path $e2e ".state/email.txt") -Raw).Trim()
  Invoke-Checked "confirmar e-mail (CLI de dev)" { docker compose -f (Join-Path $root "docker-compose.yml") exec -T api python -m app.cli verify-email --email $email }
  Invoke-Checked "e2e: usar ferramenta e ver saldo" { Run-Playwright "npx playwright test --grep @use --project desktop" }
  Invoke-Checked "criar admin de teste (CLI)" { docker compose -f (Join-Path $root "docker-compose.yml") exec -T api python -m app.cli create-admin --email $adminEmail --password $adminPassword }
  Invoke-Checked "e2e: admin" { Run-Playwright "npx playwright test --grep @admin --project desktop" }

  if (-not $SkipLighthouse) { Invoke-Checked "lighthouse" { Run-Playwright "sh /work/lighthouse.sh" } }
  Write-Host "OK: e2e concluído" -ForegroundColor Green
}
finally {
  docker rm -f baixeai-frontend-prod baixeai-e2e-proxy *> $null
}
