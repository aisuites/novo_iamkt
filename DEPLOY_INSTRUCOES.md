# 🚀 Instruções de Deploy - IAMKT

## ⚠️ IMPORTANTE: Como Executar o Deploy Corretamente

O deploy automatizado requer **entrada interativa** para coletar informações como domínio, credenciais, etc.

### ❌ NÃO FAÇA ISSO (não funciona):
```bash
curl -fsSL https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh | sudo bash
```

### ✅ FAÇA ASSIM (correto):

#### **Opção 1: Usando wget (Recomendado)**
```bash
wget https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh
sudo bash bootstrap.sh
```

#### **Opção 2: Usando curl**
```bash
curl -fsSL https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh -o bootstrap.sh
sudo bash bootstrap.sh
```

#### **Opção 3: Clonar o repositório (Mais seguro)**
```bash
git clone https://github.com/aisuites/novo_iamkt.git /tmp/iamkt
cd /tmp/iamkt
sudo bash scripts/deploy_full_auto.sh
```

---

## 📋 O que o Script Bootstrap Faz

1. ✅ Baixa o `deploy_full_auto.sh` do GitHub
2. ✅ Corrige automaticamente problemas de encoding (CRLF → LF)
3. ✅ Valida a sintaxe do script
4. ✅ Executa o deploy de forma interativa
5. ✅ Limpa arquivos temporários

---

## 🔧 O que o Deploy Completo Instala

- **Docker** + Docker Compose (versão mais recente)
- **Traefik v2.11** (proxy reverso com SSL automático)
- **PostgreSQL** (banco de dados)
- **Redis** (cache e broker Celery)
- **Celery** (processamento assíncrono)
- **Aplicação IAMKT** (clonada do GitHub)

---

## 📝 Informações que Serão Solicitadas

Durante o deploy, você precisará fornecer:

### **Obrigatórias:**
- Email para Let's Encrypt (SSL)
- Cloudflare API Token (para DNS Challenge)
- Domínio da aplicação (ex: `app.iamkt.com.br`)
- AWS Access Key ID
- AWS Secret Access Key
- AWS S3 Bucket Name
- OpenAI API Key

### **Opcionais:**
- Gemini API Key
- N8N Allowed IPs
- Email Host (SMTP)
- Email User
- Email Password

---

## 🎯 Para Deploy do VibeMKT/FEMME

### Passo 1: Preparar o novo servidor Ubuntu
```bash
# No novo servidor Ubuntu 22.04 limpo
wget https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh
sudo bash bootstrap.sh
```

### Passo 2: Aguardar instalação completa
- O script instalará tudo automaticamente
- Aguarde a geração do certificado SSL (2-5 minutos)

### Passo 3: Validar o deploy
```bash
cd /opt/iamkt
bash scripts/deploy_validate.sh seu-dominio.com
```

### Passo 4: Personalizar para FEMME
```bash
cd /opt/iamkt
# Fazer alterações de logo, cores, textos, etc.
```

### Passo 5: Criar novo repositório
```bash
# Criar repositório 'vibemkt' no GitHub
git remote set-url origin https://github.com/aisuites/vibemkt.git
git add -A
git commit -m "feat: personalização para FEMME/VibeMKT"
git push -u origin main
```

---

## 🆘 Solução de Problemas

### Erro: "cho: command not found"
**Causa:** Problema de encoding durante download  
**Solução:** Use o script bootstrap conforme instruções acima

### Erro: Script não pede informações interativas
**Causa:** Executou via pipe (`curl | bash`)  
**Solução:** Baixe o arquivo primeiro e execute diretamente

### Erro: Permissão negada
**Causa:** Não executou como root  
**Solução:** Use `sudo bash bootstrap.sh`

---

## 📚 Documentação Adicional

- **Deploy completo:** `/opt/iamkt/docs/DEPLOY_NOVO_SERVIDOR.md`
- **GitHub:** https://github.com/aisuites/novo_iamkt
- **Validação:** `bash scripts/deploy_validate.sh`
- **Logs:** `cd /opt/iamkt && docker compose logs -f`

---

## ✅ Checklist Pós-Deploy

- [ ] Aplicação acessível via HTTPS
- [ ] Certificado SSL gerado (aguardar 2-5 min)
- [ ] Admin acessível em `/admin/`
- [ ] Health check OK em `/health/`
- [ ] Containers rodando: `docker ps | grep iamkt`
- [ ] Logs sem erros: `docker compose logs --tail=50`
