#!/bin/bash
# =============================================================================
# IAMKT - SCRIPT DE DEPLOY COMPLETO E AUTOMATIZADO
# =============================================================================
# Este script faz o deploy COMPLETO da aplicação IAMKT em um Ubuntu 22.04 limpo
# 
# O que será instalado:
# - Docker + Docker Compose
# - Traefik v2.11 (proxy reverso com SSL)
# - Aplicação IAMKT (do GitHub)
# - PostgreSQL, Redis, Celery
#
# Uso: curl -fsSL https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/deploy_full_auto.sh | sudo bash
# Ou:  sudo bash deploy_full_auto.sh
#
# Data: 10/02/2026
# =============================================================================

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Funções de log
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${CYAN}=========================================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}=========================================================================${NC}"
    echo ""
}

# Verificar se é root
if [ "$EUID" -ne 0 ]; then 
    log_error "Este script precisa ser executado como root (sudo)"
    exit 1
fi

# Banner
clear
echo -e "${CYAN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║                    IAMKT - DEPLOY AUTOMATIZADO                        ║
║                                                                       ║
║          Deploy completo em Ubuntu 22.04 limpo                        ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

log_info "Este script vai instalar TUDO automaticamente:"
echo "  ✓ Docker + Docker Compose"
echo "  ✓ Traefik v2.11 (proxy reverso com SSL)"
echo "  ✓ Aplicação IAMKT (do GitHub)"
echo "  ✓ PostgreSQL, Redis, Celery"
echo ""

read -p "Deseja continuar? [S/n]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    log_warning "Deploy cancelado pelo usuário"
    exit 0
fi

# =============================================================================
# FASE 1: SETUP DO SERVIDOR
# =============================================================================
log_step "FASE 1/4: SETUP DO SERVIDOR"

log_info "Atualizando sistema operacional..."
apt update && apt upgrade -y
log_success "Sistema atualizado"

log_info "Instalando dependências básicas..."
apt install -y \
    curl \
    wget \
    git \
    make \
    htop \
    vim \
    nano \
    net-tools \
    ufw \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    jq
log_success "Dependências instaladas"

# Instalar Docker
log_info "Verificando instalação do Docker..."
if command -v docker &> /dev/null; then
    log_warning "Docker já instalado: $(docker --version)"
else
    log_info "Instalando Docker..."
    apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt update
    apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    log_success "Docker instalado: $(docker --version)"
    log_success "Docker Compose instalado: $(docker compose version)"
fi

# Configurar Docker
log_info "Configurando Docker..."
cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "dns": ["8.8.8.8", "8.8.4.4"]
}
EOF

systemctl restart docker
systemctl enable docker
log_success "Docker configurado"

# Configurar Firewall
log_info "Configurando firewall UFW..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw reload
log_success "Firewall configurado (portas 22, 80, 443)"

# Configurar Swap
log_info "Verificando swap..."
if [ $(swapon --show | wc -l) -eq 0 ]; then
    log_info "Criando swap de 4GB..."
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    log_success "Swap criado e ativado"
else
    log_warning "Swap já configurado"
fi

# Criar estrutura de diretórios
log_info "Criando estrutura de diretórios..."
mkdir -p /opt/traefik
mkdir -p /opt/traefik/{letsencrypt,oauth2}
mkdir -p /opt/backups
log_success "Diretórios criados em /opt/"

# Criar rede Docker
log_info "Criando rede Docker traefik_proxy..."
if docker network ls | grep -q traefik_proxy; then
    log_warning "Rede traefik_proxy já existe"
else
    docker network create traefik_proxy
    log_success "Rede traefik_proxy criada"
fi

# Adicionar usuário ao grupo Docker
REAL_USER=${SUDO_USER:-$USER}
if [ "$REAL_USER" != "root" ]; then
    usermod -aG docker $REAL_USER
    log_success "Usuário $REAL_USER adicionado ao grupo docker"
fi

# Otimizações do sistema
log_info "Aplicando otimizações do sistema..."
cat >> /etc/security/limits.conf <<EOF
* soft nofile 65536
* hard nofile 65536
EOF

cat >> /etc/sysctl.conf <<EOF
# Otimizações para Docker e aplicações web
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.ip_local_port_range = 1024 65535
vm.swappiness = 10
EOF

sysctl -p > /dev/null 2>&1
log_success "Otimizações aplicadas"

log_success "FASE 1 CONCLUÍDA: Servidor preparado!"

# =============================================================================
# FASE 2: CONFIGURAR TRAEFIK
# =============================================================================
log_step "FASE 2/4: CONFIGURAR TRAEFIK (Proxy Reverso + SSL)"

echo ""
log_info "Traefik será configurado com:"
echo "  - Proxy reverso para aplicações"
echo "  - SSL/TLS automático via Let's Encrypt"
echo "  - Cloudflare DNS Challenge"
echo ""

# Coletar informações
read -p "Email para Let's Encrypt: " ACME_EMAIL
read -p "Cloudflare API Token: " CF_DNS_API_TOKEN

# Criar .env do Traefik
log_info "Criando /opt/traefik/.env..."
cat > /opt/traefik/.env <<EOF
# Email para Let's Encrypt
ACME_EMAIL=$ACME_EMAIL

# Cloudflare API Token (para DNS Challenge)
CF_DNS_API_TOKEN=$CF_DNS_API_TOKEN
EOF
chmod 600 /opt/traefik/.env
log_success "Arquivo .env criado"

# Criar docker-compose.yml do Traefik
log_info "Criando /opt/traefik/docker-compose.yml..."
cat > /opt/traefik/docker-compose.yml <<'EOF'
version: "3.9"

services:
  traefik:
    image: traefik:v2.11
    container_name: traefik
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --providers.docker.endpoint=unix:///var/run/docker.sock
      
      # Entrypoints HTTP/HTTPS
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      
      # Redirecionar tudo de HTTP -> HTTPS
      - --entrypoints.web.http.redirections.entryPoint.to=websecure
      - --entrypoints.web.http.redirections.entryPoint.scheme=https
      
      # Let's Encrypt via Cloudflare DNS-01
      - --certificatesresolvers.cloudflare.acme.dnschallenge=true
      - --certificatesresolvers.cloudflare.acme.dnschallenge.provider=cloudflare
      - --certificatesresolvers.cloudflare.acme.email=${ACME_EMAIL}
      - --certificatesresolvers.cloudflare.acme.storage=/letsencrypt/acme.json
      
      # Logs
      - --log.level=INFO
    
    ports:
      - "80:80"
      - "443:443"
    
    environment:
      - CF_DNS_API_TOKEN=${CF_DNS_API_TOKEN}
    
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /opt/traefik/letsencrypt:/letsencrypt
    
    networks:
      - traefik_proxy
    
    restart: always

networks:
  traefik_proxy:
    external: true
EOF
log_success "docker-compose.yml criado"

# Criar arquivo acme.json
touch /opt/traefik/letsencrypt/acme.json
chmod 600 /opt/traefik/letsencrypt/acme.json

# Iniciar Traefik
log_info "Iniciando Traefik..."
cd /opt/traefik
docker compose up -d
sleep 5

if docker ps | grep -q traefik; then
    log_success "Traefik iniciado com sucesso!"
else
    log_error "Erro ao iniciar Traefik. Verifique os logs: docker logs traefik"
    exit 1
fi

log_success "FASE 2 CONCLUÍDA: Traefik configurado!"

# =============================================================================
# FASE 3: DEPLOY DA APLICAÇÃO
# =============================================================================
log_step "FASE 3/4: DEPLOY DA APLICAÇÃO"

# Coletar informações do projeto ANTES de clonar
echo ""
log_info "=== CONFIGURAÇÃO DO PROJETO ==="
echo ""
read -p "Nome do projeto (ex: iamkt, vibemkt): " PROJECT_NAME
PROJECT_NAME=${PROJECT_NAME:-iamkt}
log_success "Nome do projeto: $PROJECT_NAME"

read -p "Domínio da aplicação (ex: app.vibemkt.aisuites.com.br): " APP_DOMAIN
log_success "Domínio: $APP_DOMAIN"

# Definir diretório do projeto
APP_DIR="/opt/${PROJECT_NAME}"

# Clonar repositório
log_info "Clonando repositório do GitHub..."
cd /opt
if [ -d "${APP_DIR}/.git" ]; then
    log_warning "Repositório já existe em ${APP_DIR}. Atualizando..."
    cd ${APP_DIR}
    git pull origin main
else
    git clone https://github.com/aisuites/novo_iamkt.git ${PROJECT_NAME}
    cd ${APP_DIR}
fi
log_success "Repositório clonado/atualizado em ${APP_DIR}"

# Ajustar permissões
if [ "$REAL_USER" != "root" ]; then
    chown -R $REAL_USER:$REAL_USER ${APP_DIR}
    log_success "Permissões ajustadas para $REAL_USER"
fi

# Criar diretório de backups para o projeto
mkdir -p /opt/backups/${PROJECT_NAME}
log_success "Diretório de backups criado: /opt/backups/${PROJECT_NAME}"

# Configurar variáveis de ambiente
log_info "Configurando variáveis de ambiente..."
echo ""
log_warning "ATENÇÃO: Você precisará fornecer informações críticas!"
echo ""

# Copiar .env.example
cp .env.example .env.development

# Gerar secrets
SECRET_KEY=$(openssl rand -hex 32)
N8N_WEBHOOK_SECRET=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)

echo ""
log_info "=== CREDENCIAIS AWS ==="
read -p "AWS Access Key ID: " AWS_ACCESS_KEY_ID
read -p "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
read -p "AWS S3 Bucket Name: " AWS_STORAGE_BUCKET_NAME

echo ""
log_info "=== CREDENCIAIS IA ==="
read -p "OpenAI API Key: " OPENAI_API_KEY

echo ""
log_info "Configurações opcionais (pressione Enter para pular):"
read -p "Gemini API Key (opcional): " GEMINI_API_KEY
read -p "N8N Allowed IPs (opcional): " N8N_ALLOWED_IPS
read -p "Email Host (ex: smtp.gmail.com): " EMAIL_HOST
read -p "Email User: " EMAIL_HOST_USER
read -p "Email Password: " EMAIL_HOST_PASSWORD

# Atualizar .env.development
log_info "Gerando arquivo .env.development..."
cat > .env.development <<EOF
# =============================================================================
# ${PROJECT_NAME^^} - CONFIGURAÇÃO DE DESENVOLVIMENTO
# Gerado automaticamente em $(date)
# =============================================================================

# Project Configuration
PROJECT_NAME=${PROJECT_NAME}
APP_DOMAIN=${APP_DOMAIN}
DB_PASSWORD=${DB_PASSWORD}

# Environment
ENVIRONMENT=development
DEBUG=True

# Database
DATABASE_URL=postgresql://${PROJECT_NAME}_user:${DB_PASSWORD}@${PROJECT_NAME}_postgres:5432/${PROJECT_NAME}_db

# Redis & Celery
REDIS_URL=redis://${PROJECT_NAME}_redis:6379/0
CELERY_BROKER_URL=redis://${PROJECT_NAME}_redis:6379/0
CELERY_RESULT_BACKEND=redis://${PROJECT_NAME}_redis:6379/0

# Django Security
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=${APP_DOMAIN},www.${APP_DOMAIN},localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://${APP_DOMAIN},https://www.${APP_DOMAIN}
SITE_URL=https://${APP_DOMAIN}

# Django Modules
DJANGO_APPS=posts,pautas,perfil,dashboard

# Docker
COMPOSE_PROJECT_NAME=${PROJECT_NAME}

# AI Integrations
OPENAI_API_KEY=${OPENAI_API_KEY}
GEMINI_API_KEY=${GEMINI_API_KEY}
PERPLEXITY_API_KEY=

# AWS S3
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
AWS_STORAGE_BUCKET_NAME=${AWS_STORAGE_BUCKET_NAME}
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=
AWS_S3_USE_SSL=True

# Cache
CACHE_BACKEND=redis
CACHE_LOCATION=redis://iamkt_redis:6379/1

# Rate Limiting
RATELIMIT_ENABLE=True
RATELIMIT_USE_CACHE=default

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=${EMAIL_HOST}
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=${EMAIL_HOST_USER}
EMAIL_HOST_PASSWORD=${EMAIL_HOST_PASSWORD}
DEFAULT_FROM_EMAIL=${EMAIL_HOST_USER}

# N8N Integration
N8N_WEBHOOK_URL=
N8N_WEBHOOK_SECRET=${N8N_WEBHOOK_SECRET}
N8N_ALLOWED_IPS=${N8N_ALLOWED_IPS}
N8N_RATE_LIMIT=100/hour
EOF

chmod 600 .env.development
log_success "Arquivo .env.development criado"

# Gerar docker-compose.yml a partir do template
log_info "Gerando docker-compose.yml personalizado..."
if [ ! -f "docker-compose.yml.template" ]; then
    log_error "Template docker-compose.yml.template não encontrado!"
    exit 1
fi

sed -e "s/__PROJECT_NAME__/${PROJECT_NAME}/g" \
    -e "s/__APP_DOMAIN__/${APP_DOMAIN}/g" \
    -e "s/__DB_PASSWORD__/${DB_PASSWORD}/g" \
    docker-compose.yml.template > docker-compose.yml

log_success "docker-compose.yml gerado com sucesso"

log_info "Configuração aplicada:"
echo "  - PROJECT_NAME: $PROJECT_NAME"
echo "  - APP_DOMAIN: $APP_DOMAIN"
echo "  - DB_PASSWORD: ********"

# Build e deploy
log_info "Fazendo build da aplicação..."
docker compose build
log_success "Build concluído"

log_info "Iniciando containers..."
docker compose up -d
log_success "Containers iniciados"

# Aguardar containers ficarem prontos
log_info "Aguardando containers ficarem prontos (60 segundos)..."
sleep 60

# Executar migrations
log_info "Executando migrations do Django..."
docker exec ${PROJECT_NAME}_web python manage.py migrate
log_success "Migrations executadas"

# Coletar estáticos
log_info "Coletando arquivos estáticos..."
docker exec ${PROJECT_NAME}_web python manage.py collectstatic --noinput
log_success "Arquivos estáticos coletados"

# Criar superusuário
echo ""
log_info "Criando superusuário do Django..."
log_warning "Você precisará fornecer email e senha para o admin"
docker exec -it ${PROJECT_NAME}_web python manage.py createsuperuser

log_success "FASE 3 CONCLUÍDA: Aplicação deployada!"

# =============================================================================
# FASE 4: VALIDAÇÃO
# =============================================================================
log_step "FASE 4/4: VALIDAÇÃO DO DEPLOY"

log_info "Verificando containers..."
docker ps | grep ${PROJECT_NAME}

echo ""
log_info "Status dos containers:"
docker compose ps

echo ""
log_info "Testando health endpoint..."
sleep 5
if curl -f -s http://localhost:8000/health/ > /dev/null; then
    log_success "Health endpoint OK"
else
    log_warning "Health endpoint não respondeu (pode estar iniciando)"
fi

echo ""
log_info "Verificando logs (últimas 20 linhas)..."
docker compose logs --tail=20

# =============================================================================
# RESUMO FINAL
# =============================================================================
echo ""
echo -e "${CYAN}=========================================================================${NC}"
echo -e "${GREEN}✓ DEPLOY CONCLUÍDO COM SUCESSO!${NC}"
echo -e "${CYAN}=========================================================================${NC}"
echo ""
echo -e "${YELLOW}📋 INFORMAÇÕES IMPORTANTES:${NC}"
echo ""
echo "  🌐 Aplicação: https://${APP_DOMAIN}"
echo "  👤 Admin: https://${APP_DOMAIN}/admin/"
echo "  📊 Health: https://${APP_DOMAIN}/health/"
echo ""
echo "  📁 Diretório: ${APP_DIR}"
echo "  🐳 Containers: docker ps | grep ${PROJECT_NAME}"
echo "  📝 Logs: cd ${APP_DIR} && docker compose logs -f"
echo ""
echo -e "${YELLOW}🔧 PRÓXIMOS PASSOS:${NC}"
echo ""
echo "  1. Aguardar certificado SSL ser gerado (pode levar alguns minutos)"
echo "  2. Acessar https://${APP_DOMAIN} e testar"
echo "  3. Fazer login no admin: https://${APP_DOMAIN}/admin/"
echo "  4. (Opcional) Migrar dados do servidor antigo:"
echo "     cd ${APP_DIR} && bash scripts/deploy_migrate.sh"
echo ""
echo -e "${YELLOW}📚 DOCUMENTAÇÃO:${NC}"
echo ""
echo "  - Guia completo: ${APP_DIR}/docs/DEPLOY_NOVO_SERVIDOR.md"
echo "  - GitHub: https://github.com/aisuites/novo_iamkt"
echo "  - Validação: cd ${APP_DIR} && bash scripts/deploy_validate.sh ${APP_DOMAIN}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANTE:${NC}"
echo ""
echo "  - Faça logout e login para aplicar permissões Docker"
echo "  - Aguarde 2-5 minutos para certificado SSL ser gerado"
echo "  - Verifique logs: docker logs traefik"
echo ""
echo -e "${CYAN}=========================================================================${NC}"
echo ""

log_info "Informações do sistema:"
echo "  - Sistema: $(lsb_release -d | cut -f2)"
echo "  - Docker: $(docker --version)"
echo "  - Docker Compose: $(docker compose version)"
echo "  - Memória: $(free -h | grep Mem | awk '{print $2}')"
echo "  - Disco: $(df -h / | tail -1 | awk '{print $4}') disponível"
echo "  - Swap: $(free -h | grep Swap | awk '{print $2}')"
echo ""

log_success "Deploy finalizado! 🎉"
