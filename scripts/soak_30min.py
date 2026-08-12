"""Adept UI Beta — 30-minute active soak monitor (Python, no shell timeout)."""
import json
import time
import urllib.request
from datetime import datetime, timezone

API = "http://127.0.0.1:8758"
WEB = "http://127.0.0.1:8760"
LOG = r"C:\AdeptFilmWorks\AIVideoStudio\data\runtime\logs\beta\soak_30min_py.log"
END_AFTER = 30 * 60  # 30 minutes

def http_ok(url, timeout=10):
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return 200 <= resp.status < 500
    except Exception:
        return False

start = time.monotonic()
checks = 0
consecutive_failures = 0
min_consecutive = 0

with open(LOG, "w") as f:
    f.write(f"[{datetime.now(timezone.utc).isoformat()}] Soak started\n")

    while time.monotonic() - start < END_AFTER:
        elapsed = time.monotonic() - start
        web_ok = http_ok(f"{WEB}/__beta_web_health")
        api_ok = http_ok(f"{API}/api/healthz")
        health_ok = http_ok(f"{API}/api/health")
        all_ok = web_ok and api_ok and health_ok

        if all_ok:
            consecutive_failures = 0
        else:
            consecutive_failures += 1

        checks += 1
        elapsed_min = elapsed / 60
        msg = f"[{elapsed_min:.1f}min] web={web_ok} api={api_ok} health={health_ok} failures={consecutive_failures} checks={checks}"
        print(msg)
        f.write(msg + "\n")
        f.flush()
        time.sleep(15)

    total = time.monotonic() - start
    verdict = "SOAK_PASS" if consecutive_failures == 0 else "SOAK_FAIL"
    msg = f"[{verdict}] total_min={total/60:.1f} checks={checks} consecutive_failures={consecutive_failures}"
    print(msg)
    f.write(msg + "\n")
