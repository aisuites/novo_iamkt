# IAMKT - MAKEFILE OPERACIONAL
.PHONY: help setup up down restart recreate logs shell dbshell validate solo

ENV_FILE ?= development
COMPOSE_PROJECT = iamkt

help:
	@echo "🏗️  IAMKT - Comandos Operacionais"
	@echo "make setup          - Configuração inicial"
	@echo "make up             - Iniciar modo normal"
	@echo "make solo           - Iniciar modo focado (mais recursos)"
	@echo "make down           - Parar todos os serviços"
	@echo "make recreate       - Recriar containers (útil após mudar .env)"
	@echo "make logs           - Ver logs em tempo real"
	@echo "make shell          - Shell Django"
	@echo "make dbshell        - Shell PostgreSQL"
	@echo "make validate       - Verificar isolamento"

setup:
	@if [ ! -f .env.$(ENV_FILE) ]; then \
		echo "❌ Arquivo .env.$(ENV_FILE) não encontrado!"; \
		exit 1; \
	fi
	@docker network ls | grep -q traefik_proxy || docker network create traefik_proxy

up: setup
	@docker compose --env-file .env.$(ENV_FILE) up -d

solo: setup
	@docker compose -f docker-compose.yml -f docker-compose.solo.yml --env-file .env.$(ENV_FILE) up -d

down:
	@echo "⏹️  Parando IAMKT..."
	@docker compose down
	@echo "✅ IAMKT parado!"

recreate:
	@echo "🔄 Recriando containers IAMKT..."
	@docker compose down
	@docker compose --env-file .env.$(ENV_FILE) up -d
	@echo "✅ Containers recriados! Variáveis de ambiente recarregadas."

logs:
	@docker compose logs -f

shell:
	@docker compose exec iamkt_web bash

dbshell:
	@docker compose exec iamkt_postgres psql -U iamkt_user -d iamkt_db

validate:
	@echo "✅ Validando isolamento IAMKT..."
	@docker ps --format "{{.Names}}\t{{.Ports}}" | grep iamkt | grep -E "(5432|6379)" || echo "✅ Nenhuma porta exposta"

clean:
	@echo "🧹 Limpando containers órfãos..."
	@docker compose down --remove-orphans
	@docker system prune -f
	@echo "✅ Limpeza concluída!"

migrate:
	@echo "🔄 Executando migrations..."
	@docker compose exec iamkt_web python manage.py migrate
	@echo "✅ Migrations aplicadas!"

backup:
	@echo "💾 Criando backup PostgreSQL..."
	@mkdir -p backups
	@docker compose exec -T iamkt_postgres pg_dump -U iamkt_user iamkt_db > backups/iamkt_backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup criado em backups/"
