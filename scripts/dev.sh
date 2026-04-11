#!/usr/bin/env bash
set -e

# Start both backend and frontend for development
# Backend: FastAPI on port 8000
# Frontend: Next.js on port 3000

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "[INFO] Starting equity-dashboard development servers..."

# Start backend in background
echo "[INFO] Starting FastAPI backend on :8000..."
cd "$PROJECT_DIR/backend" && python main.py &
BACKEND_PID=$!

# Start frontend in background
echo "[INFO] Starting Next.js frontend on :3000..."
cd "$PROJECT_DIR/frontend" && npm run dev &
FRONTEND_PID=$!

# Trap to clean up both processes
cleanup() {
    echo ""
    echo "[INFO] Shutting down..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait $BACKEND_PID 2>/dev/null || true
    wait $FRONTEND_PID 2>/dev/null || true
    echo "[INFO] Done."
}
trap cleanup EXIT INT TERM

# Wait for either to exit
wait -n $BACKEND_PID $FRONTEND_PID
