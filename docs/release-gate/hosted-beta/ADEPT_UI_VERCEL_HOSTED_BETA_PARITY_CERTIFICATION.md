# Adept UI — Vercel Hosted Beta Skeleton-Shell Root-Cause & Full Runtime Parity Pass

| Field | Value |
|---|---|
| Date | 2026-08-10 |
| Branch | `beta` |
| Starting SHA | `2f2a338` (clean-clone build PASS) |
| Ending SHA | `58daef9` |
| Status | **PARTIAL GO** — code fixes complete, hosted certification pending user infrastructure setup |

---

## 1. Root Cause Analysis

The Vercel deployment at `https://adeptui.vercel.app` was a skeleton shell due to **two independent root causes**:

### Root Cause 1: No Central API Origin Abstraction

**File:** `studio-web/src/api.ts:69`

```69:69:studio-web/src/api.ts
const BASE = "";
```

All API calls used relative `/api/*` paths. In local dev, the Vite proxy (`vite.config.ts`) forwards `/api` and `/media` to `http://127.0.0.1:8742`. On Vercel, there is no backend proxy — relative `/api/*` requests hit Vercel's serverless functions (which don't exist) and return 404.

**Impact:** Every API call from the hosted frontend failed. Health probes returned 404, triggering the "Studio API partially available — Health check returned HTTP 404" banner. No project data, no Co-Director, no Timeline, no runtime status — skeleton shell.

### Root Cause 2: 77 Untracked Visual Assets

**Finding:** 77 of 80 `public/` asset files existed on disk but were never committed to git. Vercel builds from git, so all hero imagery, brand logo, template art, workspace cards, and empty-state graphics would 404 on the hosted deployment.

**Impact:** Even if API calls succeeded, the hosted UI would still look like a skeleton — missing hero header, brand logo, all card art, all template thumbnails, all workspace icons.

---

## 2. Repairs

### Repair 1: Central API Origin Abstraction (`efb5e1c`)

Created `studio-web/src/runtime/apiBase.ts`:

```typescript
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

export function apiUrl(path: string): string {
  if (!API_BASE) return path;
  return `${API_BASE}${path}`;
}
```

Updated all API call sites to use `apiUrl()`:

| File | Change |
|---|---|
| `src/api.ts` | Import `API_BASE` + re-export `apiUrl()` from `apiBase.ts` |
| `src/runtime/studioApiConnection.ts` | Health probes `/api/healthz` and `/api/health` now use `apiUrl()` |
| `src/posecraft/posecraftApi.ts` | `req()` and direct `fetch()` now use `apiUrl()` |
| `src/magiSequence/api.ts` | Both `fetch()` calls now use `apiUrl()` |
| `src/pages/DiagnosticsPage.tsx` | `fetch("/api/diagnostics/run")` → `fetch(apiUrl(...))` |
| `src/components/GenerationTools/PoseCraftWorkspace.tsx` | Asset upload `fetch()` now uses `apiUrl()` |
| `src/components/dashboard/NewProductionCard.tsx` | Video generators `fetch()` now uses `apiUrl()` |
| `src/hooks/useInstallJobs.ts` | SSE `EventSource` now uses `apiUrl()` |
| `src/components/timeline-master/TimelinePreviewComposer.tsx` | SSE `EventSource` now uses `apiUrl()` |
| `src/components/LivePreviewMonitor.tsx` | SSE `EventSource` now uses `apiUrl()` |
| `src/api.ts` `mediaUrl()` | Returns `apiUrl("/media/...")` or `apiUrl("/api/file?path=...")` |
| `src/api.ts` `assetUrl()` | Returns `apiUrl("/api/assets/.../file")` |
| `src/posecraft/engine.ts` | Babylon mesh loader URL now uses `apiUrl()` |

**Design:** Extracted to `runtime/apiBase.ts` to avoid circular imports between `api.ts` (which dynamically imports `studioApiConnection.ts`) and `studioApiConnection.ts` (which needs `apiUrl()`).

### Repair 2: Commit All Visual Assets (`58daef9`)

Committed all 77 untracked `public/` files:
- `public/brand/adept-ui-logo.svg`
- `public/images/hero/` (8 files: hero header, director, MAGI, timeline art)
- `public/images/ui/` (~68 files: templates, workspaces, motifs, cards, empty-states, backgrounds)

### Repair 3: SPA Routing (`efb5e1c`, fixed `f9397c0`)

Created `studio-web/vercel.json` with catch-all rewrite:

```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "installCommand": "npm install",
  "rewrites": [
    { "source": "/((?!api/).*)", "destination": "/index.html" }
  ]
}
```

This ensures direct navigation to `/project/:id`, `/co-director`, `/diagnostics`, etc. doesn't 404 on Vercel.

### Repair 4: CORS Security (`efb5e1c`)

**File:** `studio-api/app/main.py`

Replaced insecure `allow_origins=["*"]` + `allow_credentials=True` (browsers reject wildcard with credentials) with explicit origins:

```python
_default_cors_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "https://adeptui.vercel.app",
    "https://beta.adeptui.org",
]
_extra_origins = os.environ.get("STUDIO_CORS_ORIGINS", "")
```

Supports `STUDIO_CORS_ORIGINS` env var for additional origins.

### Repair 5: Cloudflare Tunnel Configuration (`efb5e1c`)

Created:
- `config/cloudflared/adept-ui-beta-tunnel.yml` — tunnel config mapping `api-beta.adeptui.org` → `http://127.0.0.1:8758`
- `Start-CloudflareTunnel.ps1` — PowerShell script to start the tunnel

### Repair 6: Environment Documentation (`efb5e1c`)

Created `studio-web/.env.example` documenting `VITE_API_BASE`:
- Local dev: leave unset (defaults to `""` → relative paths via Vite proxy)
- Hosted beta: `VITE_API_BASE=https://api-beta.adeptui.org`

### Repair 7: Gitignore Security (`efb5e1c`)

Added to `.gitignore`:
- `.cloudflared/` (tunnel credentials)
- `*.cloudflared.json`
- `config/cloudflared/*.local.yml`
- `studio-web/.env.local`

---

## 3. Subagent Audit Findings

### CORS Audit (kimi-k3-max)
- 5 SSE endpoints found — all covered by global CORS middleware
- 0 WebSocket endpoints
- 3 upload routes, 4 file-serving routes
- Confirmed wildcard+credentials is unreliable; explicit origins required

### Frontend API Audit (kimi-k3-max)
- 0 executable hardcoded localhost/127.0.0.1 references
- All API traffic routes through single `apiBase.ts` abstraction
- 11 client-side routes need SPA rewrites (now configured)
- `import.meta.env.VITE_API_BASE` already supported via `apiBase.ts`

### Asset Audit (kimi-k3-max)
- 77 of 80 `public/` files untracked — major skeleton shell cause
- 0 `file://` URLs, 0 raw Windows path asset URLs
- All dynamic media flows through `/api/assets/` and `/media/` (need runtime bridge)
- CSS uses only gradients + one self-contained data: URI — no external CSS assets

---

## 4. Build Verification

```
npm run build → ✓ built in 1.43s (zero errors)
```

Local Beta health:
```
http://127.0.0.1:8758/api/healthz → 200 {"status":"ok"}
http://127.0.0.1:8760/             → 200
```

---

## 5. Remaining Steps (User Action Required)

The code fixes are complete and pushed to `beta`. The following infrastructure steps must be completed by the user to achieve full hosted parity:

### Step A: Set Up Cloudflare Tunnel

1. Install cloudflared on the Alienware:
   ```powershell
   winget install cloudflare.cloudflared
   ```

2. Authenticate:
   ```powershell
   cloudflared tunnel login
   ```

3. Create the tunnel:
   ```powershell
   cloudflared tunnel create adept-ui-beta
   ```

4. Note the tunnel ID from the output, then update `config/cloudflared/adept-ui-beta-tunnel.yml`:
   - Replace `<TUNNEL_ID>` with the actual tunnel ID
   - Replace the credentials-file path with the actual path

5. Create DNS route:
   ```powershell
   cloudflared tunnel route dns adept-ui-beta api-beta.adeptui.org
   ```

6. Start the tunnel:
   ```powershell
   .\Start-CloudflareTunnel.ps1
   ```

7. Verify: `https://api-beta.adeptui.org/api/healthz` should return `{"status":"ok"}`

### Step B: Configure Vercel Environment Variable

1. Go to Vercel Project Settings → Environment Variables
2. Add `VITE_API_BASE` = `https://api-beta.adeptui.org` (Production environment)
3. Trigger a new deployment (the latest push should auto-deploy)

### Step C: Verify Hosted Parity

After the tunnel is running and Vercel env is set:
1. Visit `https://adeptui.vercel.app`
2. Verify no "Studio API partially available" banner
3. Verify hero imagery loads
4. Verify project list populates
5. Verify Co-Director launches
6. Verify Timeline opens with tracks

---

## 6. Commits

| SHA | Description |
|---|---|
| `efb5e1c` | Central API origin abstraction + Vercel hosted beta parity |
| `f9397c0` | Preserve vercel.json framework config + add SPA rewrites |
| `58daef9` | Commit all Aurora visual assets to git for Vercel deployment |

---

## 7. Verdict

**NO-GO — VERCEL HOSTED BETA PARITY INCOMPLETE**

The code fixes are complete and pushed. However, full hosted product GO requires:
1. Cloudflare Tunnel running (user infrastructure setup)
2. `VITE_API_BASE` configured in Vercel
3. Hosted Playwright certification passing
4. Visual parity confirmed against local Beta

Once the user completes Steps A-C above, the hosted certification can proceed to GO.
