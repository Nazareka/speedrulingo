.PHONY: format lint type test check migrate

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

check: lint type test
