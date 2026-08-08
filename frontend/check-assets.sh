#!/usr/bin/env bash
# Verify a page's CLIENT bundle actually loads, not just its server HTML.
#
# Why this exists: `curl localhost:3000/` returning 200 with correct-looking
# markup proves only that server rendering worked. If the webpack chunk
# manifest references a module that isn't in the bundle — which is what a
# stale/corrupted .next produces — the HTML is still perfect, hydration then
# throws "Cannot read properties of undefined (reading 'call')", and React
# blanks the entire page. A curl check sails straight past that.
#
# This pulls every /_next/static asset the page references and fails on any
# non-200, which is the signature of exactly that failure.
#
#   ./check-assets.sh                 # checks all routes
#   ./check-assets.sh /verify         # checks one
set -uo pipefail

BASE="${BASE:-http://localhost:3000}"
ROUTES=("$@")
if [ ${#ROUTES[@]} -eq 0 ]; then
  ROUTES=(/ /dashboard /verify /issuer /registry /log /supervision /channels /trust-circle)
fi

fail=0
for route in "${ROUTES[@]}"; do
  html=$(curl -s --max-time 60 "$BASE$route")
  code=$(curl -s --max-time 60 -o /dev/null -w '%{http_code}' "$BASE$route")
  if [ "$code" != "200" ]; then
    printf '  %-16s PAGE %s\n' "$route" "$code"
    fail=1
    continue
  fi

  # every script/style the document pulls from the build output
  # Backslash is excluded from the character class deliberately: these URLs
  # also appear inside escaped JS strings in the RSC payload, and capturing
  # the trailing \ produced phantom 308s on perfectly healthy font files.
  assets=$(printf '%s' "$html" \
    | grep -oE '/_next/static/[^"'\''<> \\]+' \
    | sed 's/&amp;/\&/g' \
    | sort -u)

  n=0; bad=0
  while IFS= read -r asset; do
    [ -z "$asset" ] && continue
    n=$((n + 1))
    st=$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' "$BASE$asset")
    if [ "$st" != "200" ]; then
      bad=$((bad + 1))
      printf '  %-16s MISSING %s -> %s\n' "$route" "$asset" "$st"
    fi
  done <<< "$assets"

  if [ "$bad" -eq 0 ]; then
    printf '  %-16s ok   page 200, %s assets all 200\n' "$route" "$n"
  else
    fail=1
    printf '  %-16s FAIL %s of %s assets missing\n' "$route" "$bad" "$n"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "Client bundle is broken. Usual fix: stop dev, rm -rf .next, restart."
  exit 1
fi
echo
echo "All routes serve a complete client bundle."
