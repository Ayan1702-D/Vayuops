# VayuOps development targets
.PHONY: install lint test check train serve up

install:
	python -m pip install -e ./backend -e "./ml[dev]"

lint:
	ruff check backend ml

test:
	pytest backend/tests ml/tests

check: lint test

train:
	python -m vayuops_ml.train

serve:
	@echo "API serving placeholder"

up:
	docker compose up --build
