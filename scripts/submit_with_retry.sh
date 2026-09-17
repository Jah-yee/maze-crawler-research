#!/usr/bin/env bash
set -euo pipefail

file="main.py"
message="${1:-v1 public top2 jump bfs baseline}"
if [[ $# -ge 1 && -f "$1" ]]; then
  file="$1"
  shift
  message="${*:-submit ${file}}"
fi
attempts="${ATTEMPTS:-8}"

for attempt in $(seq 1 "$attempts"); do
  echo "submit attempt ${attempt}/${attempts}"
  if .venv/bin/kaggle competitions submit maze-crawler -f "$file" -m "$message"; then
    .venv/bin/kaggle competitions submissions maze-crawler
    exit 0
  fi
  sleep "$((attempt * 5))"
done

echo "submission failed after ${attempts} attempts" >&2
exit 1
