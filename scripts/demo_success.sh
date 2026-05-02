#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

require_tools
wait_for_api

echo "Resetting previous demo data ..."
reset_demo_data

set_mock_mode "success"

endpoint_response="$(register_demo_endpoint)"
echo "$endpoint_response" | pretty_json

event_response="$(publish_demo_event "demo-success-$(date +%s)")"
echo "$event_response" | pretty_json
event_id="$(echo "$event_response" | extract_json_field event_id)"
delivery_id="$(delivery_id_for_event "$event_id")"

echo "Running one worker cycle ..."
run_worker_once
sleep 1

echo "Deliveries:"
print_deliveries

ensure_delivery_status "$delivery_id" "delivered"
echo "Success demo passed: delivery ${delivery_id} became delivered."
