#!/usr/bin/env python3
"""Flag `npm audit fix` candidates that were published very recently.

Supply-chain attackers publish malicious versions and race for inclusion
via transitive-dep bumps. `npm audit fix` will pull those in without
asking. This script previews the fix plan (dry-run only, no install) and
flags any package version whose registry publish time is under a
threshold (default 7 days). Exits non-zero when anything is flagged so
this can gate CI later.

Text-format parsing is deliberate: `npm audit fix --dry-run --json` is
unreliable across npm versions; the human-readable `add X ver` /
`change X old => new` lines have been stable across npm 7-10.

Cross-platform: Mac, Linux, Windows.

Usage:
    python ci/supply_chain_hygiene.py                    # defaults: front_end, 7 days
    python ci/supply_chain_hygiene.py --threshold-days 14
    python ci/supply_chain_hygiene.py --project some/other/js/project
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PROJECT = REPO / "front_end"
DEFAULT_REGISTRY = "https://registry.npmjs.org"
DEFAULT_THRESHOLD_DAYS = 7
FETCH_WORKERS = 8
FETCH_TIMEOUT_S = 15

# `add <name> <ver>` or `change <name> <old> => <new>`
ADD_RE = re.compile(r"^add\s+(\S+)\s+(\S+)\s*$")
CHANGE_RE = re.compile(r"^change\s+(\S+)\s+\S+\s+=>\s+(\S+)\s*$")


@dataclass(frozen=True)
class Planned:
    name: str
    version: str
    action: str  # "add" or "change"


@dataclass
class Resolved:
    planned: Planned
    published_at: datetime | None
    error: str | None


def npm_bin() -> str:
    # shutil.which resolves the .cmd shim on Windows.
    resolved = shutil.which("npm")
    if not resolved:
        raise SystemExit("npm not found on PATH")
    return resolved


def run_dry_run(project: Path) -> str:
    if not (project / "package.json").exists():
        raise SystemExit(f"No package.json under {project}")
    result = subprocess.run(
        [npm_bin(), "audit", "fix", "--dry-run"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    # npm exits non-zero when vulnerabilities remain even after the dry-run
    # plan — that's not a script failure. Only bail if there's no output at
    # all, which indicates the command itself broke.
    if not result.stdout and result.returncode != 0:
        raise SystemExit(
            f"npm audit fix --dry-run failed (exit {result.returncode}):\n"
            f"{result.stderr}"
        )
    return result.stdout


def parse_plan(text: str) -> list[Planned]:
    plans: list[Planned] = []
    for line in text.splitlines():
        m = ADD_RE.match(line)
        if m:
            plans.append(Planned(name=m.group(1), version=m.group(2), action="add"))
            continue
        m = CHANGE_RE.match(line)
        if m:
            plans.append(Planned(name=m.group(1), version=m.group(2), action="change"))
    return plans


def fetch_publish_date(registry: str, name: str, version: str) -> tuple[datetime | None, str | None]:
    # Scoped names ("@scope/name") need the slash percent-encoded.
    encoded = urllib.parse.quote(name, safe="@")
    url = f"{registry.rstrip('/')}/{encoded}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_S) as resp:
            data = json.load(resp)
    except Exception as e:
        return None, f"fetch failed: {e}"
    stamp = data.get("time", {}).get(version)
    if not stamp:
        return None, f"version {version} not listed in registry time map"
    try:
        # Registry format: "2024-05-01T12:34:56.789Z"
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")), None
    except ValueError as e:
        return None, f"unparseable timestamp {stamp!r}: {e}"


def resolve_all(registry: str, plans: list[Planned]) -> list[Resolved]:
    # Dedupe (name, version) — same tuple may appear only once but be safe.
    unique = {(p.name, p.version): p for p in plans}
    resolved: dict[tuple[str, str], Resolved] = {}
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {
            pool.submit(fetch_publish_date, registry, name, ver): (name, ver)
            for (name, ver) in unique
        }
        for fut in as_completed(futures):
            key = futures[fut]
            published, err = fut.result()
            resolved[key] = Resolved(planned=unique[key], published_at=published, error=err)
    # Preserve original plan order.
    seen: set[tuple[str, str]] = set()
    ordered: list[Resolved] = []
    for p in plans:
        key = (p.name, p.version)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(resolved[key])
    return ordered


def report(resolved: list[Resolved], threshold_days: int, as_json: bool) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=threshold_days)
    flagged: list[Resolved] = []
    errors: list[Resolved] = []
    for r in resolved:
        if r.error is not None:
            errors.append(r)
        elif r.published_at is not None and r.published_at >= cutoff:
            flagged.append(r)

    if as_json:
        payload = {
            "threshold_days": threshold_days,
            "checked_at": now.isoformat(),
            "total_planned": len(resolved),
            "flagged": [
                {
                    "name": r.planned.name,
                    "version": r.planned.version,
                    "action": r.planned.action,
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                    "age_days": (now - r.published_at).days if r.published_at else None,
                }
                for r in flagged
            ],
            "errors": [
                {"name": r.planned.name, "version": r.planned.version, "error": r.error}
                for r in errors
            ],
            "all": [
                {
                    "name": r.planned.name,
                    "version": r.planned.version,
                    "action": r.planned.action,
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                    "error": r.error,
                }
                for r in resolved
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"Checked {len(resolved)} planned package version(s) against a "
              f"{threshold_days}-day freshness threshold.\n")
        if flagged:
            print(f"FLAGGED ({len(flagged)}): published within last {threshold_days} day(s)")
            for r in sorted(flagged, key=lambda x: x.published_at or now):
                age = (now - r.published_at).days if r.published_at else "?"
                print(f"  {r.planned.action:6s} {r.planned.name}@{r.planned.version}"
                      f"  published {r.published_at.isoformat() if r.published_at else '?'}"
                      f"  ({age}d ago)")
            print()
        else:
            print("No packages flagged.\n")
        if errors:
            print(f"ERRORS ({len(errors)}): could not determine publish date")
            for r in errors:
                print(f"  {r.planned.name}@{r.planned.version}: {r.error}")
            print()

    return 1 if flagged or errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", type=Path, default=DEFAULT_PROJECT,
                    help=f"Path to npm project (default: {DEFAULT_PROJECT.relative_to(REPO)})")
    ap.add_argument("--threshold-days", type=int, default=DEFAULT_THRESHOLD_DAYS,
                    help=f"Flag packages published within this many days (default: {DEFAULT_THRESHOLD_DAYS})")
    ap.add_argument("--registry", default=DEFAULT_REGISTRY,
                    help=f"npm registry base URL (default: {DEFAULT_REGISTRY})")
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    args = ap.parse_args()

    project = args.project.resolve()
    print(f"[supply-chain] Running npm audit fix --dry-run in {project} ...", file=sys.stderr)
    plan_text = run_dry_run(project)
    plans = parse_plan(plan_text)
    if not plans:
        # Zero adds/changes could mean genuinely nothing to do, OR that npm
        # changed its output format and we're parsing nothing. Distinguish
        # by looking for known "up to date" / "0 vulnerabilities" markers.
        low = plan_text.lower()
        if "0 vulnerabilities" in low or "up to date" in low or not plan_text.strip():
            print("[supply-chain] Nothing to fix. Clean.", file=sys.stderr)
            return 0
        print("[supply-chain] WARNING: parsed zero planned changes from non-empty "
              "npm output. Output format may have changed. Raw output:\n",
              file=sys.stderr)
        print(plan_text, file=sys.stderr)
        return 2

    print(f"[supply-chain] {len(plans)} planned add/change; fetching publish dates ...",
          file=sys.stderr)
    resolved = resolve_all(args.registry, plans)
    return report(resolved, args.threshold_days, args.json)


if __name__ == "__main__":
    sys.exit(main())
