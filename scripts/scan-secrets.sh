#!/usr/bin/env bash
# Regex sweep for committed secrets across every tracked file (card O3.5).
#
# Usage:
#   bash scripts/scan-secrets.sh
#
# Uses `git grep`, so only tracked files are scanned — .gitignore'd content
# (local .env, .venv, node_modules, etc.) is never considered. Looks for
# patterns that look like real credential material: AWS access keys, PEM
# private key blocks, and provider-prefixed API keys (Groq gsk_, OpenAI sk-,
# Google AIza, Slack xox[baprs]-) that aren't obvious placeholders.
#
# Exits non-zero (and prints the offending file:line) if anything is found, so
# it can be wired into CI later; today it's a manual/local gate run before a
# security-hardening PR.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

PATTERN='AKIA[0-9A-Z]{16}'
PATTERN+='|-----BEGIN[A-Z ]*PRIVATE KEY-----'
PATTERN+='|gsk_[A-Za-z0-9]{20,}'
PATTERN+='|sk-[A-Za-z0-9]{20,}'
PATTERN+='|AIza[0-9A-Za-z_-]{35}'
PATTERN+='|xox[baprs]-[0-9A-Za-z-]{10,}'

# Applied to the MATCHED TOKEN itself (not the surrounding line) — a real key
# glued onto a "your-" prefix to look like a placeholder (as happened in
# .env.example, the incident this script exists to catch) still contains the
# unadorned key as a substring, and the pattern above matches starting at the
# key's own prefix (gsk_/sk-/AIza/...), not at "your-". So the matched token
# never includes "your-" even when the line around it does — checking the
# line, not the token, is what let that leak slip past an earlier version of
# this script. A genuine placeholder (`gsk_xxxxxxxxxxxxxxxxxxxx`,
# `sk-your-key-here`) fails the real pattern's alphanumeric-run requirement
# or is caught here because the placeholder filler *is* the matched token.
PLACEHOLDER_RE='xxx|your-|example|\.\.\.'

found=0
while IFS=: read -r file line value; do
  [ -n "$value" ] || continue
  if echo "$value" | grep -qiE "$PLACEHOLDER_RE"; then
    continue
  fi
  found=1
  echo "FOUND in ${file}:${line}: ${value}"
done < <(git grep -InoE "$PATTERN" -- . 2>/dev/null || true)

if [ "$found" -eq 1 ]; then
  echo
  echo "Secrets scan FAILED — rotate any real credentials found above, then remove them from the tree."
  exit 1
fi

tracked=$(git ls-files | wc -l)
echo "Secrets scan clean — no committed secrets found in ${tracked} tracked files."
