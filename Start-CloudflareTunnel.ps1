# Start-CloudflareTunnel.ps1
#
# Starts the Cloudflare Tunnel that exposes the Studio API at https://api-beta.adeptui.org
#
# Prerequisites:
#   1. cloudflared installed: winget install cloudflare.cloudflared
#   2. Authenticated: cloudflared tunnel login
#   3. Tunnel created: cloudflared tunnel create adept-ui-beta
#   4. DNS route created: cloudflared tunnel route dns adept-ui-beta api-beta.adeptui.org
#   5. Config file at config/cloudflared/adept-ui-beta-tunnel.yml
#
# Usage:
#   .\Start-CloudflareTunnel.ps1
#
# The tunnel is outbound-only — no inbound router ports are opened.
# TLS is terminated by Cloudflare; the local connection is HTTP to 127.0.0.1:8758.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot "config\cloudflared\adept-ui-beta-tunnel.yml"
$tunnelName = "adept-ui-beta"
$healthUrl = "https://api-beta.adeptui.org/api/healthz"
$localHealthUrl = "http://127.0.0.1:8758/api/healthz"

# --- Pre-flight checks ---

if (-not (Test-Path $configPath)) {
    Write-Error "Tunnel config not found at $configPath. Create it first."
    exit 1
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-Error "cloudflared is not installed. Install with: winget install cloudflare.cloudflared"
    exit 1
}

if (-not (Test-Path "$env:USERPROFILE\.cloudflared\cert.pem")) {
    Write-Error "Cloudflare not authenticated. Run: cloudflared tunnel login"
    exit 1
}

# --- Detect existing tunnel process ---

$existing = Get-Process cloudflared -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "adept-ui-beta"
}

if ($existing) {
    Write-Host "[tunnel] Already running (PID $($existing.Id)). Verifying health..." -ForegroundColor Yellow
    try {
        $h = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 10
        if ($h.StatusCode -eq 200) {
            Write-Host "[tunnel] HEALTHY — $healthUrl → $($h.StatusCode) $($h.Content)" -ForegroundColor Green
        } else {
            Write-Host "[tunnel] DEGRADED — $healthUrl → $($h.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[tunnel] UNREACHABLE — $healthUrl failed: $_" -ForegroundColor Red
    }
    exit 0
}

# --- Verify local Studio API is up ---

Write-Host "[tunnel] Pre-flight: checking local Studio API at $localHealthUrl" -ForegroundColor Cyan
try {
    $localH = Invoke-WebRequest -Uri $localHealthUrl -UseBasicParsing -TimeoutSec 5
    if ($localH.StatusCode -eq 200) {
        Write-Host "[tunnel] Local Studio API: HEALTHY" -ForegroundColor Green
    } else {
        Write-Error "[tunnel] Local Studio API returned $($localH.StatusCode). Start Beta first: .\Start-AdeptUI-Beta.ps1"
        exit 1
    }
} catch {
    Write-Error "[tunnel] Local Studio API unreachable at $localHealthUrl. Start Beta first: .\Start-AdeptUI-Beta.ps1"
    exit 1
}

# --- Start tunnel ---

Write-Host "[tunnel] Starting Cloudflare Tunnel: api-beta.adeptui.org → http://127.0.0.1:8758" -ForegroundColor Cyan
Write-Host "[tunnel] Config: $configPath"
Write-Host ""

# Run the tunnel — this is a long-running process that auto-reconnects.
# Use --config before `run` (cloudflared flag order requirement).
& cloudflared tunnel --config $configPath run $tunnelName
