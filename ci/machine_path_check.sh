#!/usr/bin/env bash
# Block absolute paths that identify a specific machine or user account
# (a POSIX home directory, a macOS /Users/<name>, a Windows C:\Users\<name>)
# before they reach the public mirror.
#
# Usage: ci/machine_path_check.sh [--cached | <commit>]     (default: --cached)
#
#   --cached   scan the index. Used by the pre-commit hook as an early warning.
#   <commit>   scan that commit's tree. scripts/publish.sh runs it on HEAD, which
#              is exactly what `git archive HEAD` ships, so this is the real gate.
#              The hook alone cannot be the gate: it does not run for
#              `--no-verify`, merge, cherry-pick or rebase, nor in clones where
#              core.hooksPath is unset.
#
# Exit: 0 clean, 1 findings (printed as [<commit>:]<file>:<line>:<match>),
#       2 usage or precondition error.
#
# Scope: the whole in-scope tree is scanned, not just changed lines, so a
# pre-existing hit blocks every run until it is removed. When publish.allow
# exists (the private repo), only its entries are scanned, matching what gets
# published. When it does not exist (the public clone), everything is published
# and the whole tree is scanned. That also fails safe: if publish.allow were
# deleted, private-only paths would come into scope and block instead of leaks
# passing silently.
#
# This file ships publicly (ci/ is published), and it scans itself, so examples
# in comments must use the placeholder names in PLACEHOLDER below.
#
# Deliberately NOT using `set -e` or `pipefail`: git grep and grep -v both exit 1
# for "nothing found", which would invert the meaning here. Exit status is
# computed explicitly from each command's own status instead.
#
# Requires git 2.19+ (git grep -o) and must work on bash 3.2 (macOS /bin/bash),
# so no mapfile and no empty-array expansion under `set -u`.

# ASCII-only [A-Za-z] on every platform, regardless of the caller's locale.
export LC_ALL=C

# Three branches:
#   1. POSIX /home/<name> or /Users/<name>, whose leading slash is not preceded by
#      a name character. That rejects relative paths such as "src/home/index.ts"
#      and "./Users/UserList". The one boundary character is part of the match;
#      the end-anchored PLACEHOLDER filter does not care. No trailing separator is
#      needed, so a path at end of line or before a quote is still caught.
#   2. WSL /mnt/c/Users/<name> and Git Bash /c/Users/<name>. Branch 1's boundary
#      would reject these because a drive letter precedes /Users.
#   3. Windows C:\Users\<name>, C:/Users/<name>, and the source/JSON-escaped
#      C:\\Users\\<name>.
# Case-sensitive on purpose: real POSIX home paths are lowercase /home and
# capitalized /Users, and ignoring case would flag web routes like /users/123.
# Only the Windows-style "Users" folder is matched in either case.
# /root is excluded because it identifies no one. UNC paths are excluded because
# the pattern would match escaped-backslash regex source (e.g. r'\\v\s+').
PAT='(^|[^A-Za-z0-9._-])/(home|Users)/[A-Za-z0-9._-]+|/(mnt/)?[A-Za-z]/[Uu]sers/[A-Za-z0-9._-]+|[A-Za-z]:(\\\\?|/)[Uu]sers(\\\\?|/)[A-Za-z0-9._-]+'

# Names that identify no one. Each `-o` output line ends with the matched path,
# so anchoring at the end means a placeholder cannot hide a real path elsewhere
# on the same line. Applied case-insensitively (grep -i), which also covers
# "Users" vs "users". This list is the only way to suppress a finding; give each
# addition a comment explaining why.
#   user, username, youruser, your_user, you, me, name, example, foo, bar, test
#                      documentation placeholders
#   node               conventional container user
#   shared, public, default
#                      built-in macOS and Windows profile folders
PLACEHOLDER='[/\\](home|users)[/\\]+(user|username|youruser|your_user|you|me|name|example|foo|bar|test|node|shared|public|default)$'

usage() {
  echo "usage: ${0##*/} [--cached | <commit>]" >&2
  exit 2
}

[ "$#" -le 1 ] || usage
target="${1:---cached}"
case "$target" in
  --cached) ;;
  -*) usage ;;
  *)
    # `^{commit}` also rejects a blob or tree name that merely resolves.
    git rev-parse --verify --quiet "${target}^{commit}" >/dev/null 2>&1 || {
      echo "${0##*/}: not a commit: $target" >&2
      exit 2
    }
    ;;
esac

root=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "${0##*/}: not inside a git repository" >&2
  exit 2
}
cd "$root" || exit 2

scope=(.)
if [ -f publish.allow ]; then
  scope=()
  # Same parsing as scripts/publish.sh: strip a trailing CR, trim whitespace,
  # skip blank and `#` lines. A CRLF checkout must not turn entries into
  # pathspecs that match nothing.
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    case "$line" in '' | '#'*) continue ;; esac
    scope+=("$line")
  done < publish.allow
  if [ "${#scope[@]}" -eq 0 ]; then
    echo "${0##*/}: publish.allow has no entries; refusing to run" >&2
    exit 2
  fi
fi

# --no-color: under color.ui=always git grep emits ANSI escapes even into captured
# output, which breaks the end-anchored filter below.
# Argument order matters: --cached is an option and must precede the pattern; a
# commit goes after it. After the pattern, git parses "--cached" as a revision.
if [ "$target" = "--cached" ]; then
  hits=$(git grep --no-color --cached -nIoE "$PAT" -- "${scope[@]}")
else
  hits=$(git grep --no-color -nIoE "$PAT" "$target" -- "${scope[@]}")
fi
status=$?
[ "$status" -eq 1 ] && exit 0
[ "$status" -gt 1 ] && {
  echo "${0##*/}: git grep failed (status $status)" >&2
  exit 2
}

findings=$(printf '%s\n' "$hits" | grep -viE "$PLACEHOLDER")
status=$?
case "$status" in
  0)
    printf '%s\n' "$findings"
    echo "machine-specific absolute path(s) found. Remove them or use a placeholder name." >&2
    exit 1
    ;;
  1) exit 0 ;;
  *)
    echo "${0##*/}: grep failed (status $status)" >&2
    exit 2
    ;;
esac
