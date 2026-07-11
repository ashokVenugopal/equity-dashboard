#!/usr/bin/env bash
set -e

# Start both backend and frontend for development
# Backend: FastAPI on port 8000
# Frontend: Next.js on port 3000

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Fail fast if a previous (possibly orphaned) dev stack still holds the
# ports — otherwise uvicorn dies with "Address already in use" mid-start.
for port in 8000 3000; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "[ERROR] Port $port is already in use:"
        lsof -nP -iTCP:"$port" -sTCP:LISTEN | tail -n +2
        echo "[ERROR] Run 'make stop' to clear stale dev servers, then retry."
        exit 1
    fi
done

echo "[INFO] Starting equity-dashboard development servers..."

# Start backend in background
echo "[INFO] Starting FastAPI backend on :8000..."
# backend.main:app must resolve from the project root (backend/ is a
# package with absolute backend.* imports) — and use the venv python.
cd "$PROJECT_DIR" && .venv/bin/python -m backend.main &
BACKEND_PID=$!

# Start frontend in background
echo "[INFO] Starting Next.js frontend on :3000..."
cd "$PROJECT_DIR/frontend" && npm run dev &
FRONTEND_PID=$!

# Kill a process and all of its descendants, depth-first. Both servers
# are process trees (npm → next dev → next-server; uvicorn reload
# supervisor → worker) — killing only the top PID can orphan the child
# that actually holds the port.
kill_tree() {
    local pid=$1 child
    for child in $(pgrep -P "$pid" 2>/dev/null); do
        kill_tree "$child"
    done
    kill "$pid" 2>/dev/null || true
}

# Clean up both process trees. HUP included: closing the terminal
# (instead of Ctrl-C) must not leave orphaned servers holding the ports.
cleanup() {
    trap - EXIT INT TERM HUP
    echo ""
    echo "[INFO] Shutting down..."
    kill_tree $BACKEND_PID
    kill_tree $FRONTEND_PID
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo "[INFO] Done."
}
trap cleanup EXIT INT TERM HUP

# Wait for either server to exit. NOT `wait -n`: macOS ships bash 3.2,
# where that's a usage error — with `set -e` the script then dies
# seconds after launch, orphaning both servers (the original cause of
# the recurring "Address already in use").
while kill -0 $BACKEND_PID 2>/dev/null && kill -0 $FRONTEND_PID 2>/dev/null; do
    sleep 1
done
