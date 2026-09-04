#!/usr/bin/env bash
# Lance toute la stack de dev (Redis, Celery, API, Web) en une seule commande.
# Usage : ./dev-start.sh   (ou : npm run dev:all)
# Peut être relancé sans risque : chaque étape détecte si elle tourne déjà.
set -uo pipefail
# 29/08 : active le contrôle de tâches ("set -m") pour que chaque commande lancée
# en fond ("&") reçoive son PROPRE groupe de processus, distinct de celui du
# terminal qui lance ce script. Sans ça (comportement par défaut d'un script
# bash non-interactif), un Ctrl-C ou la fermeture du terminal envoie son signal
# à TOUT le groupe de processus -- script + celery + uvicorn + web compris --
# ce qui explique le symptôme observé en pratique (les 3 process tombant
# ensemble, parfois sans même logger un arrêt propre). nohup + disown restent
# en plus comme filets de sécurité supplémentaires (ignorent SIGHUP même si le
# process restait par hasard dans le même groupe).
set -m
cd "$(dirname "$0")"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

echo "=== btpAO — démarrage de la stack de dev ==="
echo ""

# ── 1. Redis ──────────────────────────────────────────────────────────
if redis-cli ping >/dev/null 2>&1; then
  echo "[redis]  déjà lancé (PONG)"
elif command -v brew >/dev/null 2>&1; then
  if ! brew list redis >/dev/null 2>&1; then
    echo "[redis]  non installé — installation via Homebrew (une seule fois)..."
    brew install redis
  fi
  echo "[redis]  démarrage via brew services (démarrera aussi automatiquement au prochain login)..."
  brew services start redis
  sleep 1
  redis-cli ping >/dev/null 2>&1 && echo "[redis]  ✅ OK" || echo "[redis]  ⚠️  lancé mais le ping a échoué — voir : brew services list"
elif command -v redis-server >/dev/null 2>&1; then
  echo "[redis]  démarrage (binaire trouvé, sans Homebrew)..."
  nohup redis-server --port 6379 > "$LOG_DIR/redis.log" 2>&1 &
  disown
  sleep 1
  redis-cli ping >/dev/null 2>&1 && echo "[redis]  ✅ OK" || echo "[redis]  ⚠️  lancé mais le ping a échoué — voir $LOG_DIR/redis.log"
else
  echo "[redis]  ❌ ERREUR : ni Homebrew ni redis-server trouvés sur ce Mac."
  echo "         Installez Homebrew (https://brew.sh), puis relancez ce script — il installera et lancera Redis automatiquement."
  exit 1
fi

# ── 2. Dépendances Python (celery, redis) ────────────────────────────
echo "[python] vérification de celery/redis..."
if ! python3 -c "import celery" >/dev/null 2>&1; then
  echo "[python] celery manquant — installation ciblée (n'affecte pas vos autres paquets)..."
  pip3 install "celery>=5.4.0"
fi
if ! python3 -c "import redis" >/dev/null 2>&1; then
  echo "[python] redis (client Python) manquant — installation ciblée..."
  pip3 install "redis>=5.0.4"
fi
echo "[python] ✅ OK"

# ── 3. Celery worker ──────────────────────────────────────────────────
if pgrep -f "celery -A app.core.celery_app worker" >/dev/null 2>&1; then
  echo "[celery] déjà lancé"
else
  echo "[celery] démarrage du worker..."
  # 29/08 (suite) : --pool=solo -- le pool prefork (fork() de sous-processus) provoque un
  # SIGSEGV quasi immédiat sur macOS dès qu'une tâche touche une bibliothèque native
  # (OCR / embeddings) dans le worker forké -- classe de bug connue "fork-unsafe" sur macOS.
  # solo = un seul process, aucun fork -- élimine la cause -- suffisant en dev/local (débit non
  # critique ici). À revisiter (ex: pool=threads, ou prefork sur Linux) si le débit devient un besoin réel.
  (cd apps/api && OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES nohup python3 -m celery -A app.core.celery_app worker --loglevel=info --pool=solo < /dev/null > "../../$LOG_DIR/celery.log" 2>&1 & disown)
  sleep 1
  pgrep -f "celery -A app.core.celery_app worker" >/dev/null 2>&1 && echo "[celery] ✅ lancé — logs : $LOG_DIR/celery.log" || echo "[celery] ⚠️  n'a peut-être pas démarré — voir $LOG_DIR/celery.log"
fi

# ── 3 bis. Celery Beat (planificateur) ────────────────────────────────
# Sans Beat, la synchronisation nocturne du catalogue de modèles LLM (4h00) et la purge
# RGPD (3h00) ne s'exécutent jamais en local. L'API rattrape la synchronisation du
# catalogue au démarrage si elle date de plus de 24 h (voir app/main.py), mais la purge
# RGPD, elle, n'a pas de filet : Beat doit tourner.
if pgrep -f "celery -A app.core.celery_app beat" >/dev/null 2>&1; then
  echo "[beat]   déjà lancé"
else
  echo "[beat]   démarrage du planificateur..."
  (cd apps/api && nohup python3 -m celery -A app.core.celery_app beat --loglevel=info < /dev/null > "../../$LOG_DIR/beat.log" 2>&1 & disown)
  sleep 1
  pgrep -f "celery -A app.core.celery_app beat" >/dev/null 2>&1 && echo "[beat]   ✅ lancé — logs : $LOG_DIR/beat.log" || echo "[beat]   ⚠️  n'a peut-être pas démarré — voir $LOG_DIR/beat.log"
fi

# ── 4. Backend API (uvicorn) ─────────────────────────────────────────
if curl -s -m 2 http://localhost:8000/health >/dev/null 2>&1; then
  echo "[api]    déjà lancé sur :8000"
else
  echo "[api]    démarrage d'uvicorn..."
  (cd apps/api && nohup python3 -m uvicorn app.main:app --reload --port 8000 < /dev/null > "../../$LOG_DIR/api.log" 2>&1 & disown)
  sleep 2
  echo "[api]    lancé — logs : $LOG_DIR/api.log"
fi

# ── 5. Frontend web (Next.js) ────────────────────────────────────────
if curl -s -m 2 http://localhost:3000 >/dev/null 2>&1; then
  echo "[web]    déjà lancé sur :3000"
else
  echo "[web]    démarrage de Next.js..."
  (nohup npm --prefix apps/web run dev < /dev/null > "$LOG_DIR/web.log" 2>&1 & disown)
  sleep 1
  echo "[web]    lancé — logs : $LOG_DIR/web.log"
fi

echo ""
echo "=== Statut ==="
redis-cli ping >/dev/null 2>&1 && echo "Redis   : ✅" || echo "Redis   : ❌"
pgrep -f "celery -A app.core.celery_app worker" >/dev/null 2>&1 && echo "Celery  : ✅" || echo "Celery  : ❌"
sleep 2
curl -s -m 3 http://localhost:8000/health >/dev/null 2>&1 && echo "Backend : ✅ (http://localhost:8000)" || echo "Backend : ⏳ pas encore prêt — laissez quelques secondes, sinon voir $LOG_DIR/api.log"
echo "Web     : http://localhost:3000 (voir $LOG_DIR/web.log si besoin)"
echo ""
echo "Pour tout arrêter : ./dev-stop.sh"
echo "Pour voir les logs en direct : tail -f logs/*.log"
