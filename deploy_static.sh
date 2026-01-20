#!/bin/bash
# Script de deploy de arquivos estáticos - Solução definitiva
# Problema: collectstatic não copia knowledge.css e knowledge.js automaticamente

set -e

echo "=== DEPLOY DE ARQUIVOS ESTÁTICOS ==="
echo ""

# 1. Executar collectstatic
echo "1. Executando collectstatic..."
docker compose exec iamkt_web python manage.py collectstatic --noinput --clear

# 2. Copiar arquivos específicos que não foram copiados
echo ""
echo "2. Copiando arquivos knowledge manualmente..."
docker compose exec iamkt_web cp -v /app/static/css/knowledge.css /app/staticfiles/css/ 2>/dev/null || echo "  knowledge.css já existe ou não encontrado"
docker compose exec iamkt_web cp -v /app/static/js/knowledge.js /app/staticfiles/js/ 2>/dev/null || echo "  knowledge.js já existe ou não encontrado"

# 3. Verificar se os arquivos foram copiados
echo ""
echo "3. Verificando arquivos copiados..."
docker compose exec iamkt_web ls -lh /app/staticfiles/css/knowledge.css /app/staticfiles/js/knowledge.js

# 4. Reiniciar servidor
echo ""
echo "4. Reiniciando servidor..."
docker compose restart iamkt_web

echo ""
echo "=== DEPLOY CONCLUÍDO ==="
echo "Acesse: https://iamkt-femmeintegra.aisuites.com.br/knowledge/"
echo "Faça HARD REFRESH: Ctrl+Shift+R"
