#!/usr/bin/env bash
# Ask the R3 verification host to stop and report its real outcome.
#
# The exit status is derived from the launcher receipt, not from "a file exists":
#   gui_exited_normally     -> 0   (the GUI closed itself, helpers were stopped)
#   stopped_by_request      -> 0   (explicit abort; GUI was alive at STOP)
#   gui_exit_nonzero        -> 3   (GUI itself failed)
#   helper_exited_unexpectedly -> 4 (Xvnc/twm/websockify died before the GUI)
#   receipt missing         -> 5   (no bounded cleanup finished in time)
#   remaining_owned non-empty -> 6 (launcher failed to reap its own children)
set -Eeuo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON3="${J3_R2_PYTHON3:-/usr/bin/python3}"
RUN_ROOT="${J3_R2_RUN_ROOT:-$KIT/runs}"
RUN="${1:-}"
if [[ -z "$RUN" ]]; then
  if [[ -f "$RUN_ROOT/latest.txt" ]]; then
    RUN="$(cat "$RUN_ROOT/latest.txt")"
  else
    RUN="$(ls -1dt "$RUN_ROOT"/*/ 2>/dev/null | head -n 1 || true)"
    RUN="${RUN%/}"
  fi
fi
if [[ -z "$RUN" || ! -d "$RUN" ]]; then
  echo "stop: no run directory found; start the kit with launch.sh first" >&2
  exit 2
fi

report_receipt() {
  "$PYTHON3" - "$1" <<'PY'
import json, sys
from pathlib import Path
receipt = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(f"stop: outcome={receipt.get('outcome')} launcher_exit={receipt.get('launcher_exit')} "
      f"gui_alive_at_stop={receipt.get('gui_alive_at_stop')} "
      f"stop_requested={receipt.get('stop_requested')} "
      f"remaining_owned={receipt.get('remaining_owned')}")
for row in receipt.get("processes", []):
    print(f"  {row['name']}: exit={row['exit_code']} reason={row['termination_reason']}")
print(f"stop: receipt={sys.argv[1]}")
PY
}

map_status() {
  case "$1" in
    gui_exited_normally|stopped_by_request) echo 0 ;;
    gui_exit_nonzero) echo 3 ;;
    helper_exited_unexpectedly) echo 4 ;;
    *) echo 5 ;;
  esac
}

# If the launcher already finished, report the receipt instead of waiting.
if [[ -f "$RUN/receipt.json" ]]; then
  report_receipt "$RUN/receipt.json"
  remaining="$("$PYTHON3" -c 'import json,sys;print(len(json.load(open(sys.argv[1])).get("remaining_owned") or []))' "$RUN/receipt.json")"
  if [[ "$remaining" -ne 0 ]]; then
    echo "stop: launcher left $remaining owned processes; inspect $RUN/children.txt" >&2
    exit 6
  fi
  exit "$(map_status "$("$PYTHON3" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("outcome",""))' "$RUN/receipt.json")")"
fi

touch "$RUN/STOP"
echo "stop: marker written to $RUN/STOP; waiting for the launcher to clean up"
for _ in $(seq 1 150); do
  if [[ -f "$RUN/receipt.json" ]]; then
    report_receipt "$RUN/receipt.json"
    remaining="$("$PYTHON3" -c 'import json,sys;print(len(json.load(open(sys.argv[1])).get("remaining_owned") or []))' "$RUN/receipt.json")"
    if [[ "$remaining" -ne 0 ]]; then
      echo "stop: launcher left $remaining owned processes; inspect $RUN/children.txt" >&2
      exit 6
    fi
    outcome="$("$PYTHON3" -c 'import json,sys;print(json.load(open(sys.argv[1])).get("outcome",""))' "$RUN/receipt.json")"
    exit "$(map_status "$outcome")"
  fi
  sleep 0.2
done
echo "stop: no receipt after 30 s; inspect $RUN/children.txt and $RUN/logs/ (do not pkill by name)" >&2
exit 5
