#!/usr/bin/env bash
# Level-3 measurement, stage A (weather level-3 design 6): each finished generation-0 run of the listed sets whose
# task is in GOLD is judged again under one judging condition, one task at a time. Generation 0's answers come from
# that run's record (--gen0-from stops on any answer it cannot find), so only the judging is new. Then the gold
# summary (report.json) and the analysis (analysis.md). A task that already has a finished run in OUT is skipped,
# and so is a task listed in OUT/left_out.txt (one id per line). A task whose run stopped halfway stops the script:
# resume that run first, then run the script again.
#
#   scripts/run_gold_condition.sh OUT GOLD JUDGES CONTEXT SET [SET ...]
#   e.g. scripts/run_gold_condition.sh runs/gold-weather-l3-self gold/weather-l2/gold.json self isolated weather-v1 weather-v2
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USAGE="usage: scripts/run_gold_condition.sh OUT GOLD JUDGES CONTEXT SET [SET ...]"
if [ "$#" -lt 5 ]; then
  echo "$USAGE" >&2
  exit 2
fi
OUT="$1"; GOLD="$2"; JUDGES="$3"; CONTEXT="$4"; shift 4
export PYTHONPATH="$ROOT/src"   # this checkout's code, not an installed copy
if [ ! -f "$GOLD" ]; then
  echo "no gold file $GOLD" >&2
  exit 1
fi
for SET in "$@"; do
  if ! compgen -G "$ROOT/runs/gold-$SET/*/header.json" > /dev/null; then
    echo "no generation-0 runs in runs/gold-$SET" >&2
    exit 1
  fi
done
mkdir -p "$OUT"
for SET in "$@"; do
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
      echo "stop: the generation-0 run of $id in runs/gold-$SET did not finish; its answers cannot be reused" >&2
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
    python -m reasonlineage run "$task" --gen0-from "$source" --judges "$JUDGES" --context "$CONTEXT" \
      --generations 0 --seed 1 --out "$OUT"
  done
done
python -m reasonlineage gold --gold "$GOLD" "$OUT"/*/ --out "$OUT/report.json" --analysis "$OUT/analysis.md"
