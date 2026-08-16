.PHONY: run down restart logs shell migrate makemigrations createsuperuser create-app

run:
	docker compose up --build

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

create-superuser:
	docker compose exec backend python manage.py createsuperuser

create-app:
	docker compose exec backend python manage.py startapp $(filter-out $@,$(MAKECMDGOALS))

%:
	@: