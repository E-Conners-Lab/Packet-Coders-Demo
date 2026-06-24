# Packet Coders lab — one-command Docker stack.
# Run `make` (or `make help`) to see targets.

.DEFAULT_GOAL := help
.PHONY: help up up-host readonly down logs build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Start everything with a bundled Ollama (works anywhere, one command)
	docker compose up

up-host: ## Use the host's Ollama instead (faster on Mac; needs `ollama pull qwen3:8b` first)
	OLLAMA_BASE_URL=http://host.docker.internal:11434 docker compose up mcpo open-webui

readonly: ## Start read-only (the configure_device tool is not exposed at all)
	PACKET_CODERS_ALLOW_WRITES=false docker compose up

build: ## Rebuild the mcpo image after code changes
	docker compose build mcpo

down: ## Stop and remove the stack (volumes/data persist)
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f --tail=80
