.PHONY: eval test lint migrate benchmark run-backend

eval:
	python eval/run_eval.py

test:
	python -m pytest backend/tests/ -v

lint:
	python -m flake8 backend/ --max-line-length=120 --exclude=venv,alembic,node_modules || true

migrate:
	alembic upgrade head

benchmark:
	python backend/scripts/benchmark_sql.py

run-backend:
	uvicorn main:app --app-dir backend --reload --port 8000
