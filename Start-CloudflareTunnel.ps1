# Start-CloudflareTunnel.ps1
#
# Starts the Cloudflare Tunnel that exposes the Studio API at https://api-beta.adeptui.org
#
# Prerequisites:
#   1. cloudflared installed: winget install cloudflare.cloudflared
#   2. Tunnel created: cloudflared tunnel create adept-ui-beta
#   3. DNS route created: cloudflared tunnel route dns adept-ui-beta api-beta.adeptui.org
#   4. Config file at config/cloudflared/adept-ui-beta-tunnel.yml
#      (replace <TUNNEL_ID> with the actual tunnel ID from step 2)
#
# Usage:
#   .\Start-CloudflareTunnel.ps1
#
# The tunnel is outbound-only — no inbound router ports are opened.
# TLS is terminated by Cloudflare; the local connection is HTTP to 127.0.0.1:8758.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $repoRoot "config\cloudflared\adept-ui-beta-tunnel.yml"

if (-not (Test-Path $configPath)) {
    Write-Error "Tunnel config not found at $configPath. Create it first."
    exit 1
}

# Verify cloudflared is installed
$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-Error "cloudflared is not installed. Install with: winget install cloudflare.cloudflared"
    exit 1
}

Write-Host "Starting Cloudflare Tunnel for api-beta.adeptui.org → http://127.0.0.1:8758"
Write-Host "Config: $configPath"
Write-Host ""

# Run the tunnel — this is a long-running process
# It will automatically reconnect if the connection drops
cloudflared tunnel run --config $configPath adept-ui-beta
