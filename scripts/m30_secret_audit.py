"""M3.0 Completion Phase 12 secret + trace audit.

Prints only redacted findings. Never writes or echoes a secret value.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    ".turbo",
    "data",
    "test-results",
    "playwright-report",
}

TEXT_SUFFIXES = {
    ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".py", ".ts", ".tsx",
    ".js", ".jsx", ".mjs", ".cjs", ".log", ".env", ".ini", ".cfg", ".toml",
    ".html", ".css", ".ps1", ".sh", ".sql", ".xml",
}

SENSITIVE_NAME = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)", re.I)


def run(args):
    proc = subprocess.run(
        args, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def redact(value):
    if len(value) <= 8:
        return "****"
    return "%s...%s (len=%d)" % (value[:4], value[-4:], len(value))


def parse_env(path):
    out = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            out[name] = value
    return out


def iter_worktree_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() in TEXT_SUFFIXES or fn.startswith(".env"):
                yield p


def main():
    report = {}

    env_path = ROOT / ".env"
    env_vars = parse_env(env_path)
    secrets = {}
    for name, value in env_vars.items():
        if SENSITIVE_NAME.search(name) and len(value) >= 12:
            secrets[name] = value

    report["env_file_present"] = env_path.exists()
    report["env_secret_names"] = sorted(secrets)
    report["env_secret_redacted"] = dict((n, redact(v)) for n, v in secrets.items())

    code, out = run(["git", "check-ignore", "-v", ".env"])
    report["env_gitignored"] = code == 0
    report["env_gitignore_rule"] = out.strip()

    _, tracked = run(["git", "ls-files", "--", ".env", "*/.env"])
    report["env_tracked_paths"] = [l for l in tracked.splitlines() if l.strip()]

    _, staged = run(["git", "diff", "--cached", "--name-only"])
    staged_lines = [l for l in staged.splitlines() if l.strip()]
    report["staged_paths_count"] = len(staged_lines)
    report["env_staged"] = any(l.endswith(".env") for l in staged_lines)

    ignore_checks = {}
    targets = [
        "artifacts/",
        "artifacts/m30a-fal/seedance_t2v_4s_480p.mp4",
        "artifacts/m30a-fal/live_proof_summary.json",
        "artifacts/functional-audit/logs/api.log",
        "data/",
        "test-results/",
        "playwright-report/",
        ".env",
    ]
    for target in targets:
        c, o = run(["git", "check-ignore", "-v", target])
        rule = o.strip().split("\t")[0] if c == 0 else None
        ignore_checks[target] = {"ignored": c == 0, "rule": rule}
    report["ignore_checks"] = ignore_checks

    _, tracked_art = run(["git", "ls-files", "--", "artifacts", "data"])
    report["tracked_artifact_or_data_paths"] = [l for l in tracked_art.splitlines() if l.strip()]

    hits = dict((name, []) for name in secrets)
    scanned = 0
    for path in iter_worktree_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == ".env" or rel.endswith("/.env"):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        for name, value in secrets.items():
            if value in text:
                hits[name].append(rel)
    report["worktree_files_scanned"] = scanned
    report["worktree_value_hits"] = dict((k, v) for k, v in hits.items() if v)

    history = {}
    for name, value in secrets.items():
        c, o = run(["git", "log", "--all", "--oneline", "-S", value, "--max-count=20"])
        history[name] = [l for l in o.splitlines() if l.strip()]
    report["git_history_value_hits"] = dict((k, v) for k, v in history.items() if v)

    pattern_defs = {
        "authorization_header": re.compile(r"Authorization\s*[:=]\s*[\"']?(Key|Bearer)\s+\S", re.I),
        "fal_key_assignment": re.compile(r"\bFAL_(?:API_)?KEY\s*[:=]\s*[\"']?[A-Za-z0-9]", re.I),
        "uuid_colon_hex": re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:[0-9a-f]{16,}\b", re.I
        ),
    }
    pattern_hits = dict((k, []) for k in pattern_defs)
    for sub in ("docs", "artifacts", "logs", "scripts", "studio-api", "studio-web", "tests", "config"):
        base = ROOT / sub
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                if p.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                rel = p.relative_to(ROOT).as_posix()
                for label, rx in pattern_defs.items():
                    for m in rx.finditer(text):
                        line_no = text.count("\n", 0, m.start()) + 1
                        snippet = m.group(0)
                        window = text[m.start(): m.start() + 400]
                        real = any(v in window for v in secrets.values())
                        pattern_hits[label].append(
                            {
                                "path": rel,
                                "line": line_no,
                                "shape": redact(snippet) if real else snippet[:60],
                                "contains_real_secret": real,
                            }
                        )
    report["pattern_hits_counts"] = dict((k, len(v)) for k, v in pattern_hits.items())
    real_hits = []
    for v in pattern_hits.values():
        for h in v:
            if h["contains_real_secret"]:
                real_hits.append(h)
    report["pattern_hits_with_real_secret"] = real_hits
    report["pattern_hits_sample"] = dict((k, v[:15]) for k, v in pattern_hits.items() if v)

    _, trace_tracked = run(["git", "ls-files", "--", "*.zip", "*.webm", "*.mp4", "*trace*"])
    report["tracked_trace_media_paths"] = [l for l in trace_tracked.splitlines() if l.strip()]

    out_path = ROOT / "artifacts" / "functional-audit" / "m30-secret-audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
