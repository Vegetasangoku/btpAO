#!/usr/bin/env bash
# Arrête toute la stack de dev lancée par dev-start.sh.
# Usage : ./dev-stop.sh   (ou : npm run dev:stop)
set -uo pipefail
cd "$(dirname "$0")"

echo "=== btpAO — arrêt de la stack de dev ==="

# Celery
if pgrep -f "celery -A app.core.celery_app worker" >/dev/null 2>&1; then
  pkill -f "celery -A app.core.celery_app worker" 2>/dev/null
  echo "[celery] arrêté"
else
  echo "[celery] rien à arrêter"
fi

# Backend API (port 8000)
API_PIDS=$(lsof -ti :8000 2>/dev/null)
if [ -n "$API_PIDS" ]; then
  kill -9 $API_PIDS 2>/dev/null
  echo "[api]    arrêté"
else
  echo "[api]    rien à arrêter"
fi

# Web (port 3000)
WEB_PIDS=$(lsof -ti :3000 2>/dev/null)
if [ -n "$WEB_PIDS" ]; then
  kill -9 $WEB_PIDS 2>/dev/null
  echo "[web]    arrêté"
else
  echo "[web]    rien à arrêter"
fi

# Redis — laissé actif si géré par brew services (démarrage auto), sinon arrêté
if command -v brew >/dev/null 2>&1 && brew services list 2>/dev/null | grep -q "^redis[[:space:]].*started"; then
  echo "[redis]  laissé actif (service Homebrew — redémarre automatiquement de toute façon)"
elif redis-cli ping >/dev/null 2>&1; then
  redis-cli shutdown nosave >/dev/null 2>&1
  echo "[redis]  arrêté"
else
  echo "[redis]  rien à arrêter"
fi

echo ""
echo "Fait."
