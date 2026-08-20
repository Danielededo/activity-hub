#!/usr/bin/env bash
# Upload every demo activity to a running Activity Hub API.
#
#   ./demo/load.sh                          # user 1 on localhost:8000
#   API=http://host:8000/api USER_ID=2 ./demo/load.sh
#   ./demo/load.sh demo/generated           # a different directory
set -euo pipefail

API="${API:-http://localhost:8000/api}"
USER_ID="${USER_ID:-1}"
DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/activities}"

if [ ! -d "$DIR" ]; then
    echo "No such directory: $DIR" >&2
    exit 1
fi

body=$(mktemp)
trap 'rm -f "$body"' EXIT

uploaded=0
duplicates=0
failed=0

for file in "$DIR"/*.tcx "$DIR"/*.gpx; do
    [ -e "$file" ] || continue
    status=$(curl -sS -o "$body" -w '%{http_code}' \
        -F "file=@${file}" "${API}/upload?user_id=${USER_ID}")
    name=$(basename "$file")

    case "$status" in
        201) uploaded=$((uploaded + 1)); printf '  ok       %s\n' "$name" ;;
        409) duplicates=$((duplicates + 1)); printf '  dup      %s\n' "$name" ;;
        *)   failed=$((failed + 1)); printf '  HTTP %s  %s: %s\n' "$status" "$name" "$(cat "$body")" ;;
    esac
done

printf '\n%d uploaded, %d already present, %d failed\n' "$uploaded" "$duplicates" "$failed"
[ "$failed" -eq 0 ]
