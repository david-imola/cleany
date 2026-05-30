#!/usr/bin/env bash
# Lightweight launcher for Cleany on Raspberry Pi / Linux desktops.
# - ensures we run from the project directory
# - activates a virtualenv if present in common locations
# - falls back to running the app.sh script directly

set -euo pipefail

# Project root (this script lives in the project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Possible virtualenv locations (relative to project root)
CANDIDATES=("venv" ".venv" "env" "venv3" "venv-py3")
ACTIVATED=0
for v in "${CANDIDATES[@]}"; do
    if [ -f "$SCRIPT_DIR/$v/bin/activate" ]; then
        # shellcheck disable=SC1090
        source "$SCRIPT_DIR/$v/bin/activate"
        ACTIVATED=1
        break
    fi
done

# If no venv activated, try common system python venv name
if [ "$ACTIVATED" -eq 0 ] && [ -f "$HOME/.local/share/virtualenvs/cleany/bin/activate" ]; then
    # shellcheck disable=SC1090
    source "$HOME/.local/share/virtualenvs/cleany/bin/activate"
    ACTIVATED=1
fi

# Run the app via the wrapper script in a detached/backgrounded way so the
# desktop launcher doesn't need a terminal window. Output is captured to
# cleany.log in the project directory.
LOG="$SCRIPT_DIR/cleany.log"
if [ -x "$SCRIPT_DIR/app.sh" ]; then
    # Use setsid to detach and redirect stdout/stderr to a log file.
    setsid "$SCRIPT_DIR/app.sh" run >> "$LOG" 2>&1 </dev/null &
    # Give the desktop environment a success exit so it doesn't keep a launcher
    # process open. The real app continues running in background.
    exit 0
else
    echo "Cannot find $SCRIPT_DIR/app.sh or it is not executable" >&2
    exit 2
fi
