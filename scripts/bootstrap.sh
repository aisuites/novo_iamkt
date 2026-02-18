#!/bin/bash
# =============================================================================
# IAMKT - BOOTSTRAP SCRIPT
# =============================================================================
# Este script baixa e executa o deploy_full_auto.sh com encoding correto
# 
# IMPORTANTE: NÃO use via pipe! Baixe e execute diretamente:
# 
# wget https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh
# sudo bash bootstrap.sh
# 
# Ou:
# 
# curl -fsSL https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh -o bootstrap.sh
# sudo bash bootstrap.sh
# =============================================================================

set -e

echo "========================================================================="
echo "  IAMKT - Bootstrap Deploy"
echo "========================================================================="
echo ""

# Verificar se está rodando com stdin disponível
if [ ! -t 0 ]; then
    echo "[ERRO] Este script precisa de entrada interativa!"
    echo ""
    echo "NÃO use: curl ... | sudo bash"
    echo ""
    echo "Use:"
    echo "  wget https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh"
    echo "  sudo bash bootstrap.sh"
    echo ""
    exit 1
fi

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
echo ""
bash deploy_full_auto.sh < /dev/tty

# Limpar
cd /
rm -rf "$TEMP_DIR"
