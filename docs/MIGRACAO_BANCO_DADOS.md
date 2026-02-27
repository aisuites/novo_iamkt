# 🗄️ Migração de Banco de Dados - IAMKT

## 📋 Índice
- [Visão Geral](#-visão-geral)
- [Backup do Servidor Atual](#-backup-do-servidor-atual)
- [Transferência para Servidor Novo](#-transferência-para-servidor-novo)
- [Restauração no Servidor Novo](#-restauração-no-servidor-novo)
- [Validação Pós-Migração](#-validação-pós-migração)
- [Solução de Problemas](#-solução-de-problemas)

---

## 🎯 Visão Geral

Este guia explica como migrar todos os dados do banco de dados PostgreSQL do servidor atual para o servidor novo.

### **O Que Será Migrado:**
- ✅ Todos os dados das tabelas
- ✅ Usuários e permissões
- ✅ Pautas, posts e conteúdos
- ✅ Configurações da aplicação
- ✅ Histórico completo

### **O Que NÃO Será Migrado:**
- ❌ Arquivos de mídia (imagens, vídeos) - ver seção separada
- ❌ Configurações do servidor (Docker, Traefik)
- ❌ Logs da aplicação

---

## 💾 Backup do Servidor Atual

### **Passo 1: Conectar no Servidor Atual**

```bash
ssh root@servidor-atual-ip
cd /opt/iamkt
```

### **Passo 2: Executar Script de Backup**

```bash
bash scripts/backup_database.sh
```

**O script irá:**
1. ✅ Criar backup completo do PostgreSQL
2. ✅ Comprimir o arquivo (`.sql.gz`)
3. ✅ Salvar em `/opt/backups/iamkt/`
4. ✅ Mostrar instruções de transferência

**Saída esperada:**
```
[INFO] Iniciando backup do banco de dados...
[INFO] Container: iamkt_postgres
[INFO] Database: iamkt_db
[INFO] Executando pg_dump...
[✓] Backup SQL criado com sucesso!
[✓] Backup comprimido com sucesso!
[✓] Arquivo: /opt/backups/iamkt/iamkt_backup_20260227_120000.sql.gz
[✓] Tamanho: 2.5M
```

### **Passo 3: Verificar Backup Criado**

```bash
ls -lh /opt/backups/iamkt/
```

**Exemplo:**
```
-rw-r--r-- 1 root root 2.5M Feb 27 12:00 iamkt_backup_20260227_120000.sql.gz
```

---

## 📤 Transferência para Servidor Novo

### **Método 1: SCP (Recomendado)**

```bash
# No servidor atual
scp /opt/backups/iamkt/iamkt_backup_20260227_120000.sql.gz \
    root@servidor-novo-ip:/tmp/
```

### **Método 2: Download Local + Upload**

```bash
# Baixar do servidor atual para sua máquina
scp root@servidor-atual-ip:/opt/backups/iamkt/iamkt_backup_20260227_120000.sql.gz \
    ~/Downloads/

# Enviar para servidor novo
scp ~/Downloads/iamkt_backup_20260227_120000.sql.gz \
    root@servidor-novo-ip:/tmp/
```

### **Método 3: Via URL (se tiver acesso web)**

```bash
# No servidor atual, criar servidor HTTP temporário
cd /opt/backups/iamkt
python3 -m http.server 8888

# No servidor novo, baixar
wget http://servidor-atual-ip:8888/iamkt_backup_20260227_120000.sql.gz -O /tmp/backup.sql.gz
```

---

## 📥 Restauração no Servidor Novo

### **Pré-requisitos:**

1. ✅ Deploy já executado no servidor novo
2. ✅ Containers rodando (`docker ps`)
3. ✅ Backup transferido para `/tmp/`

### **Passo 1: Conectar no Servidor Novo**

```bash
ssh root@servidor-novo-ip
cd /opt/iamkt
```

### **Passo 2: Verificar Backup**

```bash
ls -lh /tmp/*.sql.gz
```

### **Passo 3: Executar Restauração**

```bash
bash scripts/restore_database.sh /tmp/iamkt_backup_20260227_120000.sql.gz
```

**O script irá:**
1. ⚠️ Pedir confirmação (digite `SIM`)
2. 🛑 Parar containers da aplicação
3. 📥 Descomprimir e restaurar backup
4. 🔄 Reiniciar containers
5. ✅ Validar restauração

**Saída esperada:**
```
[!] ATENÇÃO: Este processo irá SUBSTITUIR todos os dados do banco atual!
[INFO] Arquivo de backup: /tmp/iamkt_backup_20260227_120000.sql.gz

Deseja continuar? (digite 'SIM' para confirmar): SIM

[INFO] Iniciando restauração do banco de dados...
[INFO] Descomprimindo backup...
[✓] Backup preparado para restauração
[INFO] Parando containers da aplicação...
[✓] Containers parados
[INFO] Restaurando banco de dados...
[✓] Banco de dados restaurado com sucesso!
[INFO] Reiniciando containers da aplicação...
[✓] Containers reiniciados

=========================================================================
RESTAURAÇÃO CONCLUÍDA COM SUCESSO!
=========================================================================
```

---

## ✅ Validação Pós-Migração

### **1. Verificar Containers:**

```bash
docker compose ps
```

**Esperado:**
```
iamkt_web        Up (healthy)
iamkt_celery     Up (healthy)
iamkt_postgres   Up
iamkt_redis      Up
```

### **2. Verificar Logs:**

```bash
docker compose logs -f iamkt_web
```

**Procurar por:**
- ✅ Sem erros de conexão com banco
- ✅ Aplicação iniciada corretamente

### **3. Acessar Aplicação:**

```bash
# Testar health check
curl https://app.iamkt.com.br/health/

# Acessar no navegador
https://app.iamkt.com.br/admin/
```

### **4. Fazer Login:**

Use as **mesmas credenciais** do servidor atual:
- Email: (seu email de admin)
- Senha: (sua senha de admin)

### **5. Verificar Dados:**

No admin, verificar:
- ✅ Usuários existem
- ✅ Pautas estão presentes
- ✅ Posts estão presentes
- ✅ Configurações preservadas

---

## 📊 Migração de Arquivos de Mídia (Opcional)

Se você tem arquivos de mídia (imagens, vídeos) armazenados localmente:

### **No Servidor Atual:**

```bash
# Criar backup dos arquivos de mídia
cd /opt/iamkt
tar -czf /tmp/iamkt_media.tar.gz -C /var/lib/docker/volumes/iamkt_media/_data .

# Transferir para servidor novo
scp /tmp/iamkt_media.tar.gz root@servidor-novo-ip:/tmp/
```

### **No Servidor Novo:**

```bash
# Parar aplicação
cd /opt/iamkt
docker compose stop iamkt_web iamkt_celery

# Restaurar arquivos de mídia
docker run --rm -v iamkt_media:/media -v /tmp:/backup alpine \
    sh -c "cd /media && tar -xzf /backup/iamkt_media.tar.gz"

# Reiniciar aplicação
docker compose up -d iamkt_web iamkt_celery
```

---

## 🔄 Processo Completo de Migração

### **Resumo Passo a Passo:**

```bash
# ========================================
# SERVIDOR ATUAL
# ========================================
ssh root@servidor-atual-ip
cd /opt/iamkt

# 1. Fazer backup
bash scripts/backup_database.sh

# 2. Transferir backup
scp /opt/backups/iamkt/iamkt_backup_*.sql.gz root@servidor-novo-ip:/tmp/

# (Opcional) Backup de mídia
tar -czf /tmp/iamkt_media.tar.gz -C /var/lib/docker/volumes/iamkt_media/_data .
scp /tmp/iamkt_media.tar.gz root@servidor-novo-ip:/tmp/


# ========================================
# SERVIDOR NOVO
# ========================================
ssh root@servidor-novo-ip

# 1. Fazer deploy (se ainda não fez)
wget https://raw.githubusercontent.com/aisuites/novo_iamkt/main/scripts/bootstrap.sh
sudo bash bootstrap.sh

# 2. Restaurar banco de dados
cd /opt/iamkt
bash scripts/restore_database.sh /tmp/iamkt_backup_*.sql.gz

# 3. (Opcional) Restaurar mídia
docker compose stop iamkt_web iamkt_celery
docker run --rm -v iamkt_media:/media -v /tmp:/backup alpine \
    sh -c "cd /media && tar -xzf /backup/iamkt_media.tar.gz"
docker compose up -d

# 4. Validar
docker compose ps
curl https://app.iamkt.com.br/health/
```

---

## ⏱️ Tempo Estimado

| Etapa | Tempo |
|-------|-------|
| Backup do banco | 1-3 min |
| Transferência (depende da conexão) | 2-10 min |
| Restauração | 2-5 min |
| Validação | 2 min |
| **Total** | **7-20 min** |

---

## 🆘 Solução de Problemas

### **Erro: "Container não está rodando"**

```bash
cd /opt/iamkt
docker compose up -d
docker compose ps
```

### **Erro: "Permission denied" ao restaurar**

```bash
chmod +x scripts/restore_database.sh
```

### **Erro: Backup muito grande para transferir**

Use compressão adicional:
```bash
# Comprimir ainda mais
xz /opt/backups/iamkt/iamkt_backup_*.sql.gz
# Transferir arquivo .xz
```

### **Erro: "Database is being accessed by other users"**

```bash
# Parar todos os containers que acessam o banco
docker compose stop iamkt_web iamkt_celery

# Tentar restauração novamente
bash scripts/restore_database.sh /tmp/backup.sql.gz
```

### **Dados não aparecem após restauração**

```bash
# Verificar logs do PostgreSQL
docker compose logs iamkt_postgres

# Verificar logs da aplicação
docker compose logs iamkt_web

# Recriar containers
docker compose down
docker compose up -d
```

---

## 🔒 Segurança

### **Boas Práticas:**

1. ✅ **Sempre teste o backup** antes de fazer mudanças críticas
2. ✅ **Mantenha múltiplos backups** (não apenas um)
3. ✅ **Delete backups do /tmp** após restauração
4. ✅ **Use conexões SSH seguras** para transferência
5. ✅ **Verifique permissões** dos arquivos de backup

### **Limpeza Pós-Migração:**

```bash
# No servidor novo, após validar que tudo funciona
rm /tmp/iamkt_backup_*.sql.gz
rm /tmp/iamkt_media.tar.gz
```

---

## 📚 Comandos Úteis

### **Verificar tamanho do banco:**

```bash
docker exec iamkt_postgres psql -U iamkt_user -d iamkt_db -c \
    "SELECT pg_size_pretty(pg_database_size('iamkt_db'));"
```

### **Listar tabelas:**

```bash
docker exec iamkt_postgres psql -U iamkt_user -d iamkt_db -c "\dt"
```

### **Contar registros:**

```bash
docker exec iamkt_postgres psql -U iamkt_user -d iamkt_db -c \
    "SELECT 'posts' as table, COUNT(*) FROM posts_post 
     UNION ALL 
     SELECT 'pautas', COUNT(*) FROM content_pauta;"
```

### **Backup manual (sem script):**

```bash
docker exec iamkt_postgres pg_dump -U iamkt_user iamkt_db > backup.sql
```

---

## ✅ Checklist de Migração

- [ ] Backup criado no servidor atual
- [ ] Backup transferido para servidor novo
- [ ] Deploy executado no servidor novo
- [ ] Restauração executada com sucesso
- [ ] Containers rodando sem erros
- [ ] Login funciona com credenciais antigas
- [ ] Dados visíveis no admin
- [ ] Health check retorna OK
- [ ] Aplicação acessível via HTTPS
- [ ] Arquivos de mídia migrados (se aplicável)
- [ ] Backups temporários deletados
- [ ] DNS atualizado (se necessário)

---

**Migração completa! Seu banco de dados foi transferido com sucesso.** 🎉
