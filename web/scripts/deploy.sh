#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Building and starting red-tide-risk-web..."
docker compose up -d --build

echo
echo "Deployment finished."
echo "Local URL: http://127.0.0.1:8080/red-tide-risk/"
echo "Health:    http://127.0.0.1:8080/healthz"
