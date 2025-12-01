.PHONY: help build up down restart logs clean test init db-migrate db-upgrade db-downgrade

help:
	@echo "Available commands:"
	@echo "  build      - Build all Docker images"
	@echo "  up         - Start all services"
	@echo "  down       - Stop all services"
	@echo "  restart    - Restart all services"
	@echo "  logs       - Show logs from all services"
	@echo "  clean      - Remove all containers and volumes"
	@echo "  test       - Run tests"
	@echo "  init       - Initialize the project"
	@echo "  db-migrate - Create a new database migration"
	@echo "  db-upgrade - Apply database migrations"
	@echo "  db-downgrade - Rollback database migrations"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	docker system prune -f

test:
	docker-compose exec backend python -m pytest

init:
	cp .env.example .env
	docker-compose up -d postgres redis
	sleep 10
	docker-compose exec backend python -c "from app.database import init_db; init_db()"
	@echo "Project initialized! Run 'make up' to start all services."

db-migrate:
	docker-compose exec backend alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	docker-compose exec backend alembic upgrade head

db-downgrade:
	docker-compose exec backend alembic downgrade -1
