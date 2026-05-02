#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

require_tools
wait_for_api

echo "Resetting previous demo data ..."
reset_demo_data

set_mock_mode "flaky"

endpoint_response="$(register_demo_endpoint)"
echo "$endpoint_response" | pretty_json

event_response="$(publish_demo_event "demo-flaky-$(date +%s)")"
echo "$event_response" | pretty_json
event_id="$(echo "$event_response" | extract_json_field event_id)"
delivery_id="$(delivery_id_for_event "$event_id")"

echo "The mock receiver fails the first two attempts, then succeeds."
for attempt in 1 2 3; do
  echo "Worker attempt ${attempt}"
  run_worker_once --ignore-schedule >/dev/null
  print_delivery_line "$delivery_id"

  if [[ "$(delivery_status "$delivery_id")" == "delivered" ]]; then
    break
  fi
done

ensure_delivery_status "$delivery_id" "delivered"
echo "Flaky demo passed: delivery ${delivery_id} eventually became delivered."
