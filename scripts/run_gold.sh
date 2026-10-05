#!/usr/bin/env bash
# Level-1 measurement of a gold set (gold design 7, gold v0 design 4.5): generation 0 only, one task at
# a time, then the gold summary (report.json) and the level-1 analysis (analysis.md). A task that already
# has a finished run in OUT is skipped. A task whose run stopped halfway stops the script: resume that run
# first, then run the script again.
#
#   scripts/run_gold.sh SET [OUT]      # SET: a folder under tasks/ and gold/, e.g. repodb-dev; default OUT: runs/gold-SET
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SET="${1:?usage: scripts/run_gold.sh SET [OUT]}"
OUT="${2:-$ROOT/runs/gold-$SET}"
export PYTHONPATH="$ROOT/src"   # this checkout's code, not an installed copy
if ! compgen -G "$ROOT/tasks/$SET/*.json" > /dev/null; then
  echo "no task files in tasks/$SET; build the set first" >&2
  exit 1
fi
mkdir -p "$OUT"
for task in "$ROOT"/tasks/"$SET"/*.json; do
  id="$(basename "$task" .json)"
  if compgen -G "$OUT/*-$id/result.json" > /dev/null; then
    echo "skip $id: already finished"
    continue
  fi
  if compgen -G "$OUT/*-$id/header.json" > /dev/null; then
    echo "stop: $id has a run in $OUT that did not finish; resume it with" \
         "'PYTHONPATH=$ROOT/src python -m reasonlineage resume <run folder>', then run this script again" >&2
    exit 1
  fi
  python -m reasonlineage run "$task" --generations 0 --seed 1 --out "$OUT"
done
python -m reasonlineage gold --gold "$ROOT/gold/$SET/gold.json" "$OUT"/*/ --out "$OUT/report.json" \
  --analysis "$OUT/analysis.md"
