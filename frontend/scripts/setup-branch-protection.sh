#!/usr/bin/env bash
# Apply identical branch protection to main and develop (card O1.2).
#
# Usage:
#   gh auth login                       # once, with a token that has 'repo' admin scope
#   OWNER=your-org REPO=afri-wealth-ai-mentor bash scripts/setup-branch-protection.sh
#
# Idempotent: re-running just re-applies the same ruleset. Requires the GitHub CLI (gh).
#
# Protection applied to each branch:
#   - No direct pushes; changes land via PR only.
#   - Require the aggregate `ci-ok` status check (from ci.yml) to pass and be up to date.
#   - Require 1 approving review; dismiss stale approvals on new commits.
#   - Require conversation resolution; block force-pushes and deletions.
#   - Enforce the rules for admins too.
set -euo pipefail

OWNER="${OWNER:?set OWNER=<github-org-or-user>}"
REPO="${REPO:?set REPO=<repo-name>}"
BRANCHES=("main" "develop")

# Required status check contexts. `ci-ok` is the aggregate gate in .github/workflows/ci.yml.
read -r -d '' PAYLOAD <<'JSON' || true
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci-ok"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true
}
JSON

for branch in "${BRANCHES[@]}"; do
  echo "Applying branch protection to ${OWNER}/${REPO}@${branch}..."
  if ! gh api "repos/${OWNER}/${REPO}/branches/${branch}" --silent 2>/dev/null; then
    echo "  ! branch '${branch}' does not exist yet — create & push it first, then re-run. Skipping."
    continue
  fi
  echo "${PAYLOAD}" | gh api \
    --method PUT \
    -H "Accept: application/vnd.github+json" \
    "repos/${OWNER}/${REPO}/branches/${branch}/protection" \
    --input - >/dev/null
  echo "  [ok] protected ${branch}"
done

echo "Done. Verify in Settings → Branches, or: gh api repos/${OWNER}/${REPO}/branches/main/protection"
