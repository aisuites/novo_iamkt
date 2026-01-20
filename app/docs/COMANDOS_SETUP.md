# Comandos para Setup do IAMKT MVP

## 🐳 Build e Deploy dos Containers

### 1. Build da Imagem Docker (com novas dependências)
```bash
cd /opt/iamkt
docker-compose build --no-cache
```

### 2. Subir os Containers
```bash
docker-compose up -d
```

### 3. Verificar Status dos Containers
```bash
docker-compose ps
```

### 4. Ver Logs
```bash
# Todos os containers
docker-compose logs -f

# Apenas web
docker-compose logs -f iamkt_web

# Apenas celery
docker-compose logs -f iamkt_celery
```

## 📊 Migrations e Banco de Dados

### 5. Criar Migrations
```bash
docker-compose exec iamkt_web python manage.py makemigrations
```

### 6. Aplicar Migrations
```bash
docker-compose exec iamkt_web python manage.py migrate
```

### 7. Criar Superusuário
```bash
docker-compose exec iamkt_web python manage.py createsuperuser
```

## 🔧 Comandos Úteis

### Acessar Shell do Container
```bash
docker-compose exec iamkt_web bash
```

### Acessar Django Shell
```bash
docker-compose exec iamkt_web python manage.py shell
```

### Coletar Arquivos Estáticos
```bash
docker-compose exec iamkt_web python manage.py collectstatic --noinput
```

### Verificar Configurações
```bash
docker-compose exec iamkt_web python manage.py check
```

## 🔄 Rebuild Após Mudanças

### Rebuild Apenas Web
```bash
docker-compose up -d --build iamkt_web
```

### Rebuild Apenas Celery
```bash
docker-compose up -d --build iamkt_celery
```

### Restart Serviços
```bash
docker-compose restart iamkt_web
docker-compose restart iamkt_celery
```

## 🧹 Limpeza

### Parar Containers
```bash
docker-compose down
```

### Parar e Remover Volumes (CUIDADO: apaga dados!)
```bash
docker-compose down -v
```

## 📝 Notas Importantes

1. **Sempre execute comandos Django dentro do container** usando `docker-compose exec`
2. **Não instale dependências Python no host** - tudo roda dentro do Docker
3. **O código em `/opt/iamkt/app/` é montado como volume** - mudanças são refletidas automaticamente
4. **Para mudanças no `requirements.txt`** - faça rebuild da imagem
5. **Para mudanças em models** - crie e aplique migrations
6. **Celery já está configurado** e roda automaticamente no container `iamkt_celery`

## 🎯 Ordem de Execução Recomendada

```bash
# 1. Build
cd /opt/iamkt
docker-compose build --no-cache

# 2. Subir
docker-compose up -d

# 3. Aguardar containers iniciarem (30-60s)
sleep 60

# 4. Verificar status
docker-compose ps

# 5. Criar migrations
docker-compose exec iamkt_web python manage.py makemigrations

# 6. Aplicar migrations
docker-compose exec iamkt_web python manage.py migrate

# 7. Criar superusuário
docker-compose exec iamkt_web python manage.py createsuperuser

# 8. Acessar: https://iamkt-femmeintegra.aisuites.com.br
```

## ⚠️ Troubleshooting

### Container não sobe
```bash
# Ver logs detalhados
docker-compose logs iamkt_web

# Verificar se portas estão em uso
docker ps -a
```

### Erro de dependências
```bash
# Rebuild sem cache
docker-compose build --no-cache iamkt_web
```

### Erro de migrations
```bash
# Entrar no container e debugar
docker-compose exec iamkt_web bash
python manage.py showmigrations
```
