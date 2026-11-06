#!/usr/bin/env bash
# Installs the newest TruffleHog release that has been public for at least 7 days.
#
# Usage: install_trufflehog.sh [-b BINDIR]     (default BINDIR: ~/.local/bin)
#
# TruffleHog backs the pre-commit secret scan (ci/secrets_detector/). Needs: curl, tar,
# and sha256sum or shasum. Linux and macOS only; Windows users should follow
# https://github.com/trufflesecurity/trufflehog#installation
#
# Why it works this way:
# - The 7-day minimum age gives the community time to notice and yank a compromised
#   release before we install it. Age is measured from the release's published_at.
# - The upstream scripts/install.sh is deliberately NOT used: it is fetched from a
#   moving branch, so the code we execute could change underneath a pinned version.
#   This script downloads the release tarball itself and checks its SHA-256 against
#   the release's checksums.txt. That catches corruption and a swapped tarball, but
#   both files come from the same release, so it does not defend against a
#   compromised release; the age gate is the defense for that.
# - Nothing is installed unless every earlier step succeeded, and the temp dir is
#   removed on exit.

set -euo pipefail

readonly MIN_AGE_DAYS=7
readonly REPO="trufflesecurity/trufflehog"

die() { echo "install_trufflehog: $*" >&2; exit 1; }

bindir="$HOME/.local/bin"
while getopts "b:" opt; do
  case "$opt" in
    b) bindir="$OPTARG" ;;
    *) die "usage: $0 [-b BINDIR]" ;;
  esac
done

case "$(uname -s)" in
  Linux)  os=linux ;;
  Darwin) os=darwin ;;
  *) die "unsupported OS '$(uname -s)'; see https://github.com/$REPO#installation" ;;
esac
case "$(uname -m)" in
  x86_64 | amd64)  arch=amd64 ;;
  aarch64 | arm64) arch=arm64 ;;
  *) die "unsupported CPU architecture '$(uname -m)'" ;;
esac

if command -v sha256sum >/dev/null 2>&1; then
  sha256_of() { sha256sum "$1" | awk '{print $1}'; }
elif command -v shasum >/dev/null 2>&1; then
  sha256_of() { shasum -a 256 "$1" | awk '{print $1}'; }
else
  die "need sha256sum or shasum to verify the download"
fi

fetch() { # fetch URL OUTPUT_FILE
  curl --proto '=https' --tlsv1.2 --silent --show-error --fail --location \
    --retry 3 --output "$2" "$1"
}

tmpdir=$(mktemp -d)
trap 'rm -r -- "$tmpdir"' EXIT

# Cutoff as an ISO-8601 UTC timestamp, which compares correctly as a plain string
# against the API's published_at values. GNU date takes -d, BSD/macOS date takes -r.
cutoff_epoch=$(( $(date +%s) - MIN_AGE_DAYS * 86400 ))
cutoff=$(date -u -d "@$cutoff_epoch" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
  || date -u -r "$cutoff_epoch" +%Y-%m-%dT%H:%M:%SZ)

# Release list is parsed with awk instead of jq/python because neither is guaranteed
# on every machine this runs on. It relies on the API's pretty-printed JSON, where
# release-level keys are indented exactly 4 spaces (nested objects are deeper), and on
# published_at appearing after draft and prerelease. If that format ever changes, no
# tag is selected and the script fails below rather than installing something wrong.
# `sort -V` picks the highest version, not the most recent, so a late patch release
# of an older line cannot win.
fetch "https://api.github.com/repos/$REPO/releases?per_page=100" "$tmpdir/releases.json"
tag=$(awk -v cutoff="$cutoff" '
  /^    "tag_name":/     { gsub(/[",]/, "", $2); tag = $2 }
  /^    "draft":/        { draft = $2 }
  /^    "prerelease":/   { prerelease = $2 }
  /^    "published_at":/ {
    gsub(/[",]/, "", $2)
    if (draft == "false," && prerelease == "false," && $2 <= cutoff \
        && tag ~ /^v[0-9]+\.[0-9]+\.[0-9]+$/) print tag
  }' "$tmpdir/releases.json" | sort -V | tail -n 1)
[ -n "$tag" ] || die "no release at least $MIN_AGE_DAYS days old (published on or before $cutoff) found"

version="${tag#v}"
tarball="trufflehog_${version}_${os}_${arch}.tar.gz"
base_url="https://github.com/$REPO/releases/download/$tag"
echo "install_trufflehog: selected $tag (newest published on or before $cutoff)"

fetch "$base_url/$tarball" "$tmpdir/$tarball"
fetch "$base_url/trufflehog_${version}_checksums.txt" "$tmpdir/checksums.txt"

# Require exactly one 64-hex-digit entry for our tarball, then compare.
expected=$(awk -v name="$tarball" '$2 == name { print $1 }' "$tmpdir/checksums.txt")
[[ "$expected" =~ ^[0-9a-f]{64}$ ]] || die "no valid checksum entry for $tarball in checksums.txt"
actual=$(sha256_of "$tmpdir/$tarball")
[ "$actual" = "$expected" ] || die "checksum mismatch for $tarball (expected $expected, got $actual)"

# Extract only the one member we want, into an empty directory.
mkdir "$tmpdir/extracted"
tar --no-same-owner -xzf "$tmpdir/$tarball" -C "$tmpdir/extracted" trufflehog

mkdir -p -- "$bindir"
install -m 0755 "$tmpdir/extracted/trufflehog" "$bindir/trufflehog"

# --version prints to stderr in some releases, hence 2>&1.
"$bindir/trufflehog" --version 2>&1 | grep -qF "$version" \
  || die "installed binary at $bindir/trufflehog does not report version $version"
echo "install_trufflehog: installed $bindir/trufflehog ($tag)"

case ":$PATH:" in
  *":$bindir:"*) ;;
  *) echo "install_trufflehog: NOTE: $bindir is not on your PATH; add it so the pre-commit scan can find trufflehog." ;;
esac
