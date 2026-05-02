#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

require_tools
wait_for_api

echo "Local-development only: deleting rows created by the demo scripts."
reset_demo_data
echo "Demo data reset complete."
