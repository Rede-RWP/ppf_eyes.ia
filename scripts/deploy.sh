#!/usr/bin/env bash
# Deploy na VPS: puxa o Git e recria os containers Docker.
# Uso: ./scripts/deploy.sh
# Mantém .env local (não vem do Git).

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/ppf-eyes}"
BRANCH="${DEPLOY_BRANCH:-main}"

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  echo "ERRO: falta $APP_DIR/.env — copie de .env.production.example e configure."
  exit 1
fi

echo "==> Atualizando código ($BRANCH)…"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

echo "==> Subindo Docker…"
docker compose up -d --build --remove-orphans

echo "==> Limpando imagens antigas…"
docker image prune -f

echo "==> Status:"
docker compose ps
echo "OK — deploy concluído em $(date -u +%Y-%m-%dT%H:%M:%SZ)"
