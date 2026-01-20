#!/bin/bash
# =============================================================================
# NTO - ENTRYPOINT SCRIPT
# =============================================================================
set -e

# Cores para logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Função de log
log() {
    echo -e "${BLUE}[VIBE MKT]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[VIBE MKT]${NC} ✅ $1"
}

log_error() {
    echo -e "${RED}[VIBE MKT]${NC} ❌ $1"
}

# Aguardar dependências
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=1

    log "Aguardando $service_name em $host:$port..."
    
    while ! nc -z $host $port; do
        if [ $attempt -eq $max_attempts ]; then
            log_error "$service_name não respondeu"
            exit 1
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log_success "$service_name disponível!"
}

# Aguardar PostgreSQL
if [ -n "$DATABASE_URL" ]; then
    DB_HOST=$(echo $DATABASE_URL | sed 's/.*@\([^:]*\):.*/\1/')
    DB_PORT=$(echo $DATABASE_URL | sed 's/.*:\([0-9]*\)\/.*/\1/')
    wait_for_service $DB_HOST $DB_PORT "PostgreSQL"
fi

# Aguardar Redis  
if [ -n "$REDIS_URL" ]; then
    REDIS_HOST=$(echo $REDIS_URL | sed 's/redis:\/\/\([^:]*\):.*/\1/')
    REDIS_PORT=$(echo $REDIS_URL | sed 's/.*:\([0-9]*\)\/.*/\1/')
    wait_for_service $REDIS_HOST $REDIS_PORT "Redis"
fi

# Configurar Django settings
if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
    if [ "$ENVIRONMENT" = "production" ]; then
        export DJANGO_SETTINGS_MODULE="sistema.settings.production"
    else
        export DJANGO_SETTINGS_MODULE="sistema.settings.development"
    fi
fi

log "Django Settings: $DJANGO_SETTINGS_MODULE"

# Executar comando
case "$1" in
    "migrate")
        python manage.py migrate --noinput
        ;;
    "shell")
        python manage.py shell
        ;;
    "celery-worker")
        celery -A sistema worker -l info
        ;;
    "celery-beat")
        celery -A sistema beat -l info
        ;;
    *)
        exec "$@"
        ;;
esac
