# ==========================
# DevOps automation (Layer 0 / 6). Article uses `make docker-build-env ENV=...`.
# On Windows, run these targets from Git Bash, or use the raw commands directly.
# ==========================
ENV ?= development

.PHONY: install run docker-up docker-down docker-build-env lint test

install:            ## Sync dependencies from the lockfile
	uv sync

run:                ## Run the API locally (reads .env.$(ENV))
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-up:          ## Start the full local stack (api + db + prometheus + grafana)
	docker compose up --build

docker-down:        ## Stop the stack
	docker compose down

docker-build-env:   ## Build the app image for a given ENV (=development|staging|production)
	docker build -t 7layers-agent:$(ENV) .

# --- Azure deploy (cloud-required; run once az CLI is authenticated) ---
azure-push:         ## Tag + push the image to Azure Container Registry ($(ACR) must be set)
	docker tag 7layers-agent:$(ENV) $(ACR).azurecr.io/7layers-agent:$(ENV)
	docker push $(ACR).azurecr.io/7layers-agent:$(ENV)

lint:               ## Lint + format check
	uv run ruff check .

test:               ## Run tests
	uv run pytest -q
