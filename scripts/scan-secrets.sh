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

# A real key does not contain the literal word "your"/"xxx"/"example"/a
# "<placeholder>" token — that's how every genuine placeholder in this repo
# is written (see .env.example, research/README.md).
PLACEHOLDER_RE='your-|xxx|example|<[a-z_-]+>|\.\.\.'

matches=$(git grep -InE "$PATTERN" -- . 2>/dev/null | grep -viE "$PLACEHOLDER_RE" || true)

if [ -n "$matches" ]; then
  echo "FOUND potential committed secrets:"
  echo "$matches"
  echo
  echo "Secrets scan FAILED — rotate any real credentials found above, then remove them from the tree."
  exit 1
fi

tracked=$(git ls-files | wc -l)
echo "Secrets scan clean — no committed secrets found in ${tracked} tracked files."
