# Set sane defaults for Make
SHELL = bash
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

# Set default goal such that `make` runs `make help`
.DEFAULT_GOAL := help

IMAGE_AUTHOR = toozej
IMAGE_NAME = exifizer
IMAGE_TAG = latest

.PHONY: all build test run local local-run local-test local-lint local-fmt update-python-version pre-reqs-install pre-commit pre-commit-install pre-commit-run clean help

all: build run verify ## Run default workflow
local: local-update-deps local-fmt local-lint local-test local-run ## Run local toolchain workflow

build: ## Build Dockerized project
	docker build -f $(CURDIR)/Dockerfile -t $(IMAGE_AUTHOR)/$(IMAGE_NAME):$(IMAGE_TAG) .

test: ## Test Dockerized project
	docker build --target test -f $(CURDIR)/Dockerfile -t $(IMAGE_AUTHOR)/$(IMAGE_NAME):$(IMAGE_TAG) .

run: ## Run Dockerized project
	-docker kill $(IMAGE_NAME)
	docker run --rm --name $(IMAGE_NAME) $(IMAGE_AUTHOR)/$(IMAGE_NAME):$(IMAGE_TAG)

local-update-deps: ## Update dependencies locally
	uv sync --all-groups

local-install: ## Install python-starter CLI locally via uv (builds + installs)
	uv tool install --force-reinstall .

local-run: ## Run Python project locally
	uv sync
	uv run exifizer --help

local-test: ## Run unit tests locally
	uv run -m pytest
	# use uv run -m pytest -n auto for parallel tests if needed, note can be slower for small test suites

local-lint: ## Run linters locally (ruff + ty)
	uv run ruff check --fix .
	uvx ty check .

local-fmt: ## Format code locally
	uv run ruff format .

update-python-version: ## Update Python version
	@VERSION=`curl -s "https://endoflife.date/api/python.json" | jq -r '.[0].latest' | sed 's/\.[0-9]*$$//'`; \
	echo "Updating Python to $$VERSION"; \
	./scripts/update_python_version.sh $$VERSION

pre-reqs-install: ## Install pre-requisite tools for using python-starter
	# uv
	command -v uv || brew install uv || (echo "uv not found. Install from https://docs.astral.sh/uv/" && exit 1)

pre-commit: pre-reqs-install pre-commit-install pre-commit-run ## Install and run pre-commit hooks

pre-commit-install: ## Install pre-commit hooks and necessary binaries
	# actionlint
	command -v actionlint || brew install actionlint || go install github.com/rhysd/actionlint/cmd/actionlint@latest
	# install and update pre-commits
	# determine if on Debian 12 and if so use pip to install more modern pre-commit version
	grep --silent "VERSION=\"12 (bookworm)\"" /etc/os-release && apt install -y --no-install-recommends python3-pip && python3 -m pip install --break-system-packages --upgrade pre-commit || echo "OS is not Debian 12 bookworm"
	# pre-commit
	command -v pre-commit || brew install pre-commit || sudo dnf install -y pre-commit || sudo apt install -y pre-commit
	# install and update pre-commits
	pre-commit install
	pre-commit autoupdate

pre-commit-run: ## Run pre-commit hooks against all files
	pre-commit run --all-files
	uvx ty check

clean: ## Clean up built Docker images
	docker image rm $(IMAGE_AUTHOR)/$(IMAGE_NAME):$(IMAGE_TAG)

help: ## Display help text
	@grep -E '^[a-zA-Z_-]+ ?:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
