.PHONY: run down restart logs shell migrate migrations create-superuser create-app clean recreate-schema seed

run:
	docker compose up

down:
	docker compose down

restart:
	docker compose down
	docker compose up --build

logs:
	docker compose logs -f

shell:
	docker compose exec backend python manage.py shell

migrate:
	docker compose exec backend python manage.py migrate

migrations:
	docker compose exec backend python manage.py makemigrations

seed:
	docker compose exec backend python manage.py seed_performance_data

create-superuser:
	docker compose exec backend python manage.py createsuperuser

create-app:
	docker compose exec backend python manage.py startapp $(filter-out $@,$(MAKECMDGOALS))

clean:
	docker compose down -v --remove-orphans
	docker run --rm -v $(shell pwd)/frontend:/app alpine rm -rf /app/.next /app/node_modules || rm -rf frontend/node_modules frontend/.next
	cd frontend && pnpm install

recreate-schema:
	@echo "Recreating PostgreSQL public schema..."
	docker compose exec db psql -U postgres -d mybackend -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO postgres;"
	docker compose exec backend python manage.py migrate

%:
	@: