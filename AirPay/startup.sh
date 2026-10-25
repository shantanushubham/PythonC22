#!/usr/bin/env bash

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
  echo "${BOLD}${CYAN}║${RESET}      ${BOLD}💸  AirPay · Starting all services${RESET}      ${BOLD}${CYAN}║${RESET}"
  echo "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${RESET}"
}

step()    { echo; echo "${BOLD}${BLUE}▶ [$1/4]${RESET} ${BOLD}$2${RESET}"; echo "${DIM}──────────────────────────────────────────────${RESET}"; }
info()    { echo "  ${CYAN}•${RESET} $1"; }
success() { echo "  ${GREEN}✔${RESET} $1"; }

banner

# ── 1. Card payment service (Python / FastAPI) ──────────────────────────────
step 1 "💳 Card Payment Service ${DIM}(FastAPI · :8001)${RESET}"
cd ./card_payment_service || exit 1
info "Syncing dependencies..."
uv sync
info "Launching uvicorn..."
nohup uv run uvicorn app.main:app --reload --port 8001 &
# Only deactivate if a virtualenv is active
type deactivate >/dev/null 2>&1 && deactivate
success "Card payment service started"

# ── 2. Netbanking support (Go) ──────────────────────────────────────────────
step 2 "🏦 Netbanking Support ${DIM}(Go)${RESET}"
cd ../netbanking_support || exit 1
info "Launching Go service..."
nohup go run ./cmd/netbanking &
success "Netbanking service started"

# ── 3. UPI payment service (Node) ───────────────────────────────────────────
step 3 "📱 UPI Payment Service ${DIM}(Node)${RESET}"
cd ../upi_payment_service || exit 1
info "Installing dependencies..."
npm i
info "Building..."
npm run build
info "Launching server..."
nohup npm start &
success "UPI payment service started"

# ── 4. Payment gateway (Python / Django) ────────────────────────────────────
step 4 "🚪 Payment Gateway ${DIM}(Django · :8000)${RESET}"
cd ../payment_gateway_django || exit 1
# Postgres by default (via docker compose); falls back to SQLite without Docker.
# Override with e.g. `DB_ENGINE=sqlite ./startup.sh`.
export DB_ENGINE="${DB_ENGINE:-postgres}"
if [ "$DB_ENGINE" = "postgres" ]; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    info "Starting Postgres..."
    docker compose up -d --wait db || docker compose up -d db
  else
    info "Docker not available, falling back to SQLite"
    export DB_ENGINE=sqlite
  fi
fi
info "Syncing dependencies..."
uv sync
info "Running migrations ${DIM}(DB_ENGINE=$DB_ENGINE)${RESET}..."
uv run python manage.py migrate || exit 1
info "Launching Django..."
nohup uv run python manage.py runserver 8000 &
success "Payment gateway started"

# ── Done ────────────────────────────────────────────────────────────────────
echo
echo "${BOLD}${GREEN}🚀 All services launched!${RESET} ${DIM}(running in background via nohup)${RESET}"
echo
