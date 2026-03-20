
install:
	uv sync

test:
	uv run pytest tests

test-unit:
	uv run pytest tests/unit -v

lint:
	uv run ruff check src/

format:
	uv run ruff format src/ tests/

mypy:
	uv run mypy src

shell:
	uv run moneywiz-cli

package:
	uv run python -m build

test-publish:
	uv run python -m twine upload --repository testpypi dist/*

publish:
	uv run python -m twine upload --repository pypi dist/*
