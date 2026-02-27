#!/bin/bash
# =============================================================================
# IAMKT - SCRIPT DE RESTAURAÇÃO DO BANCO DE DADOS POSTGRESQL
# =============================================================================
# Este script restaura um backup do banco de dados PostgreSQL
# 
# Uso: bash scripts/restore_database.sh /caminho/para/backup.sql.gz
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

# Verificar argumentos
if [ $# -eq 0 ]; then
    log_error "Uso: bash scripts/restore_database.sh /caminho/para/backup.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Verificar se arquivo existe
if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Arquivo não encontrado: $BACKUP_FILE"
    exit 1
fi

# Verificar se está no diretório correto
if [ ! -f "docker-compose.yml" ]; then
    log_error "Execute este script a partir do diretório /opt/iamkt"
    exit 1
fi

log_warning "========================================================================="
log_warning "ATENÇÃO: Este processo irá SUBSTITUIR todos os dados do banco atual!"
log_warning "========================================================================="
echo ""
log_info "Arquivo de backup: $BACKUP_FILE"
echo ""
read -p "Deseja continuar? (digite 'SIM' para confirmar): " CONFIRM

if [ "$CONFIRM" != "SIM" ]; then
    log_info "Restauração cancelada pelo usuário."
    exit 0
fi

echo ""
log_info "Iniciando restauração do banco de dados..."
echo ""

# Obter credenciais do docker-compose.yml
DB_NAME="iamkt_db"
DB_USER="iamkt_user"
DB_PASSWORD="dev_password_change_me"
CONTAINER_NAME="iamkt_postgres"

# Verificar se container está rodando
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_error "Container $CONTAINER_NAME não está rodando!"
    log_info "Execute: cd /opt/iamkt && docker compose up -d"
    exit 1
fi

# Criar diretório temporário
TEMP_DIR=$(mktemp -d)
TEMP_SQL="$TEMP_DIR/restore.sql"

# Descomprimir se necessário
if [[ "$BACKUP_FILE" == *.gz ]]; then
    log_info "Descomprimindo backup..."
    gunzip -c "$BACKUP_FILE" > "$TEMP_SQL"
else
    cp "$BACKUP_FILE" "$TEMP_SQL"
fi

log_success "Backup preparado para restauração"
echo ""

# Parar aplicação temporariamente
log_info "Parando containers da aplicação..."
docker compose stop iamkt_web iamkt_celery

log_success "Containers parados"
echo ""

# Restaurar backup
log_info "Restaurando banco de dados..."
log_warning "Isso pode levar alguns minutos dependendo do tamanho do backup..."
echo ""

docker exec -i -e PGPASSWORD="$DB_PASSWORD" "$CONTAINER_NAME" \
    psql -U "$DB_USER" -d "$DB_NAME" < "$TEMP_SQL"

if [ $? -eq 0 ]; then
    log_success "Banco de dados restaurado com sucesso!"
    echo ""
    
    # Reiniciar aplicação
    log_info "Reiniciando containers da aplicação..."
    docker compose up -d iamkt_web iamkt_celery
    
    log_success "Containers reiniciados"
    echo ""
    
    # Limpar arquivos temporários
    rm -rf "$TEMP_DIR"
    
    echo ""
    echo -e "${GREEN}=========================================================================${NC}"
    echo -e "${GREEN}RESTAURAÇÃO CONCLUÍDA COM SUCESSO!${NC}"
    echo -e "${GREEN}=========================================================================${NC}"
    echo ""
    log_success "Banco de dados restaurado de: $BACKUP_FILE"
    echo ""
    log_info "Verificando status dos containers..."
    docker compose ps
    echo ""
    log_info "Para verificar logs:"
    echo "  docker compose logs -f iamkt_web"
    echo ""
else
    log_error "Erro ao restaurar banco de dados!"
    
    # Tentar reiniciar aplicação mesmo com erro
    log_info "Tentando reiniciar containers..."
    docker compose up -d iamkt_web iamkt_celery
    
    # Limpar arquivos temporários
    rm -rf "$TEMP_DIR"
    
    exit 1
fi
