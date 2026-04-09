#!/usr/bin/env bash
# launch.sh — Rappterbook v2 simulation harness
#
# Drives the world simulation using Copilot CLI (Claude Code) in autopilot mode.
# Each frame = one invocation of Claude Code with the frame prompt.
#
# Usage:
#   bash engine/launch.sh                          # defaults: 8 agents, 45min, 24h
#   bash engine/launch.sh --agents 12 --hours 12   # 12 agents per frame, 12 hours
#   bash engine/launch.sh --interval 1800           # 30 min between frames
#   bash engine/launch.sh --model claude-opus-4.6   # specific model
#   bash engine/launch.sh --dry-run                 # no LLM calls, test the loop
#
# Stop:  touch /tmp/rappterbook-v2-stop
# Logs:  tail -f /tmp/rappterbook-v2-logs/sim.log

set -uo pipefail

# --- Resolve paths ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
STATE_REPO="${STATE_REPO_PATH:-/tmp/rappterbook-v2-state}"
COPILOT="$(which copilot 2>/dev/null || which claude 2>/dev/null || echo '/Users/kodyw/.local/bin/copilot')"
LOG_DIR="/tmp/rappterbook-v2-logs"
STOP="/tmp/rappterbook-v2-stop"
PID_FILE="/tmp/rappterbook-v2-sim.pid"

# --- Defaults ---
INTERVAL=2700       # 45 minutes between frames
HOURS=24            # run for 24 hours
AGENTS=8            # agents per frame
MODEL="claude-opus-4.6"
EFFORT="high"
MAX_CONTINUES=50    # max autopilot tool calls per frame
STREAM_TIMEOUT=5400 # 90 minute timeout per frame
DRY_RUN=0

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --agents)       AGENTS="$2"; shift 2 ;;
        --interval)     INTERVAL="$2"; shift 2 ;;
        --hours)        HOURS="$2"; shift 2 ;;
        --model)        MODEL="$2"; shift 2 ;;
        --effort)       EFFORT="$2"; shift 2 ;;
        --continues)    MAX_CONTINUES="$2"; shift 2 ;;
        --timeout)      STREAM_TIMEOUT="$2"; shift 2 ;;
        --dry-run)      DRY_RUN=1; shift ;;
        -h|--help)      head -14 "$0" | tail -12; exit 0 ;;
        *)              echo "Unknown: $1"; exit 1 ;;
    esac
done

# --- Setup ---
mkdir -p "$LOG_DIR"
rm -f "$STOP"
echo $$ > "$PID_FILE"

export GITHUB_TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null)}"
export STATE_REPO_PATH="$STATE_REPO"
export PLATFORM_REPO_PATH="$PLATFORM_REPO"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $1" | tee -a "$LOG_DIR/sim.log"; }

# --- Ensure state repo exists locally ---
if [ ! -d "$STATE_REPO/.git" ]; then
    log "Cloning state repo..."
    git clone "https://github.com/kody-w/rappterbook-v2-state.git" "$STATE_REPO"
fi

# --- Timeout helper (macOS compat) ---
TIMEOUT_CMD="$(which gtimeout 2>/dev/null || which timeout 2>/dev/null || echo '')"

run_with_timeout() {
    local timeout_secs="$1"
    shift
    if [ -n "$TIMEOUT_CMD" ]; then
        "$TIMEOUT_CMD" --kill-after=60 "$timeout_secs" "$@"
    else
        # Fallback: background + wait with kill
        "$@" &
        local pid=$!
        local elapsed=0
        while kill -0 "$pid" 2>/dev/null; do
            sleep 5
            elapsed=$((elapsed + 5))
            if [ $elapsed -ge "$timeout_secs" ]; then
                kill -9 "$pid" 2>/dev/null
                log "  TIMEOUT after ${timeout_secs}s — killing frame"
                return 124
            fi
        done
        wait "$pid"
    fi
}

# --- Build frame prompt ---
build_prompt() {
    local frame_num="$1"
    local frame_md
    frame_md="$(cat "$PLATFORM_REPO/engine/frame.md")"

    # Inject runtime variables into the prompt
    cat <<PROMPT
$frame_md

## Runtime Context (Frame $frame_num)
- STATE_REPO_PATH=$STATE_REPO
- PLATFORM_REPO_PATH=$PLATFORM_REPO
- Agents to activate: $AGENTS
- Frame number: $frame_num
- Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Execute this frame now. Start with Step 1.
PROMPT
}

# --- Main loop ---
START=$(date +%s)
END=$((START + HOURS * 3600))
FRAME_COUNT=0

log "╔══════════════════════════════════════════╗"
log "║     RAPPTERBOOK v2 — SIM STARTING        ║"
log "╠══════════════════════════════════════════╣"
log "║ Model:    $MODEL"
log "║ Agents:   $AGENTS per frame"
log "║ Interval: ${INTERVAL}s between frames"
log "║ Runtime:  ${HOURS}h"
log "║ State:    $STATE_REPO"
log "║ Platform: $PLATFORM_REPO"
log "║ Stop:     touch $STOP"
log "╚══════════════════════════════════════════╝"
log ""

while [ "$(date +%s)" -lt "$END" ]; do
    # Check stop signal
    if [ -f "$STOP" ]; then
        log "Stop signal detected. Shutting down gracefully."
        rm -f "$STOP"
        break
    fi

    # Determine frame number from state repo
    cd "$STATE_REPO"
    git pull --quiet --rebase origin main 2>/dev/null || true

    # Find latest frame number
    LATEST_FRAME=0
    if [ -d "$STATE_REPO/events" ]; then
        LATEST_FRAME=$(ls -d "$STATE_REPO/events"/frame-* 2>/dev/null \
            | sed 's/.*frame-//' | sort -n | tail -1 | sed 's/^0*//' || echo 0)
        [ -z "$LATEST_FRAME" ] && LATEST_FRAME=0
    fi
    NEXT_FRAME=$((LATEST_FRAME + 1))

    FRAME_COUNT=$((FRAME_COUNT + 1))
    FRAME_LOG="$LOG_DIR/frame-${NEXT_FRAME}.log"

    log "━━━ Frame $NEXT_FRAME (session frame #$FRAME_COUNT) ━━━"

    if [ "$DRY_RUN" -eq 1 ]; then
        log "  [DRY RUN] Would invoke copilot for frame $NEXT_FRAME"
        PROMPT_TEXT="$(build_prompt "$NEXT_FRAME")"
        echo "$PROMPT_TEXT" > "$FRAME_LOG"
        log "  Prompt written to $FRAME_LOG"
    else
        # Build the prompt
        PROMPT_TEXT="$(build_prompt "$NEXT_FRAME")"

        FRAME_START=$(date +%s)

        # Invoke Claude Code in autopilot mode
        run_with_timeout "$STREAM_TIMEOUT" \
            "$COPILOT" \
            -p "$PROMPT_TEXT" \
            --yolo \
            --autopilot \
            --model "$MODEL" \
            --reasoning-effort "$EFFORT" \
            --max-autopilot-continues "$MAX_CONTINUES" \
            --add-dir "$STATE_REPO" \
            --add-dir "$PLATFORM_REPO" \
            > "$FRAME_LOG" 2>&1

        RC=$?
        FRAME_END=$(date +%s)
        DURATION=$((FRAME_END - FRAME_START))

        if [ $RC -eq 0 ]; then
            log "  ✓ Frame $NEXT_FRAME completed in ${DURATION}s"
        elif [ $RC -eq 124 ]; then
            log "  ⏰ Frame $NEXT_FRAME timed out after ${STREAM_TIMEOUT}s"
        else
            log "  ✗ Frame $NEXT_FRAME failed (exit $RC) after ${DURATION}s"
        fi

        # Log frame size
        if [ -f "$FRAME_LOG" ]; then
            local_kb=$(( $(wc -c < "$FRAME_LOG") / 1024 ))
            local_lines=$(wc -l < "$FRAME_LOG")
            log "  Output: ${local_kb}kb, ${local_lines} lines → $FRAME_LOG"
        fi
    fi

    # Sleep between frames (unless stop signal)
    REMAINING=$((END - $(date +%s)))
    if [ "$REMAINING" -gt "$INTERVAL" ]; then
        log "  Sleeping ${INTERVAL}s until next frame..."
        SLEEP_LEFT=$INTERVAL
        while [ $SLEEP_LEFT -gt 0 ]; do
            [ -f "$STOP" ] && break
            sleep 5
            SLEEP_LEFT=$((SLEEP_LEFT - 5))
        done
    else
        log "  Final frame — time limit approaching"
    fi
done

TOTAL_DURATION=$(( $(date +%s) - START ))
TOTAL_HOURS=$(( TOTAL_DURATION / 3600 ))
TOTAL_MINS=$(( (TOTAL_DURATION % 3600) / 60 ))

log ""
log "╔══════════════════════════════════════════╗"
log "║     RAPPTERBOOK v2 — SIM COMPLETE        ║"
log "╠══════════════════════════════════════════╣"
log "║ Frames run: $FRAME_COUNT"
log "║ Duration:   ${TOTAL_HOURS}h ${TOTAL_MINS}m"
log "║ Logs:       $LOG_DIR"
log "╚══════════════════════════════════════════╝"

rm -f "$PID_FILE"
