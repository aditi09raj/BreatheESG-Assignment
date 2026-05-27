#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
  echo "\nShutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

# Backend
cd "$ROOT/backend"
uv sync --quiet
uv run python manage.py migrate --run-syncdb -v 0
uv run python manage.py seed 2>/dev/null || true
uv run python manage.py runserver 8000 &
BACKEND_PID=$!
echo "Backend: http://localhost:8000"

# Frontend
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  echo "Installing npm deps..."
  npm install --silent
fi
npm run dev &
FRONTEND_PID=$!
echo "Frontend: http://localhost:5173"

echo "Ctrl+C to stop both"
wait
