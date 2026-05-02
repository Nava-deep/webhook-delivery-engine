#!/usr/bin/env bash

API_URL="${API_URL:-http://localhost:8000}"
MOCK_URL="${MOCK_URL:-http://localhost:9000}"
INTERNAL_MOCK_WEBHOOK_URL="${INTERNAL_MOCK_WEBHOOK_URL:-http://mock-receiver:9000/webhook}"
DEMO_DESCRIPTION="${DEMO_DESCRIPTION:-Demo mock receiver}"
DEMO_EVENT_TYPE="${DEMO_EVENT_TYPE:-order.created}"

require_tools() {
  command -v curl >/dev/null || {
    echo "curl is required to run the demo scripts."
    exit 1
  }
  command -v python3 >/dev/null || {
    echo "python3 is required to parse demo JSON responses."
    exit 1
  }
}

wait_for_api() {
  echo "Waiting for API at ${API_URL} ..."
  for _ in $(seq 1 30); do
    if curl -fsS "${API_URL}/api/stats/" >/dev/null 2>&1; then
      echo "API is ready."
      return 0
    fi
    sleep 1
  done

  echo "API did not become ready. Start the project with: docker compose up --build"
  exit 1
}

pretty_json() {
  python3 -m json.tool
}

extract_json_field() {
  local field="$1"
  python3 -c 'import json, sys; print(json.load(sys.stdin)[sys.argv[1]])' "$field"
}

reset_demo_data() {
  docker compose exec -T api python manage.py shell -c "
from deliveries.models import Event, WebhookEndpoint

endpoint_deleted, _ = WebhookEndpoint.objects.filter(description__startswith='Demo').delete()
event_deleted, _ = Event.objects.filter(idempotency_key__startswith='demo-').delete()
print(f'Deleted {endpoint_deleted} demo endpoint-related rows and {event_deleted} demo event-related rows.')
"
}

set_mock_mode() {
  local mode="$1"
  echo "Setting mock receiver mode to '${mode}' ..."
  curl -fsS -X POST "${MOCK_URL}/mode" \
    -H "Content-Type: application/json" \
    -d "{\"mode\":\"${mode}\"}" | pretty_json
}

register_demo_endpoint() {
  echo "Registering demo webhook endpoint ..." >&2
  curl -fsS -X POST "${API_URL}/api/endpoints/" \
    -H "Content-Type: application/json" \
    -d "{
      \"url\": \"${INTERNAL_MOCK_WEBHOOK_URL}\",
      \"description\": \"${DEMO_DESCRIPTION}\",
      \"event_types\": [\"${DEMO_EVENT_TYPE}\"],
      \"secret\": \"demo-secret\"
    }"
}

publish_demo_event() {
  local idempotency_key="$1"
  echo "Publishing ${DEMO_EVENT_TYPE} with idempotency key ${idempotency_key} ..." >&2
  curl -fsS -X POST "${API_URL}/api/events/" \
    -H "Content-Type: application/json" \
    -d "{
      \"event_type\": \"${DEMO_EVENT_TYPE}\",
      \"payload\": {
        \"order_id\": \"ord_demo\",
        \"amount\": 1999,
        \"currency\": \"INR\"
      },
      \"idempotency_key\": \"${idempotency_key}\"
    }"
}

delivery_id_for_event() {
  local event_id="$1"
  curl -fsS "${API_URL}/api/deliveries/?event_type=${DEMO_EVENT_TYPE}" |
    python3 -c '
import json
import sys

event_id = sys.argv[1]
deliveries = json.load(sys.stdin)
matches = [delivery for delivery in deliveries if delivery["event"] == event_id]
if not matches:
    raise SystemExit(f"No delivery found for event {event_id}")
print(matches[0]["id"])
' "$event_id"
}

delivery_status() {
  local delivery_id="$1"
  curl -fsS "${API_URL}/api/deliveries/${delivery_id}/" |
    python3 -c 'import json, sys; print(json.load(sys.stdin)["status"])'
}

print_delivery_line() {
  local delivery_id="$1"
  curl -fsS "${API_URL}/api/deliveries/${delivery_id}/" |
    python3 -c '
import json
import sys

d = json.load(sys.stdin)
print(
    "delivery={id} status={status} attempts={attempt_count} "
    "last_status={last_status_code} error={last_error}".format(**d)
)
'
}

print_deliveries() {
  curl -fsS "${API_URL}/api/deliveries/" | pretty_json
}

run_worker_once() {
  docker compose exec -T api python manage.py run_delivery_worker --once "$@"
}

replay_delivery() {
  local delivery_id="$1"
  curl -fsS -X POST "${API_URL}/api/deliveries/${delivery_id}/replay/" | pretty_json
}

ensure_delivery_status() {
  local delivery_id="$1"
  local expected="$2"
  local actual
  actual="$(delivery_status "$delivery_id")"

  if [[ "$actual" != "$expected" ]]; then
    echo "Expected delivery ${delivery_id} to be '${expected}', but it is '${actual}'."
    exit 1
  fi
}
