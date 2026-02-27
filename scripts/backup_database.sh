#!/bin/bash
# =============================================================================
# IAMKT - SCRIPT DE BACKUP DO BANCO DE DADOS POSTGRESQL
# =============================================================================
# Este script cria um backup completo do banco de dados PostgreSQL
# 
# Uso: bash scripts/backup_database.sh
# =============================================================================

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Funções de log
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Verificar se está no diretório correto
if [ ! -f "docker-compose.yml" ]; then
    log_error "Execute este script a partir do diretório /opt/iamkt"
    exit 1
fi

# Criar diretório de backups
BACKUP_DIR="/opt/backups/iamkt"
mkdir -p "$BACKUP_DIR"

# Data e hora para nome do arquivo
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/iamkt_backup_$TIMESTAMP.sql"
BACKUP_COMPRESSED="$BACKUP_FILE.gz"

log_info "Iniciando backup do banco de dados..."
echo ""

# Obter credenciais do docker-compose.yml
DB_NAME="iamkt_db"
DB_USER="iamkt_user"
DB_PASSWORD="dev_password_change_me"
CONTAINER_NAME="iamkt_postgres"

# Verificar se container está rodando
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_error "Container $CONTAINER_NAME não está rodando!"
    exit 1
fi

log_info "Container: $CONTAINER_NAME"
log_info "Database: $DB_NAME"
log_info "Destino: $BACKUP_FILE"
echo ""

# Fazer backup
log_info "Executando pg_dump..."
docker exec -e PGPASSWORD="$DB_PASSWORD" "$CONTAINER_NAME" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    log_success "Backup SQL criado com sucesso!"
    
    # Comprimir backup
    log_info "Comprimindo backup..."
    gzip "$BACKUP_FILE"
    
    if [ $? -eq 0 ]; then
        log_success "Backup comprimido com sucesso!"
        
        # Informações do arquivo
        BACKUP_SIZE=$(du -h "$BACKUP_COMPRESSED" | cut -f1)
        log_success "Arquivo: $BACKUP_COMPRESSED"
        log_success "Tamanho: $BACKUP_SIZE"
        
        echo ""
        echo -e "${GREEN}=========================================================================${NC}"
        echo -e "${GREEN}BACKUP CONCLUÍDO COM SUCESSO!${NC}"
        echo -e "${GREEN}=========================================================================${NC}"
        echo ""
        echo "📁 Arquivo: $BACKUP_COMPRESSED"
        echo "📊 Tamanho: $BACKUP_SIZE"
        echo ""
        echo "Para transferir para o servidor novo:"
        echo ""
        echo "  # No servidor atual:"
        echo "  scp $BACKUP_COMPRESSED root@servidor-novo:/tmp/"
        echo ""
        echo "  # No servidor novo (após deploy):"
        echo "  cd /opt/iamkt"
        echo "  bash scripts/restore_database.sh /tmp/$(basename $BACKUP_COMPRESSED)"
        echo ""
    else
        log_error "Erro ao comprimir backup!"
        exit 1
    fi
else
    log_error "Erro ao criar backup!"
    exit 1
fi

# Listar backups existentes
echo ""
log_info "Backups disponíveis em $BACKUP_DIR:"
ls -lh "$BACKUP_DIR" | grep "iamkt_backup" | awk '{print "  - " $9 " (" $5 ")"}'
echo ""

# Limpeza de backups antigos (manter últimos 7 dias)
log_info "Limpando backups antigos (mantendo últimos 7 dias)..."
find "$BACKUP_DIR" -name "iamkt_backup_*.sql.gz" -type f -mtime +7 -delete
log_success "Limpeza concluída!"
