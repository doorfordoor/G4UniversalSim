#!/usr/bin/env bash
# Start the isolated Linux X11 verification host for the J3 candidate (R3).
#
# Lifecycle contract (see docs/collab/outbox/20261104-j3-linux-candidate-r3.md):
#   * the production GUI is the primary child and its real exit code is kept;
#   * GUI exit 0 ends the host normally; helpers are then stopped in reverse
#     start order and reported as terminated, never as "exited 0";
#   * a helper exiting before the GUI is a failure (exit 6);
#   * STOP with the GUI alive is an explicit abort: outcome=stopped_by_request,
#     gui_alive_at_stop=true, and the GUI is terminated by this launcher;
#   * every child's actual exit code and termination reason is recorded in
#     receipt.json; remaining_owned must be empty after cleanup.
#
# J3_R2_TEST_MODE=1 replaces the four real commands with short-lived fake
# children (no X server, no window, no preflight) so lifecycle_test.py can
# exercise the supervision logic deterministically.

set -Eeuo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${G4USIM_REPO:-$(cd "$KIT/../../.." && pwd)}"
ASSETS="${J3_R2_ASSETS:-/mnt/c/Users/123/.codex/worktrees/effective-config/G4UniversalSim/out/collab}"
DEDICATED="$ASSETS/l1-linux-dedicated-xvnc-assets-246/root"
SHARED="$ASSETS/l1-linux-existing-window-vnc-246/root"
PYTHON3="${J3_R2_PYTHON3:-/usr/bin/python3}"
GUI_PYTHON="${J3_R2_GUI_PYTHON:-/home/u123/venvs/g4-j3-native-20261103/bin/python}"
GUI_LIBS="${J3_R2_GUI_LIBS:-/home/u123/g4gui-libs/usr/lib/x86_64-linux-gnu}"
RUN_ROOT="${J3_R2_RUN_ROOT:-$KIT/runs}"

# Fixed defaults, overridable per deployment. The same values are exported to
# preflight.py so it can never validate a different display than launch uses.
DISPLAY_NUM="${J3_R2_DISPLAY:-94}"
RFB_PORT="${J3_R2_RFB_PORT:-5910}"
WEB_PORT="${J3_R2_WEB_PORT:-6090}"
export J3_R2_DISPLAY="$DISPLAY_NUM" J3_R2_RFB_PORT="$RFB_PORT" J3_R2_WEB_PORT="$WEB_PORT"
TEST_MODE="${J3_R2_TEST_MODE:-0}"

RUN=""
PIDS=()
NAMES=()
GUI_INDEX=-1
declare -A EXIT_CODES=()
declare -A TERMINATION=()
CLEANED=0
OUTCOME=""
EXIT_CODE=0
GUI_ALIVE_AT_STOP=false

is_alive() {
  local state
  state="$(ps -o stat= -p "$1" 2>/dev/null | tr -d '[:space:]')" || true
  [[ -n "$state" && "${state:0:1}" != "Z" ]]
}

collect_exit() {
  local index="$1"
  local name="${NAMES[$index]}"
  local pid="${PIDS[$index]}"
  [[ -n "${EXIT_CODES[$name]+x}" ]] && return 0
  local rc=0
  wait "$pid" 2>/dev/null || rc=$?
  EXIT_CODES["$name"]="$rc"
}

start_child() {
  local name="$1"
  shift
  local log="$RUN/logs/$(printf '%02d' "${#PIDS[@]}")-$name.log"
  "$@" >>"$log" 2>&1 &
  local pid=$!
  PIDS+=("$pid")
  NAMES+=("$name")
  if [[ "$name" == "production-gui" ]]; then
    GUI_INDEX=$(( ${#PIDS[@]} - 1 ))
  fi
  echo "$name $pid" >>"$RUN/children.txt"
}

write_receipt() {
  local launcher_exit="$1"
  "$PYTHON3" - "$RUN" "$launcher_exit" "$OUTCOME" "$TEST_MODE" "${PIDS[*]}" <<'PY'
import json, os, sys, time
from pathlib import Path

run = Path(sys.argv[1])
launcher_exit = int(sys.argv[2])
outcome = sys.argv[3]
test_mode = sys.argv[4] == "1"
pid_list = [int(p) for p in sys.argv[5].split()]

children = []
children_file = run / "children.txt"
if children_file.exists():
    for line in children_file.read_text(encoding="utf-8").splitlines():
        name, _, pid = line.partition(" ")
        if name:
            children.append({"name": name, "pid": int(pid)})

def env_name(name):
    return name.replace("-", "_")

def reason(name):
    return os.environ.get(f"RECEIPT_REASON_{env_name(name)}", "unknown")

def code(name):
    raw = os.environ.get(f"RECEIPT_CODE_{env_name(name)}", "")
    return int(raw) if raw.lstrip("-").isdigit() else None

rows = []
for child in children:
    rows.append({
        "name": child["name"],
        "pid": child["pid"],
        "exit_code": code(child["name"]),
        "termination_reason": reason(child["name"]),
        "alive_after_cleanup": Path(f"/proc/{child['pid']}").exists(),
    })

receipt = {
    "schema": "g4usim_j3_linux_candidate_r3_run",
    "test_mode": test_mode,
    "native_window_started": not test_mode,
    "run_dir": str(run),
    "started_utc": (run / "started.txt").read_text(encoding="utf-8").strip()
    if (run / "started.txt").exists() else None,
    "finished_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "display": os.environ.get("J3_R2_DISPLAY"),
    "rfb_port": os.environ.get("J3_R2_RFB_PORT"),
    "web_port": os.environ.get("J3_R2_WEB_PORT"),
    "outcome": outcome,
    "launcher_exit": launcher_exit,
    "stop_requested": (run / "STOP").exists(),
    "gui_alive_at_stop": os.environ.get("RECEIPT_GUI_ALIVE_AT_STOP") == "true",
    "owned_pids": pid_list,
    "processes": rows,
    "remaining_owned": [row["pid"] for row in rows if row["alive_after_cleanup"]],
}
(run / "receipt.json").write_text(json.dumps(receipt, indent=2) + os.linesep, encoding="utf-8")
print("receipt: " + str(run / "receipt.json"))
PY
}

cleanup() {
  local trap_rc=$?
  if [[ "$CLEANED" -eq 1 ]]; then return; fi
  CLEANED=1
  trap - EXIT INT TERM

  if [[ -z "$RUN" ]]; then
    exit "$trap_rc"
  fi
  set +e

  local index
  local reverse=()
  for (( index = ${#PIDS[@]} - 1; index >= 0; index-- )); do
    reverse+=("$index")
  done

  # Reverse start order: GUI first, then websockify / twm / Xvnc.
  for index in "${reverse[@]}"; do
    local name="${NAMES[$index]}" pid="${PIDS[$index]}"
    if is_alive "$pid"; then
      case "$name" in
        production-gui)
          case "$OUTCOME" in
            stopped_by_request) TERMINATION["$name"]="terminated_by_stop_request" ;;
            helper_exited_unexpectedly) TERMINATION["$name"]="terminated_after_peer_exit" ;;
            *) TERMINATION["$name"]="terminated_after_launcher_exit" ;;
          esac
          ;;
        *)
          case "$OUTCOME" in
            stopped_by_request) TERMINATION["$name"]="terminated_after_stop_request" ;;
            helper_exited_unexpectedly) TERMINATION["$name"]="terminated_after_peer_exit" ;;
            gui_exited_normally|gui_exit_nonzero) TERMINATION["$name"]="terminated_after_gui_exit" ;;
            *) TERMINATION["$name"]="terminated_after_launcher_exit" ;;
          esac
          ;;
      esac
      kill -TERM "$pid" 2>/dev/null
    else
      if [[ "$name" == "production-gui" ]]; then
        case "$OUTCOME" in
          gui_exited_normally) TERMINATION["$name"]="exited_normally" ;;
          gui_exit_nonzero) TERMINATION["$name"]="exited_nonzero" ;;
          *) TERMINATION["$name"]="${TERMINATION[$name]:-exited_early}" ;;
        esac
      else
        TERMINATION["$name"]="${TERMINATION[$name]:-exited_early}"
      fi
    fi
  done

  local attempt alive
  for attempt in $(seq 1 50); do
    alive=0
    for index in "${!PIDS[@]}"; do
      is_alive "${PIDS[$index]}" && alive=1
    done
    if [[ "$alive" -eq 0 ]]; then break; fi
    sleep 0.2
  done
  for index in "${reverse[@]}"; do
    local name="${NAMES[$index]}" pid="${PIDS[$index]}"
    if is_alive "$pid"; then
      kill -KILL "$pid" 2>/dev/null
      TERMINATION["$name"]="killed_after_timeout"
    fi
done

  for index in "${reverse[@]}"; do
    local name="${NAMES[$index]}"
    collect_exit "$index"
    if [[ -z "${TERMINATION[$name]:-}" ]]; then
      TERMINATION["$name"]="exited"
    fi
    local env_name="${name//-/_}"
    export "RECEIPT_CODE_${env_name}=${EXIT_CODES[$name]}"
    export "RECEIPT_REASON_${env_name}=${TERMINATION[$name]}"
  done
  export RECEIPT_GUI_ALIVE_AT_STOP="$GUI_ALIVE_AT_STOP"

  local final_rc="$EXIT_CODE"
  if [[ "$trap_rc" -ne 0 && "$final_rc" -eq 0 ]]; then final_rc="$trap_rc"; fi
  write_receipt "$final_rc"
  echo "launch: outcome=$OUTCOME launcher_exit=$final_rc"
  exit "$final_rc"
}

trap cleanup EXIT INT TERM

if [[ "$TEST_MODE" != "1" ]]; then
  if ! "$PYTHON3" "$KIT/preflight.py" >"$KIT/preflight.out" 2>&1; then
    cat "$KIT/preflight.out"
    echo "launch: preflight failed; refusing to start any service" >&2
    exit 3
  fi
fi

mkdir -p "$RUN_ROOT"
RUN="$RUN_ROOT/$(date +%Y%m%d-%H%M%S-%N)"
mkdir -p "$RUN/logs"
STATE_DIR="${J3_R2_STATE_DIR:-$RUN/state}"
echo "$RUN" >"$RUN_ROOT/latest.txt"
date -u +%Y-%m-%dT%H:%M:%SZ >"$RUN/started.txt"
{
  echo "run=$RUN"
  echo "test_mode=$TEST_MODE"
  echo "display=:$DISPLAY_NUM rfb=$RFB_PORT web=$WEB_PORT"
} | tee "$RUN/launch.txt"

if [[ "$TEST_MODE" == "1" ]]; then
  helper_sleep="${J3_R2_TEST_HELPER_SLEEP:-300}"
  X11_CMD=(bash -c "sleep ${helper_sleep}")
  TWM_CMD=(bash -c "sleep ${helper_sleep}")
  WEB_CMD=(bash -c "sleep ${helper_sleep}")
  if [[ "${J3_R2_TEST_X11_EARLY_EXIT:-0}" == "1" ]]; then
    X11_CMD=(bash -c "sleep 0.3; exit 1")
  fi
  GUI_CMD=(bash -c "${J3_R2_TEST_GUI_CMD:-sleep 0.6; exit 0}")
  start_child xtigervnc "${X11_CMD[@]}"
  start_child twm "${TWM_CMD[@]}"
  start_child websockify "${WEB_CMD[@]}"
  start_child production-gui "${GUI_CMD[@]}"
else
  start_child xtigervnc env -u WAYLAND_DISPLAY \
    DISPLAY=":$DISPLAY_NUM" \
    LD_LIBRARY_PATH="$DEDICATED/usr/lib/x86_64-linux-gnu" \
    PATH="$DEDICATED/usr/bin:/usr/bin:/bin" \
    "$DEDICATED/usr/bin/Xtigervnc" ":$DISPLAY_NUM" \
    -geometry 1440x1000 -depth 24 -localhost -rfbport "$RFB_PORT" \
    -SecurityTypes None -nolisten tcp -ac -noreset \
    -xkbdir /usr/share/X11/xkb

  for _ in $(seq 1 50); do
    if [[ -S "/tmp/.X11-unix/X$DISPLAY_NUM" ]]; then break; fi
    sleep 0.2
  done
  if [[ ! -S "/tmp/.X11-unix/X$DISPLAY_NUM" ]]; then
    echo "launch: X server socket did not appear" >&2
    exit 4
  fi

  cat >"$RUN/twmrc" <<'TWM'
NoGrabServer
RandomPlacement
BorderWidth 1
TitleFont "fixed"
ResizeFont "fixed"
MenuFont "fixed"
IconFont "fixed"
IconManagerFont "fixed"
"F4" = m : window : f.delete
TWM
  start_child twm env -u WAYLAND_DISPLAY \
    DISPLAY=":$DISPLAY_NUM" \
    LD_LIBRARY_PATH="$DEDICATED/usr/lib/x86_64-linux-gnu" \
    PATH="$DEDICATED/usr/bin:/usr/bin:/bin" \
    "$DEDICATED/usr/bin/twm" -display ":$DISPLAY_NUM" -f "$RUN/twmrc"

  start_child websockify env -u WAYLAND_DISPLAY \
    PYTHONPATH="$SHARED/usr/lib/python3/dist-packages" \
    "$SHARED/usr/bin/websockify" --web "$SHARED/usr/share/novnc" \
    127.0.0.1:"$WEB_PORT" 127.0.0.1:"$RFB_PORT"

  start_child production-gui env -u WAYLAND_DISPLAY \
    DISPLAY=":$DISPLAY_NUM" QT_QPA_PLATFORM=xcb \
    LD_LIBRARY_PATH="$GUI_LIBS:$DEDICATED/usr/lib/x86_64-linux-gnu" \
    "$GUI_PYTHON" -B "$REPO/out/collab/j3-production-startup-r1/start_production.py" \
    --state-dir "$STATE_DIR"

  cat <<EOF
Linux verification host is starting.
  run directory : $RUN
  VNC viewer    : 127.0.0.1:$RFB_PORT  (loopback only)
  browser noVNC : http://127.0.0.1:$WEB_PORT/vnc.html
  stop          : bash "$KIT/stop.sh"
EOF
fi

GUI_NAME="${NAMES[$GUI_INDEX]}"
GUI_PID="${PIDS[$GUI_INDEX]}"
while :; do
  if ! is_alive "$GUI_PID"; then
    collect_exit "$GUI_INDEX"
    if [[ "${EXIT_CODES[$GUI_NAME]}" -eq 0 ]]; then
      OUTCOME="gui_exited_normally"
      EXIT_CODE=0
    else
      OUTCOME="gui_exit_nonzero"
      EXIT_CODE="${EXIT_CODES[$GUI_NAME]}"
    fi
    break
  fi
  if [[ -e "$RUN/STOP" ]]; then
    GUI_ALIVE_AT_STOP=true
    OUTCOME="stopped_by_request"
    EXIT_CODE=0
    break
  fi
  helper_down=0
  for index in "${!PIDS[@]}"; do
    if [[ "$index" -eq "$GUI_INDEX" ]]; then continue; fi
    if ! is_alive "${PIDS[$index]}"; then
      collect_exit "$index"
      TERMINATION["${NAMES[$index]}"]="exited_early"
      helper_down=1
      break
    fi
  done
  if [[ "$helper_down" -eq 1 ]]; then
    OUTCOME="helper_exited_unexpectedly"
    EXIT_CODE=6
    break
  fi
  sleep 0.5
done

echo "launch: supervision ended (outcome=$OUTCOME)"
exit "$EXIT_CODE"
