# Shortcuts for the commands in the README. Each target runs one documented command,
# Needs uv (https://docs.astral.sh/uv/) and the challenge files in Data/.

.DEFAULT_GOAL := help
.PHONY: help install forecast csv check test test-fast app

help:  ## list the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install:  ## install the pinned packages (uv.lock)
	uv sync

forecast:  ## one command: raw data in Data/ -> validated forecast CSV (about 5 min)
	uv run python -m src.pipeline

csv:  ## rebuild the CSV from the saved model outputs (cost model, simulation, submission)
	uv run python -m src.pipeline --from cost_model

check:  ## validate the committed CSV against the submission format
	uv run python -m src.submission --check-only

test:  ## every test, including the leakage tests that re-run each model (10-15 min)
	uv run pytest tests/

test-fast:  ## the quick tests: formulas, submission format, pipeline order, story claims
	uv run pytest tests/test_submission.py tests/test_pipeline.py tests/test_story.py tests/test_strategy.py tests/test_pricing.py tests/test_simulation.py

app:  ## the decision tool (Streamlit), at http://localhost:8501
	uv run streamlit run app/streamlit_app.py
