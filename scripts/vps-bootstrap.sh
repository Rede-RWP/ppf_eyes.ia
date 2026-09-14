#!/usr/bin/env bash
# Setup único na VPS: clona o repo e prepara deploy automático via GitHub Actions.
# Rode NA VPS como root (ou usuário com Docker).
#
# Uso:
#   export GIT_REPO=https://github.com/SEU_USER/ppf-eyes.git
#   # ou SSH: git@github.com:SEU_USER/ppf-eyes.git
#   bash scripts/vps-bootstrap.sh

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ppf-eyes}"
GIT_REPO="${GIT_REPO:?Defina GIT_REPO=https://github.com/USER/ppf-eyes.git}"
BRANCH="${DEPLOY_BRANCH:-main}"

if ! command -v docker >/dev/null; then
  echo "Instalando Docker…"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

mkdir -p "$(dirname "$APP_DIR")"
if [[ -d "$APP_DIR/.git" ]]; then
  echo "Repo já existe em $APP_DIR — atualizando…"
  cd "$APP_DIR"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git reset --hard "origin/$BRANCH"
else
  echo "Clonando $GIT_REPO → $APP_DIR"
  git clone --branch "$BRANCH" "$GIT_REPO" "$APP_DIR"
  cd "$APP_DIR"
fi

if [[ ! -f .env ]]; then
  cp .env.production.example .env
  echo ""
  echo ">>> Edite o .env agora:"
  echo "    nano $APP_DIR/.env"
  echo ">>> Depois: cd $APP_DIR && docker compose up -d --build"
else
  chmod +x scripts/deploy.sh
  ./scripts/deploy.sh
fi

echo "Bootstrap OK."
