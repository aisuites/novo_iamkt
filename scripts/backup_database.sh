#!/bin/bash
# =============================================================================
# IAMKT - SCRIPT DE BACKUP DO BANCO DE DADOS POSTGRESQL
# =============================================================================
# Cria um backup completo do banco via pg_dump DENTRO do container, usando o
# socket local do Postgres — NAO precisa de senha (e nenhuma senha fica
# hardcoded aqui). Funciona de qualquer diretorio e serve para cron.
#
# Uso:  bash scripts/backup_database.sh
# Cron: 0 3 * * * root bash /opt/iamkt/scripts/backup_database.sh >> /var/log/iamkt_backup.log 2>&1
#
# Variaveis (opcionais, via ambiente):
#   BACKUP_DIR      (default /opt/backups/iamkt)
#   RETENTION_DAYS  (default 7)
#   DB_NAME/DB_USER (default iamkt_db/iamkt_user)
#   CONTAINER_NAME  (default iamkt_postgres)
# =============================================================================

set -e
set -o pipefail

# Cores (desativadas quando nao ha TTY — ex.: cron/log)
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; NC=''
fi

log_info()    { echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error()   { echo -e "${RED}[✗]${NC} $1"; }

BACKUP_DIR="${BACKUP_DIR:-/opt/backups/iamkt}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DB_NAME="${DB_NAME:-iamkt_db}"
DB_USER="${DB_USER:-iamkt_user}"
CONTAINER_NAME="${CONTAINER_NAME:-iamkt_postgres}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_COMPRESSED="$BACKUP_DIR/iamkt_backup_$TIMESTAMP.sql.gz"

# Verificar se o container esta rodando
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_error "Container $CONTAINER_NAME não está rodando!"
    exit 1
fi

log_info "Backup de $DB_NAME ($CONTAINER_NAME) -> $BACKUP_COMPRESSED"

# pg_dump via socket local do container: sem senha, sem PGPASSWORD.
# gzip roda FORA do exec para o pipefail detectar falha do pg_dump.
docker exec "$CONTAINER_NAME" \
    pg_dump -U "$DB_USER" -d "$DB_NAME" \
    --clean --if-exists --no-owner --no-privileges \
    | gzip > "$BACKUP_COMPRESSED"

# Sanidade: o dump precisa ter conteudo real (nao so cabecalho)
if [ "$(stat -c%s "$BACKUP_COMPRESSED")" -lt 10240 ]; then
    log_error "Backup suspeito (<10KB) — verifique! Arquivo mantido para análise."
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_COMPRESSED" | cut -f1)
log_success "Backup concluído: $BACKUP_COMPRESSED ($BACKUP_SIZE)"

# Limpeza de backups antigos
log_info "Retenção: removendo backups com mais de $RETENTION_DAYS dias..."
find "$BACKUP_DIR" -name "iamkt_backup_*.sql.gz" -type f -mtime +"$RETENTION_DAYS" -delete
log_success "OK. Backups atuais:"
ls -lh "$BACKUP_DIR" | grep "iamkt_backup" | awk '{print "  - " $9 " (" $5 ")"}'
