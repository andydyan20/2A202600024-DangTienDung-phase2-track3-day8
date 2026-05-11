.PHONY: install test lint typecheck run-scenarios grade-local run-extensions run-custom run-hidden hitl clean

install:
	pip install -e '.[dev]'

test:
	pytest

lint:
	ruff check src tests

typecheck:
	mypy src

run-scenarios:
	python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json

grade-local:
	python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json

run-extensions:
	python -m langgraph_agent_lab.cli extensions --config configs/lab.yaml

run-custom:
	python -m langgraph_agent_lab.cli run-custom --scenarios data/custom/scenarios.jsonl

run-hidden:
	python -m langgraph_agent_lab.cli run-scenarios --config configs/lab_hidden.yaml --output outputs/hidden_metrics.json

hitl:
	python -m langgraph_agent_lab.cli hitl

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov dist build *.egg-info outputs/*.json outputs/*.md checkpoints_demo.db
