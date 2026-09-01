#!/usr/bin/env bash
set -euo pipefail

command -v trufflehog >/dev/null 2>&1 || {
  echo "ERROR: trufflehog not installed — cannot scan staged changes for secrets." >&2
  echo "Install: https://github.com/trufflesecurity/trufflehog#installation" >&2
  echo "(Deliberate bypass, use with care: git commit --no-verify)" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../.."

# The credential file setup_auth.py writes, by name. *.env is gitignored, but
# `git add -f` (or a rename) could still stage it — this catches that.
# NOTE: no `grep -q`. Under `set -o pipefail`, grep -q exits on first match,
# git gets SIGPIPE (141), and pipefail would report that as "no match" — the
# guard would silently NOT fire on large diffs. Reading to EOF (>/dev/null)
# avoids it. --diff-filter=ACMR so a rename INTO the name is caught too.
if git diff --cached --name-only --diff-filter=ACMR \
     | grep -iE '(^|/)mongodb_credentials\.env$' >/dev/null; then
  echo "ERROR: refusing to stage mongodb_credentials.env — it holds a live MongoDB credential." >&2
  exit 1
fi

# Deliberately no path exclusion here (unlike secret-scan-full.sh's
# secret-scan-exclude.txt). A hit in a staged diff is far more likely a
# freshly pasted real credential, so this scan is exclusion-free by design;
# only the full-history scan excludes the known placeholder-bearing files.
#
# Known quirk: `git diff --cached` includes *removed* lines, so a commit
# that deletes a known placeholder (e.g. cleaning a doc) re-feeds that
# string to trufflehog and gets blocked too. Use --no-verify for known fakes.
git diff --cached --no-color | trufflehog stdin --no-verification --fail --no-update
