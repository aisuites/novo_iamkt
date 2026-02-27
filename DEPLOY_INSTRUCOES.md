# 🚀 Instruções de Deploy - IAMKT

## 📋 Índice
- [Deploy Automatizado em Servidor Novo](#-deploy-automatizado-em-servidor-novo)
- [Requisitos do Servidor](#-requisitos-do-servidor)
- [Credenciais Necessárias](#-credenciais-necessárias)
- [Passo a Passo Completo](#-passo-a-passo-completo)
- [Validação Pós-Deploy](#-validação-pós-deploy)
- [Solução de Problemas](#-solução-de-problemas)

---

## 🚀 Deploy Automatizado em Servidor Novo

### ⚠️ IMPORTANTE: Como Executar o Deploy Corretamente

O deploy automatizado requer **entrada interativa** para coletar informações como domínio, credenciais, etc.

### ❌ NÃO FAÇA ISSO (não funciona):
```bash
curl -fsSL https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh | sudo bash
```

### ✅ FAÇA ASSIM (correto):

#### **Método 1: Bootstrap (Recomendado)** ⭐
```bash
# No servidor novo Ubuntu 22.04
wget https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh
sudo bash bootstrap.sh
```

#### **Método 2: Usando curl**
```bash
curl -fsSL https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh -o bootstrap.sh
sudo bash bootstrap.sh
```

#### **Método 3: Clonar repositório (Mais seguro)**
```bash
git clone https://github.com/aisuites/novo_iamkt.git /tmp/iamkt
cd /tmp/iamkt
sudo bash scripts/deploy_full_auto.sh
```

---

## � Requisitos do Servidor

### **Sistema Operacional:**
- ✅ Ubuntu 22.04 LTS (limpo, sem instalações prévias)
- ✅ Ubuntu 20.04 LTS (compatível)

### **Hardware Mínimo:**
- ✅ **RAM:** 2GB (recomendado 4GB)
- ✅ **Disco:** 20GB (recomendado 40GB)
- ✅ **CPU:** 1 core (recomendado 2 cores)

### **Rede:**
- ✅ Porta 80 (HTTP) aberta
- ✅ Porta 443 (HTTPS) aberta
- ✅ Domínio apontado para o IP do servidor

### **Acesso:**
- ✅ Acesso root ou sudo
- ✅ Conexão SSH estável

---

## 🔑 Credenciais Necessárias

Prepare as seguintes credenciais **ANTES** de iniciar o deploy:

### **Obrigatórias:**

| Credencial | Exemplo | Onde Obter |
|------------|---------|------------|
| **Nome do Projeto** | `iamkt` ou `vibemkt` | Escolha o nome |
| **Domínio** | `app.iamkt.com.br` | Seu domínio |
| **Email Let's Encrypt** | `admin@iamkt.com.br` | Email válido |
| **Cloudflare API Token** | `abc123...` | Cloudflare Dashboard → API Tokens |
| **AWS Access Key ID** | `AKIA...` | AWS IAM → Usuário → Credenciais |
| **AWS Secret Access Key** | `wJalr...` | AWS IAM → Usuário → Credenciais |
| **AWS S3 Bucket Name** | `iamkt-assets-prod` | AWS S3 → Nome do bucket |
| **OpenAI API Key** | `sk-...` | OpenAI Dashboard → API Keys |

### **Opcionais:**

| Credencial | Quando Usar |
|------------|-------------|
| **Gemini API Key** | Se usar Google Gemini |
| **N8N Allowed IPs** | Se integrar com N8N |
| **Email Host (SMTP)** | Para envio de emails |
| **Email User** | Usuário SMTP |
| **Email Password** | Senha SMTP |

---

## � O que Será Instalado Automaticamente

| Componente | Versão | Descrição |
|------------|--------|-----------|
| **Docker** | Latest | Engine de containers |
| **Docker Compose** | Latest | Orquestração de containers |
| **Traefik** | v2.11 | Proxy reverso + SSL automático |
| **PostgreSQL** | 15-alpine | Banco de dados |
| **Redis** | 7-alpine | Cache + Celery broker |
| **Python** | 3.11 | Runtime da aplicação |
| **Celery** | Latest | Processamento assíncrono |
| **IAMKT App** | Latest | Aplicação do GitHub |

---

## 📝 Passo a Passo Completo

### **Passo 1: Preparar o Servidor**

```bash
# Conectar no servidor via SSH
ssh root@seu-servidor-ip

# Atualizar sistema (opcional mas recomendado)
apt update && apt upgrade -y
```

### **Passo 2: Baixar e Executar Bootstrap**

```bash
# Baixar script
wget https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh

# Executar deploy
sudo bash bootstrap.sh
```

### **Passo 3: Responder às Perguntas Interativas**

O script vai perguntar (em ordem):

#### **3.1 Configuração do Projeto:**
```
Nome do projeto (ex: iamkt, vibemkt): iamkt
Domínio da aplicação (ex: app.vibemkt.aisuites.com.br): app.iamkt.com.br
```

#### **3.2 Credenciais AWS:**
```
AWS Access Key ID: AKIA...
AWS Secret Access Key: wJalr...
AWS S3 Bucket Name: iamkt-assets-prod
```

#### **3.3 Credenciais IA:**
```
OpenAI API Key: sk-...
```

#### **3.4 Configurações Opcionais:**
```
Gemini API Key (opcional): [Enter para pular]
N8N Allowed IPs (opcional): [Enter para pular]
Email Host (ex: smtp.gmail.com): [Enter para pular]
Email User: [Enter para pular]
Email Password: [Enter para pular]
```

### **Passo 4: Aguardar Instalação**

O script executará automaticamente:

1. ✅ Instalação do Docker (2-3 min)
2. ✅ Configuração do Traefik (1 min)
3. ✅ Clone do repositório GitHub (30s)
4. ✅ Geração do `.env.development` (10s)
5. ✅ Geração do `docker-compose.yml` (10s)
6. ✅ Build dos containers (3-5 min)
7. ✅ Execução das migrations (30s)
8. ✅ Criação do superusuário (interativo)

**Tempo total estimado:** 10-15 minutos

### **Passo 5: Criar Superusuário**

```
Email: admin@iamkt.com.br
Password: [sua senha segura]
Password (again): [repetir senha]
```

### **Passo 6: Aguardar SSL**

O certificado SSL será gerado automaticamente em 2-5 minutos.

---

## ✅ Validação Pós-Deploy

### **Verificar Containers:**
```bash
docker ps --filter "name=iamkt"
```

**Esperado:**
```
iamkt_web        Up (healthy)
iamkt_celery     Up (healthy)
iamkt_postgres   Up
iamkt_redis      Up
```

### **Verificar Logs:**
```bash
cd /opt/iamkt
docker compose logs -f
```

### **Testar Aplicação:**
```bash
# Health check
curl https://app.iamkt.com.br/health/

# Acessar no navegador
https://app.iamkt.com.br
https://app.iamkt.com.br/admin/
```

### **Validar Deploy Completo:**
```bash
cd /opt/iamkt
bash scripts/deploy_validate.sh app.iamkt.com.br
```

---

## 📁 Estrutura de Diretórios Criada

```
/opt/
├── iamkt/                      # Aplicação principal
│   ├── app/                    # Código Django
│   ├── docker-compose.yml      # Gerado automaticamente
│   ├── .env.development        # Variáveis de ambiente
│   ├── scripts/                # Scripts auxiliares
│   └── docs/                   # Documentação
│
├── traefik/                    # Proxy reverso
│   ├── traefik.yml             # Configuração
│   ├── letsencrypt/            # Certificados SSL
│   └── oauth2/                 # Autenticação
│
└── backups/
    └── iamkt/                  # Backups do banco
```

---

## 🎯 Deploy para Projetos Diferentes

### **Para VibeMKT/FEMME:**

Quando o script perguntar:
- **Nome do projeto:** `vibemkt` (em vez de `iamkt`)
- **Domínio:** `vibemkt.aisuites.com.br`

Isso criará:
- **Pasta:** `/opt/vibemkt`
- **Containers:** `vibemkt_web`, `vibemkt_postgres`, etc.
- **Volumes:** `vibemkt_postgres_data`, etc.

### **Múltiplos Projetos no Mesmo Servidor:**

Você pode rodar vários projetos no mesmo servidor:
```bash
/opt/iamkt/      → app.iamkt.com.br
/opt/vibemkt/    → vibemkt.aisuites.com.br
/opt/femme/      → app.femme.com.br
```

Cada um terá containers e volumes isolados.

---

## 🔄 Reutilização de Credenciais

### **Pode Reutilizar:**
- ✅ **Cloudflare API Token** - mesmo token serve para múltiplos domínios
- ✅ **AWS Access Keys** - mesmas credenciais AWS
- ✅ **AWS S3 Bucket** - pode usar o mesmo bucket (ou criar novo)
- ✅ **OpenAI API Key** - mesma chave serve para todos os projetos

### **Deve Criar Novo:**
- ⚠️ **Nome do Projeto** - cada deploy deve ter nome único no servidor
- ⚠️ **Domínio** - cada projeto precisa de domínio próprio

---

## 🔧 Mudança de Domínio em Servidor Existente

Para mudar o domínio de um servidor já instalado:

```bash
cd /opt/iamkt

# 1. Editar .env.development
nano .env.development
# Mudar: APP_DOMAIN=devapp.iamkt.com.br

# 2. Regenerar docker-compose.yml
export PROJECT_NAME=iamkt
export APP_DOMAIN=devapp.iamkt.com.br
export DB_PASSWORD=$(grep DB_PASSWORD .env.development | cut -d'=' -f2)

sed -e "s/__PROJECT_NAME__/${PROJECT_NAME}/g" \
    -e "s/__APP_DOMAIN__/${APP_DOMAIN}/g" \
    -e "s/__DB_PASSWORD__/${DB_PASSWORD}/g" \
    docker-compose.yml.template > docker-compose.yml

# 3. Recriar containers
docker compose up -d --force-recreate

# 4. Aguardar novo certificado SSL (2-5 min)
docker logs traefik -f
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
