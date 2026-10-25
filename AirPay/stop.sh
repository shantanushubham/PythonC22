#!/usr/bin/env bash
#
# Stops the services launched by startup.sh.
#
# Each service is found by the port it listens on, which also catches the
# child processes spawned by `uv run`, `go run` and `npm start`.
#
# Usage: ./stop.sh

# ── Colors (disabled automatically when not writing to a terminal) ──────────
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
  RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'
  BLUE=$'\033[34m'; MAGENTA=$'\033[35m'; CYAN=$'\033[36m'
else
  BOLD=""; DIM=""; RESET=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; MAGENTA=""; CYAN=""
fi

banner() {
  echo
  echo "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${RESET}"
  echo "${BOLD}${CYAN}║${RESET}      ${BOLD}💸  AirPay · Stopping all services${RESET}      ${BOLD}${CYAN}║${RESET}"
  echo "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${RESET}"
}

step()    { echo; echo "${BOLD}${BLUE}▶ [$1/4]${RESET} ${BOLD}$2${RESET}"; echo "${DIM}──────────────────────────────────────────────${RESET}"; }
info()    { echo "  ${CYAN}•${RESET} $1"; }
success() { echo "  ${GREEN}✔${RESET} $1"; }
warn()    { echo "  ${YELLOW}!${RESET} $1"; }
fail()    { echo "  ${RED}✘${RESET} $1"; }

# PIDs listening on a TCP port
pids_on_port() {
  lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null
}

# stop_port <port> <name>
# Sends SIGTERM, waits up to ~5s, then falls back to SIGKILL.
stop_port() {
  local port="$1" name="$2" pids
  pids=$(pids_on_port "$port")

  if [ -z "$pids" ]; then
    warn "$name is not running ${DIM}(nothing on :$port)${RESET}"
    return 0
  fi

  info "Stopping $name ${DIM}(pid $(echo $pids | tr '\n' ' ')on :$port)${RESET}"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null

  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    [ -z "$(pids_on_port "$port")" ] && break
    sleep 0.5
  done

  pids=$(pids_on_port "$port")
  if [ -n "$pids" ]; then
    warn "Still running, forcing shutdown..."
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null
    sleep 0.5
  fi

  if [ -z "$(pids_on_port "$port")" ]; then
    success "$name stopped"
  else
    fail "Could not stop $name on :$port"
    STATUS=1
  fi
}

# Kill leftover wrapper processes (`uv run`, `go run`, `npm start`) whose
# command line matches a pattern, e.g. the uvicorn --reload supervisor.
cleanup_pattern() {
  local pattern="$1" pids
  pids=$(pgrep -f "$pattern" 2>/dev/null)
  if [ -n "$pids" ]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null
  fi
}

STATUS=0
banner

# ── 1. Card payment service (Python / FastAPI) ──────────────────────────────
step 1 "💳 Card Payment Service ${DIM}(FastAPI · :8001)${RESET}"
# Stop the --reload supervisor first so it doesn't respawn the worker.
cleanup_pattern "uvicorn app.main:app --reload --port 8001"
stop_port 8001 "Card payment service"

# ── 2. Netbanking support (Go) ──────────────────────────────────────────────
step 2 "🏦 Netbanking Support ${DIM}(Go · :8002)${RESET}"
cleanup_pattern "go run ./cmd/netbanking"
stop_port 8002 "Netbanking service"

# ── 3. UPI payment service (Node) ───────────────────────────────────────────
step 3 "📱 UPI Payment Service ${DIM}(Node · :8003)${RESET}"
cleanup_pattern "npm start"
stop_port 8003 "UPI payment service"

# ── 4. Payment gateway (Python / Django) ────────────────────────────────────
step 4 "🚪 Payment Gateway ${DIM}(Django · :8000)${RESET}"
# Stop the autoreloader parent first so it doesn't respawn the server.
cleanup_pattern "manage.py runserver 8000"
stop_port 8000 "Payment gateway"

# Postgres container started by startup.sh (data is kept; only the container stops).
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  if [ -n "$(cd "$(dirname "$0")/payment_gateway_django" && docker compose ps -q db 2>/dev/null)" ]; then
    info "Stopping Postgres container..."
    if (cd "$(dirname "$0")/payment_gateway_django" && docker compose stop db >/dev/null 2>&1); then
      success "Postgres stopped"
    else
      fail "Could not stop Postgres container"
      STATUS=1
    fi
  fi
fi

# ── Done ────────────────────────────────────────────────────────────────────
echo
if [ "$STATUS" -eq 0 ]; then
  echo "${BOLD}${GREEN}🛑 All services stopped.${RESET}"
else
  echo "${BOLD}${RED}Some services could not be stopped.${RESET}"
fi
echo
exit "$STATUS"
