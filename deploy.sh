#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

command_exists() { command -v "$1" >/dev/null 2>&1; }

log() { echo "[deploy] $*"; }

# 1) Ensure dependencies
if ! command_exists docker; then
  log "Installing Docker..."
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl gnupg
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER" || true
  log "Docker installed. You may need to log out/in for group changes to take effect."
fi

if ! docker compose version >/dev/null 2>&1; then
  log "Installing docker compose plugin..."
  sudo apt-get update -y
  sudo apt-get install -y docker-compose-plugin
fi

# 2) Prepare backend .env
BACKEND_ENV="$PROJECT_ROOT/backend/.env"
if [ ! -f "$BACKEND_ENV" ]; then
  log "Creating backend .env"
  cat > "$BACKEND_ENV" << 'EOF'
# Required
OPENAI_API_KEY=
# Optional
MODEL_NAME=gpt-4o-mini
MAX_TOKENS=1500
EOF
  log "Please edit backend/.env to set OPENAI_API_KEY."
fi

# 3) Ensure uploads directory exists
mkdir -p "$PROJECT_ROOT/backend/uploads"

# 4) Build and start services
log "Validating env and starting containers..."
set -a
. "$BACKEND_ENV"
set +a
if [ -z "${OPENAI_API_KEY:-}" ]; then
  log "ERROR: OPENAI_API_KEY is empty in backend/.env. Please set it and re-run."
  exit 1
fi

# Use sudo for docker if needed
if docker ps >/dev/null 2>&1; then
  DOCKER="docker"
else
  DOCKER="sudo docker"
fi

$DOCKER compose -f "$PROJECT_ROOT/docker-compose.yml" up -d --build

# 5) Health checks
log "Waiting for backend health..."
for i in {1..30}; do
  if curl -sSf http://localhost:5000/healthz >/dev/null 2>&1; then
    log "Backend is healthy."
    break
  fi
  sleep 2
  if [ "$i" -eq 30 ]; then
    log "Backend health check timed out. Continuing."
  fi
done

log "Frontend should be available on port 8080."

# 6) Optional: create systemd unit file
if [ "${SETUP_SYSTEMD:-false}" = "true" ]; then
  SERVICE_NAME="rag2-stack"
  UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
  log "Setting up systemd unit: $SERVICE_NAME"
  sudo tee "$UNIT_FILE" >/dev/null <<EOF
[Unit]
Description=RAG2 Docker Compose Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_ROOT
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
RemainAfterExit=yes
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable "$SERVICE_NAME"
  sudo systemctl start "$SERVICE_NAME"
  log "systemd service enabled and started."
fi

log "Done. Access frontend at http://<server-ip>/ and backend at http://<server-ip>:5000/"