#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--volumes" ]]; then
  echo "Stopping Docker Compose and removing volumes ..."
  docker compose down -v
else
  echo "Stopping Docker Compose. Volumes are preserved."
  echo "Use scripts/stop_demo.sh --volumes if you also want to remove local database data."
  docker compose down
fi
