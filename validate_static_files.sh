#!/bin/bash
# Script de validação de arquivos estáticos

echo "=== VALIDAÇÃO DE ARQUIVOS ESTÁTICOS ==="
echo ""

echo "1. Verificando arquivos em /app/static/:"
ls -lh /app/static/css/knowledge.css 2>&1
ls -lh /app/static/js/knowledge.js 2>&1
echo ""

echo "2. Verificando arquivos em /app/staticfiles/:"
ls -lh /app/staticfiles/css/knowledge.css 2>&1
ls -lh /app/staticfiles/js/knowledge.js 2>&1
echo ""

echo "3. Verificando conteúdo do knowledge.css (primeiras 10 linhas):"
head -10 /app/staticfiles/css/knowledge.css 2>&1
echo ""

echo "4. Verificando conteúdo do knowledge.js (primeiras 10 linhas):"
head -10 /app/staticfiles/js/knowledge.js 2>&1
echo ""

echo "5. Testando acesso HTTP aos arquivos estáticos:"
curl -s -I http://localhost:8000/static/css/knowledge.css | head -5
curl -s -I http://localhost:8000/static/js/knowledge.js | head -5
echo ""

echo "=== FIM DA VALIDAÇÃO ==="
