#!/usr/bin/env python3
"""Regenerate THIRD_PARTY_LICENSES.txt at the repo root.

Collects license metadata + full license text from both the Python backend
(via pip-licenses, run against the uv-managed .venv) and the JS frontend
(via npx license-checker, production deps only), then writes a single combined
file at the repo root, overwriting any existing one.

Cross-platform: Mac, Linux, Windows.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "back_end"
FRONTEND = REPO / "front_end"
# The venv's location varies by machine (<repo>/.venv on the host, absolute in the
# devcontainer). UV_PROJECT_ENVIRONMENT is the variable uv itself reads, so one setting
# steers both `uv sync` and this script. Joining onto REPO leaves absolute values as-is.
VENV = REPO / (os.environ.get("UV_PROJECT_ENVIRONMENT") or ".venv")
FORMAT_SPEC = Path(__file__).resolve().parent / "license_checker_format.json"
OUTPUT = REPO / "THIRD_PARTY_LICENSES.txt"

SEP = "=" * 70
SUB = "-" * 70


def venv_bin(name: str) -> Path:
    # Windows venvs use Scripts/ with .exe; POSIX uses bin/.
    if os.name == "nt":
        return VENV / "Scripts" / f"{name}.exe"
    return VENV / "bin" / name


# Some wheels bundle non-license binary blobs as their "license file" — e.g.
# cyclonedx-python-lib ships a marshalled .pyc fragment that pip-licenses will
# happily emit verbatim. A marshalled code object embeds co_filename, the
# absolute path of the machine it was built on, so copying such a blob into
# this file leaks the build machine's directory layout. Real license text never
# contains control characters, so that's the discriminator; the absolute-path
# scrub on everything else is belt-and-braces.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ABS_PATH = re.compile(r"/(?:Users|home|root)/\S+|[A-Za-z]:\\(?:Users|Documents and Settings)\\\S+")
_UNREADABLE = "(license file in the package is not readable text; consult the URL above)"


def _sanitize_license_text(text: str) -> str:
    if _CONTROL_CHARS.search(text):
        return _UNREADABLE
    return _ABS_PATH.sub("<local-path>", text)


def collect_backend() -> str:
    pip_licenses = venv_bin("pip-licenses")
    if not pip_licenses.exists():
        raise SystemExit(
            f"pip-licenses not found at {pip_licenses}\n"
            "Create or update the environment with `uv sync` at the repo root."
        )
    # JSON format (not plain-vertical) so each package's license text can be
    # sanitized individually; the block layout below reproduces plain-vertical's.
    result = subprocess.run(
        [
            str(pip_licenses),
            "--format=json",
            "--with-license-file",
            "--no-license-path",
            "--with-urls",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    packages = json.loads(result.stdout)

    blocks: list[str] = []
    for pkg in packages:
        lines = [
            pkg.get("Name", ""),
            pkg.get("Version", ""),
            pkg.get("License", "") or "UNKNOWN",
        ]
        url = (pkg.get("URL") or "").strip()
        if url:
            lines.append(url)
        text = _sanitize_license_text(pkg.get("LicenseText") or "")
        lines += [text or "(no license text bundled with package)", ""]
        blocks += lines
    return "\n".join(blocks)


def collect_frontend() -> str:
    npx = shutil.which("npx.cmd") if os.name == "nt" else shutil.which("npx")
    if not npx:
        raise SystemExit("npx not found on PATH. Install Node.js.")
    if not (FRONTEND / "node_modules").exists():
        raise SystemExit(
            f"{FRONTEND / 'node_modules'} missing. Run `npm install` in front_end/."
        )

    pkg = json.loads((FRONTEND / "package.json").read_text())
    self_id = f"{pkg['name']}@{pkg['version']}"

    result = subprocess.run(
        [
            npx,
            "license-checker",
            "--production",
            "--excludePackages",
            self_id,
            "--customPath",
            str(FORMAT_SPEC),
            "--json",
        ],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    blocks: list[str] = []
    for name, info in sorted(data.items()):
        text = _sanitize_license_text((info.get("licenseText") or "").strip())
        if text == "none":
            text = ""
        blocks += [
            SEP,
            name,
            f"License: {info.get('licenses', '') or 'UNKNOWN'}",
        ]
        if info.get("repository"):
            blocks.append(f"Repository: {info['repository']}")
        if info.get("publisher"):
            blocks.append(f"Publisher: {info['publisher']}")
        blocks += [SUB, text or "(no license text bundled with package)", ""]
    return "\n".join(blocks)


def main() -> int:
    print("Collecting backend (Python) licenses...", flush=True)
    backend = collect_backend()
    print("Collecting frontend (npm, production) licenses...", flush=True)
    frontend = collect_frontend()

    header = (
        "Third-Party Software Licenses\n"
        "=============================\n"
        "This file lists the open-source dependencies bundled with this software\n"
        "and their license terms. Generated by ci/generate_third_party_licenses.py.\n"
        "Do not edit by hand; re-run the script to regenerate.\n"
    )
    body = "\n".join(
        [
            header,
            "\n\n" + "#" * 70,
            "# BACKEND  (Python, uv-managed .venv)",
            "#" * 70 + "\n",
            backend,
            "\n" + "#" * 70,
            "# FRONTEND (npm, front_end production dependencies)",
            "#" * 70 + "\n",
            frontend,
        ]
    )
    # Backstop: if sanitization ever lets a binary blob or absolute path
    # through, fail loudly instead of writing it into a committed file.
    if _CONTROL_CHARS.search(body):
        raise SystemExit("generated output contains control characters; refusing to write")
    if _ABS_PATH.search(body):
        raise SystemExit("generated output contains absolute filesystem paths; refusing to write")

    OUTPUT.write_text(body, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
