# IAMKT - Marketing Automation Platform

Sistema de automação de marketing integrado à infraestrutura FemmeIntegra.

## 🚀 Quick Start

```bash
# Iniciar em modo SOLO (recomendado para desenvolvimento)
make solo

# Ver logs
make logs

# Parar
make down
```

## 🔗 URLs

- **Produção:** https://iamkt-femmeintegra.aisuites.com.br
- **Admin:** https://iamkt-femmeintegra.aisuites.com.br/admin/
- **Health Check:** https://iamkt-femmeintegra.aisuites.com.br/health/

## 📚 Documentação

Consulte `/opt/docs/` para documentação completa da infraestrutura.

## 🛠️ Comandos Úteis

```bash
make help       # Ver todos os comandos
make shell      # Acessar shell Django
make dbshell    # Acessar PostgreSQL
make validate   # Verificar isolamento
make migrate    # Executar migrations
make backup     # Backup do banco
```

## 🏗️ Arquitetura

- **Django 4.2+** com estrutura modular
- **PostgreSQL 15** (isolado, sem porta exposta)
- **Redis 7** para cache e Celery
- **Celery** para tarefas assíncronas
- **Traefik** para roteamento HTTPS
- **Cloudflare** para DNS e SSL

## 📊 Status

- ✅ Infraestrutura configurada
- ✅ Containers isolados
- ✅ HTTPS funcionando
- ✅ Health checks ativos
