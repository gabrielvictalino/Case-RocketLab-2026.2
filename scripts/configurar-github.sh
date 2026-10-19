#!/usr/bin/env bash
# Reexecutável; não apaga rulesets ou branches existentes.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
for tool in gh rg python3; do
  command -v "$tool" >/dev/null || { echo "Instale $tool." >&2; exit 1; }
done
gh auth status
repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
admin="$(gh api "repos/$repo" --jq '.permissions.admin')"
[[ "$admin" == true ]] || { echo 'Acesso administrativo necessário.' >&2; exit 1; }
# Exige a CI já integrada: evita proteção obrigatória sem workflow na main.
gh api "repos/$repo/contents/.github/workflows/fluxo-git.yml?ref=main" >/dev/null
branches="$(gh api --paginate "repos/$repo/branches?per_page=100" --jq '.[].name')"
if ! rg -qx 'dev' <<< "$branches"; then
  main_sha="$(gh api "repos/$repo/git/ref/heads/main" --jq .object.sha)"
  gh api --method POST "repos/$repo/git/refs" -f ref=refs/heads/dev -f sha="$main_sha" >/dev/null
fi
gh api --method PATCH "repos/$repo" \
  -F allow_merge_commit=true -F allow_squash_merge=true -F allow_rebase_merge=false \
  -F delete_branch_on_merge=false -F allow_update_branch=true \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY >/dev/null
# Os formulários de issues referenciam estas labels.
labels="$(gh api --paginate "repos/$repo/labels?per_page=100" --jq '.[].name')"
for label in feat fix tarefa; do
  if ! rg -Fqx "$label" <<< "$labels"; then
    gh label create "$label" --repo "$repo" --color 1D76DB --description "Tipo de trabalho: $label"
  fi
done
existing="$(mktemp)"
trap 'rm -f "$existing"' EXIT
gh api --paginate --slurp "repos/$repo/rulesets?per_page=100" > "$existing"
for branch in main dev; do
  file=".github/rulesets/$branch.json"
  rule_id="$(python3 - "$existing" "$file" <<'PY'
import json, sys
pages = json.load(open(sys.argv[1]))
name = json.load(open(sys.argv[2]))['name']
ids = [str(r['id']) for page in pages for r in page if r['name'] == name]
if len(ids) > 1:
    raise SystemExit('Há rulesets duplicados com o mesmo nome; resolva antes de continuar.')
print(ids[0] if ids else '')
PY
)"
  if [[ -n "$rule_id" ]]; then
    gh api --method PUT "repos/$repo/rulesets/$rule_id" --input "$file" >/dev/null
  else
    gh api --method POST "repos/$repo/rulesets" --input "$file" >/dev/null
  fi
done
gh api "repos/$repo" --jq '{allow_merge_commit,allow_squash_merge,allow_rebase_merge,delete_branch_on_merge}'
gh api "repos/$repo/rulesets" --jq '.[] | {name,enforcement}'
echo "Confira: https://github.com/$repo/settings/rules"
