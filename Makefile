# Quest Board — convenience targets for common operations

.PHONY: help up down logs migrate set-admin

help:
	@echo ""
	@echo "Quest Board — common make targets"
	@echo ""
	@echo "  make up                      Start all services (detached)"
	@echo "  make down                    Stop all services"
	@echo "  make logs                    Tail logs for all services"
	@echo "  make migrate                 Run Alembic migrations"
	@echo "  make set-admin EMAIL=x@x.x   Grant admin status to a user by email"
	@echo ""

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec backend alembic upgrade head

set-admin:
ifndef EMAIL
	$(error EMAIL is required: make set-admin EMAIL=user@example.com)
endif
	docker compose exec backend python -m app.cli set_admin --email "$(EMAIL)"
