include .env

init:
	if [ ! -d ".git" ]; then git init; fi
	poetry install --sync

lint: clean
	poetry run yapf -i -r src
	poetry run isort -rc src
	poetry run ruff src --fix

test: clean
	PYTHONPATH=./src:./ poetry run pytest tests -v
	# PYTHONPATH=./src:./ poetry run python tests/test_all_in_one.py

dev: clean
	PYTHONPATH=./src:./ poetry run python examples/dev.py
	# PYTHONPATH=./src:./ poetry run python examples/example_static.py

clean:
	find . -depth -name "__pycache__" -print -exec rm -rf {} \;
	find . -depth -name "*.pyc" -print -exec rm -rf {} \;
	find . -depth -name "*.log" -print -exec rm -rf {} \;
	find . -depth -name "tmp_*" -print -exec rm -rf {} \;
	find . -depth -name ".*_cache" -print -exec rm -rf {} \;
	find . -depth -name "*_task.txt" -exec rm -rf {} \;
	find . -depth -name "tasks.db" -exec rm -rf {} \;
	find . -depth -name "openapi.json" -exec rm -rf {} \;
	find . -depth -name "temp_*" -exec rm -rf {} \;
	find . -depth -name "*.bak" -exec rm -rf {} \;
	rm -rf ./dist
	clear

cloc:
	cloc src/

commit: clean cloc
	git add .
	@if [ "$(msg)" != "" ]; then \
		git commit -m "$(msg)"; \
	else \
		git commit -m "update"; \
	fi

push: commit
	git push

pull:
	git pull

genreqs:
	poetry export -f requirements.txt --output requirements.txt --without-hashes


install:
	poetry run pip uninstall fly -y
	poetry run pip install -e .

build: clean
	poetry build

publish:
	poetry publish --username $(PYPI__FLY_USERNAME) --password $(PYPI__FLY_PASSWORD)