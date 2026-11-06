# Shortcuts for development and deployment. Run `make help`.
SHELL := /bin/bash
COMPOSE := docker compose
ANSIBLE := cd deploy/ansible && ansible-playbook
ENV ?= staging
VERSION ?=

.PHONY: help dev dev-down dev-reset demo shell manage test oq jobs logs \
        check provision deploy restore-test

help:  ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

# --- development -------------------------------------------------------------------
dev:  ## Start the dev stack (app :8000, mail :8025) and follow app logs
	$(COMPOSE) up --build -d
	$(COMPOSE) logs -f app

dev-down:  ## Stop the dev stack (keeps data)
	$(COMPOSE) down

dev-reset:  ## Stop the dev stack and delete its database, files and backups
	$(COMPOSE) down -v

demo:  ## Load the demo devices, users and records into the dev database
	$(COMPOSE) exec app python manage.py load_demo_data

shell:  ## Django shell in the dev app container
	$(COMPOSE) exec app python manage.py shell

manage:  ## Run a management command: make manage CMD="createsuperuser"
	$(COMPOSE) exec app python manage.py $(CMD)

test:  ## Run the test suite on the dev PostgreSQL
	$(COMPOSE) exec app python manage.py test qms

oq:  ## Write OQ evidence to ./oq_evidence: make oq NAME="Your Name"
	$(COMPOSE) exec app python manage.py run_oq --executed-by "$(NAME)" --release dev --output oq_evidence

jobs:  ## Also run the scheduler (daily jobs) in development
	$(COMPOSE) --profile jobs up -d scheduler

logs:  ## Follow logs of all dev services
	$(COMPOSE) logs -f

check:  ## Lint shell scripts, Compose files and Ansible playbooks
	shellcheck deploy/scripts/*.sh
	$(COMPOSE) -f compose.yaml config --quiet
	cd deploy/ansible && for p in provision.yml deploy.yml restore-test.yml; do \
	  ansible-playbook --syntax-check $$p; done

# --- production / staging (Ansible) ------------------------------------------------
provision:  ## Prepare a server: make provision ENV=production
	$(ANSIBLE) provision.yml --limit $(ENV)

deploy:  ## Deploy a release: make deploy ENV=production VERSION=1.0.0
	@test -n "$(VERSION)" || (echo "Set VERSION, e.g. make deploy ENV=staging VERSION=1.0.0" && exit 1)
	$(ANSIBLE) deploy.yml --limit $(ENV) -e qms_version=$(VERSION)

restore-test:  ## Restore the latest backup into a scratch database and verify it
	$(ANSIBLE) restore-test.yml --limit $(ENV)
