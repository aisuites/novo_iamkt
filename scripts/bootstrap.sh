#!/bin/bash
# =============================================================================
# IAMKT - BOOTSTRAP SCRIPT
# =============================================================================
# Este script baixa e executa o deploy_full_auto.sh com encoding correto
# Uso: curl -fsSL https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh | sudo bash
# =============================================================================

set -e

echo "========================================================================="
echo "  IAMKT - Bootstrap Deploy"
echo "========================================================================="
echo ""

# Criar diretório temporário
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

echo "[INFO] Baixando script de deploy..."
curl -fsSL https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/deploy_full_auto.sh -o deploy_full_auto.sh

echo "[INFO] Corrigindo encoding..."
sed -i 's/\r$//' deploy_full_auto.sh
chmod +x deploy_full_auto.sh

echo "[INFO] Validando script..."
bash -n deploy_full_auto.sh

echo "[INFO] Executando deploy..."
bash deploy_full_auto.sh

# Limpar
cd /
rm -rf "$TEMP_DIR"
