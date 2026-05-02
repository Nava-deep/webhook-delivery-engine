.PHONY: up down test demo-success demo-failure-replay demo-flaky reset stop down-volumes

up:
	docker compose up --build

down:
	./scripts/stop_demo.sh

stop:
	./scripts/stop_demo.sh

down-volumes:
	./scripts/stop_demo.sh --volumes

test:
	docker compose exec api pytest

demo-success:
	./scripts/demo_success.sh

demo-failure-replay:
	./scripts/demo_failure_replay.sh

demo-flaky:
	./scripts/demo_flaky.sh

reset:
	./scripts/reset_demo.sh
