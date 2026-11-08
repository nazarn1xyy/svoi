#!/usr/bin/env bash
# Apply repo merge settings and main protection from .github/settings (FRONTEND.md section 6).
# Usage: infra/github-settings.sh [owner/repo]   needs gh with admin rights on the repo.
set -euo pipefail

repo="${1:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"
root="$(git rev-parse --show-toplevel)"

gh api --method PATCH "repos/${repo}" --input "${root}/.github/settings/repo.json" >/dev/null
gh api --method PUT "repos/${repo}/branches/main/protection" \
  --input "${root}/.github/settings/branch-protection.json" >/dev/null
echo "applied settings and main protection to ${repo}"
