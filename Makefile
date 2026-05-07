# content-stack Makefile
# All targets idempotent unless documented otherwise.
# Stubs that land in later milestones print the milestone tag and exit 0.

SHELL := /bin/bash
PYTHON ?= uv run python
UV ?= uv

.DEFAULT_GOAL := help

.PHONY: help install serve dev-ui build-ui register-codex register-claude \
        install-skills-codex install-skills-claude \
        install-procedures-codex install-procedures-claude \
        install-launchd doctor test migrate lint format typecheck \
        gen-types clean uninstall backup restore rotate-seed rotate-token \
        oauth-refresh

help: ## Show this help with all targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## (M0/M10) Install Python deps via uv (full install pipeline lands in M10)
	$(UV) sync --all-extras

serve: ## (M0) Run the daemon foreground on 127.0.0.1:5180
	$(PYTHON) -m content_stack serve

dev-ui: ## (M6) Run Vite dev server alongside daemon (UI source lands in M6)
	@if [ -d ui ]; then cd ui && pnpm dev; else echo "ui/ not yet scaffolded — lands in M6"; exit 0; fi

build-ui: ## (M6) Build Vue UI into content_stack/ui_dist/
	@if [ -d ui ]; then cd ui && pnpm install && pnpm build; else echo "ui/ not yet scaffolded — lands in M6"; exit 0; fi

migrate: ## (M0/M1) Run alembic migrations forward (schema lands in M1)
	$(UV) run alembic upgrade head

test: ## (M0) Run pytest
	$(UV) run pytest

lint: ## (M0) Run ruff check + format-check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## (M0) Apply ruff format + auto-fix lints
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

typecheck: ## (M0) Run mypy on the package
	$(UV) run mypy content_stack

gen-types: ## (M2) Regenerate ui/src/api.ts from the daemon's OpenAPI spec
	bash scripts/gen-types.sh

doctor: ## (M0) Diagnose install (M0 minimal — full check list grows through M10)
	$(PYTHON) -m content_stack doctor

clean: ## (M0) Remove caches and build artifacts (preserves DB at ~/.local/share/content-stack/)
	rm -rf __pycache__ .ruff_cache .mypy_cache .pytest_cache build dist
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +

# ---- Stubs for later milestones (present so `make` target list matches PLAN.md) ----

register-codex: ## (M10) Register MCP server with Codex CLI
	@echo "Not yet implemented (M10: distribution / MCP registration)"

register-claude: ## (M10) Register MCP server with Claude Code (.mcp.json upsert)
	@echo "Not yet implemented (M10: distribution / MCP registration)"

install-skills-codex: ## (M7/M10) Install skills into ~/.codex/skills/content-stack/
	@echo "Not yet implemented (M10: distribution; depends on M7 skills)"

install-skills-claude: ## (M7/M10) Install skills into ~/.claude/skills/content-stack/
	@echo "Not yet implemented (M10: distribution; depends on M7 skills)"

install-procedures-codex: ## (M8/M10) Install procedures into ~/.codex/procedures/content-stack/
	@echo "Not yet implemented (M10: distribution; depends on M8 procedures)"

install-procedures-claude: ## (M8/M10) Install procedures into ~/.claude/procedures/content-stack/
	@echo "Not yet implemented (M10: distribution; depends on M8 procedures)"

install-launchd: ## (M9/M10) Write launchd plist for auto-start
	@echo "Not yet implemented (M9 jobs / M10 distribution)"

uninstall: ## (M10) Remove installed skills/procedures/MCP entries; preserve DB
	@echo "Not yet implemented (M10: distribution)"

backup: ## (M9) Atomic SQLite .backup + copy seed.bin and auth.token
	@echo "Not yet implemented (M9: jobs/scheduling; auto-backup job)"

restore: ## (M9) Halt daemon, copy backup file over current DB, restart
	@echo "Not yet implemented (M9: jobs/scheduling)"

rotate-seed: ## (M4) Re-encrypt all integration_credentials with a new seed
	$(PYTHON) -m content_stack rotate-seed --reencrypt

oauth-refresh: ## (M4) Run the GSC OAuth refresh worker once
	$(PYTHON) -m content_stack.jobs.oauth_refresh --once

rotate-token: ## (M10) Generate new auth token and update MCP configs
	@echo "Not yet implemented (M10: distribution)"
