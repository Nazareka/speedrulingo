.PHONY: format lint type test check migrate ui

format:
	env -u VIRTUAL_ENV uv run ruff format .

lint:
	env -u VIRTUAL_ENV uv run ruff check . --fix
	./lint-rules/run-ast-grep.sh

type:
	env -u VIRTUAL_ENV uv run mypy .

test:
	env -u VIRTUAL_ENV uv run pytest -q

migrate:
	env -u VIRTUAL_ENV uv run alembic upgrade head

ui:
	env -u VIRTUAL_ENV uv run python -m reflex run --frontend-port 3001 --backend-port 8001

check: lint type test
