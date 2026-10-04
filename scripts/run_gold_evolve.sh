#!/usr/bin/env bash
# Level-2 measurement (weather level-2 design 6.2): each finished generation-0 run of the listed sets whose task
# is in GOLD is replayed with GENERATIONS generations of evolution, one task at a time; then the gold summary
# (report.json) and the analysis (analysis.md). Generation 0 comes from the record and is not written again.
# A task that already has a finished run in OUT is skipped, and so is a task listed in OUT/left_out.txt (one id per
# line; a task that kept stopping is left out and reported, design 7). A task whose run stopped halfway stops the
# script: resume that run first, then run the script again.
#
#   scripts/run_gold_evolve.sh OUT GOLD GENERATIONS SET [SET ...]
#   e.g. scripts/run_gold_evolve.sh runs/gold-weather-l2 gold/weather-l2/gold.json 3 weather-v1 weather-v2
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USAGE="usage: scripts/run_gold_evolve.sh OUT GOLD GENERATIONS SET [SET ...]"
if [ "$#" -lt 4 ]; then
  echo "$USAGE" >&2
  exit 2
fi
OUT="$1"; GOLD="$2"; GENERATIONS="$3"; shift 3
export PYTHONPATH="$ROOT/src"   # this checkout's code, not an installed copy
if ! [[ "$GENERATIONS" =~ ^[1-9][0-9]*$ ]]; then
  echo "GENERATIONS must be a whole number of at least 1, not '$GENERATIONS'" >&2
  exit 2
fi
if [ ! -f "$GOLD" ]; then
  echo "no gold file $GOLD" >&2
  exit 1
fi
mkdir -p "$OUT"
for SET in "$@"; do
  if ! compgen -G "$ROOT/runs/gold-$SET/*/header.json" > /dev/null; then
    echo "no generation-0 runs in runs/gold-$SET" >&2
    exit 1
  fi
  for source in "$ROOT"/runs/gold-"$SET"/*/; do
    source="${source%/}"
    name="$(basename "$source")"
    id="${name#*-*-}"   # run folders are named <date>-<time>-<task id>
    if ! grep -qF "\"$id\":" "$GOLD"; then
      continue          # not part of this measurement
    fi
    if [ -f "$OUT/left_out.txt" ] && grep -qxF "$id" "$OUT/left_out.txt"; then
      echo "skip $id: left out after repeated stops (see $OUT/left_out.txt)"
      continue
    fi
    if [ ! -f "$source/result.json" ]; then
      echo "stop: the generation-0 run of $id in runs/gold-$SET did not finish; it cannot be replayed" >&2
      exit 1
    fi
    task="$ROOT/tasks/$SET/$id.json"
    if [ ! -f "$task" ]; then
      echo "stop: $id has a generation-0 run but no task file tasks/$SET/$id.json" >&2
      exit 1
    fi
    if compgen -G "$OUT/*-$id/result.json" > /dev/null; then
      echo "skip $id: already finished"
      continue
    fi
    if compgen -G "$OUT/*-$id/header.json" > /dev/null; then
      echo "stop: $id has a run in $OUT that did not finish; resume it with" \
           "'PYTHONPATH=$ROOT/src python -m reasonlineage resume <run folder>', then run this script again" >&2
      exit 1
    fi
    python -m reasonlineage run "$task" --replay "$source" --generations "$GENERATIONS" --out "$OUT"
  done
done
python -m reasonlineage gold --gold "$GOLD" "$OUT"/*/ --out "$OUT/report.json" --analysis "$OUT/analysis.md"
