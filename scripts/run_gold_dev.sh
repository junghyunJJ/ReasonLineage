#!/usr/bin/env bash
# Level-1 measurement of the repoDB dev set (gold design 7): generation 0 only, one task at a
# time, then the gold summary. A task that already has a finished run in OUT is skipped. A task
# whose run stopped halfway stops the script: resume that run first, then run the script again.
#
#   scripts/run_gold_dev.sh [OUT]      # default OUT: runs/gold-dev
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/runs/gold-dev}"
export PYTHONPATH="$ROOT/src"   # this checkout's code, not an installed copy
mkdir -p "$OUT"
for task in "$ROOT"/tasks/repodb-dev/*.json; do
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
python -m reasonlineage gold --gold "$ROOT/gold/repodb-dev/gold.json" "$OUT"/*/ --out "$OUT/report.json"
