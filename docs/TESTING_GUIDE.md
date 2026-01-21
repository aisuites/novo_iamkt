# 🧪 Guia de Testes - Sistema IAMKT Multi-Tenant

## 📋 Pré-requisitos

Antes de testar, certifique-se de que:
- ✅ Todos os containers estão rodando (`docker compose ps`)
- ✅ Migrations foram aplicadas (`docker compose exec -u root iamkt_web python manage.py migrate`)
- ✅ Organization "IAMKT" foi criada
- ✅ Usuário está vinculado à organization

---

## 🚀 Como Testar o Sistema

### **1. Verificar Status dos Containers**

```bash
cd /opt/iamkt
docker compose ps
```

**Esperado:** Todos os containers devem estar `Up` e `healthy`:
- `iamkt_web` - Up (healthy)
- `iamkt_postgres` - Up
- `iamkt_redis` - Up
- `iamkt_celery` - Up (healthy)

---

### **2. Acessar o Dashboard**

**URL:** `http://iamkt-femmeintegra.aisuites.com.br/dashboard/`

**O que você deve ver:**
- ✅ Bem-vindo com seu nome
- ✅ Card "Base de Conhecimento" com percentual
- ✅ Card "Pautas" com total e pendentes
- ✅ Card "Posts" com total, rascunhos e aprovados
- ✅ Card "Quotas de Uso" com 4 métricas:
  - Pautas Hoje (X / Y)
  - Posts Hoje (X / Y)
  - Posts Mês (X / Y)
  - Custo Mês ($X / $Y)
- ✅ Atividades Recentes
- ✅ Trends em Alta

---

### **3. Testar Django Admin**

**URL:** `http://iamkt-femmeintegra.aisuites.com.br/admin/`

**Login:** Use suas credenciais de superuser

**O que testar:**

#### **3.1. Organization**
1. Ir em `Core > Organizations`
2. Clicar em "IAMKT"
3. Verificar:
   - Nome: IAMKT
   - Slug: iamkt
   - Plan Type: premium
   - Quotas configuradas
   - Alertas habilitados

#### **3.2. Quota Usage Daily**
1. Ir em `Core > Quota usage dailies`
2. Verificar se há registros de uso diário
3. Ver: organization, date, pautas_requested, posts_created, cost_usd

#### **3.3. Quota Adjustments**
1. Ir em `Core > Quota adjustments`
2. Testar criar um ajuste manual:
   - Organization: IAMKT
   - Adjustment Type: Bonus
   - Resource Type: Post (Diária)
   - Amount: 5
   - Reason: "Teste de ajuste"

#### **3.4. Quota Alerts**
1. Ir em `Core > Quota alerts`
2. Verificar se há alertas registrados (se houver)
3. Ver: organization, alert_type, resource_type, date, sent_to

---

### **4. Testar Sistema de Quotas**

#### **4.1. Criar uma Pauta**
1. Acessar `/content/pautas/` ou clicar em "Nova Pauta"
2. Preencher dados e salvar
3. Verificar no Admin:
   - `Quota Usage Daily` deve ter incrementado `pautas_requested`

#### **4.2. Criar um Post**
1. Acessar `/content/posts/` ou clicar em "Novo Post"
2. Preencher dados e salvar
3. Verificar no Admin:
   - `Quota Usage Daily` deve ter incrementado `posts_created`

#### **4.3. Verificar Dashboard Atualizado**
1. Voltar ao dashboard
2. Verificar se os números de "Quotas de Uso" foram atualizados
3. Barras de progresso devem refletir o uso atual

---

### **5. Testar Sistema de Alertas (Opcional)**

#### **5.1. Simular Uso Alto**

```bash
# Entrar no shell Django
docker compose exec -u root iamkt_web python manage.py shell

# Executar no shell:
from apps.core.models import Organization, QuotaUsageDaily
from django.utils import timezone
from decimal import Decimal

org = Organization.objects.get(slug='iamkt')
today = timezone.now().date()

# Criar uso alto (90% das quotas)
usage, created = QuotaUsageDaily.objects.get_or_create(
    organization=org,
    date=today,
    defaults={
        'pautas_requested': 18,  # 90% de 20
        'posts_created': 18,     # 90% de 20
        'cost_usd': Decimal('90.0')  # 90% de 100
    }
)

print(f"Uso criado: Pautas={usage.pautas_requested}, Posts={usage.posts_created}")
```

#### **5.2. Executar Verificação de Alertas**

```bash
# Ainda no shell Django:
from apps.core.tasks import check_quota_alerts

result = check_quota_alerts()
print(result)
```

**Esperado:** Se alertas estiverem configurados, você deve ver:
- "Alertas verificados: X enviados"
- Emails enviados para `org.alert_email`
- Registros em `Quota Alerts` no Admin

---

### **6. Verificar Logs**

#### **6.1. Logs do Web Server**
```bash
docker compose logs iamkt_web --tail=50
```

**Procurar por:**
- ✅ `Booting worker with pid: X`
- ✅ `GET /dashboard/ HTTP/1.1" 200`
- ❌ Erros `ProgrammingError` ou `DoesNotExist`

#### **6.2. Logs do Celery**
```bash
docker compose logs iamkt_celery --tail=50
```

**Procurar por:**
- ✅ `celery@X ready`
- ✅ Tasks executando (se houver)

---

## 🐛 Troubleshooting

### **Erro: "relation content_generatedcontent does not exist"**

**Causa:** Cache de Python ou referência antiga

**Solução:**
```bash
# 1. Limpar cache Python
docker compose exec -u root iamkt_web find /app -type f -name "*.pyc" -delete
docker compose exec -u root iamkt_web find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 2. Reiniciar container
docker compose restart iamkt_web

# 3. Se persistir, recriar container
docker compose stop iamkt_web
docker compose rm -f iamkt_web
docker compose up -d iamkt_web
```

---

### **Erro: "System check identified some issues"**

**Causa:** Campos do Admin não correspondem aos models

**Solução:** Já foi corrigido no commit `6fd3500`. Se persistir:
```bash
docker compose exec -u root iamkt_web python manage.py check
```

---

### **Dashboard não mostra quotas**

**Causa:** `QuotaUsageDaily` não existe para hoje

**Solução:**
```bash
# Criar registro de uso para hoje
docker compose exec -u root iamkt_web python manage.py shell

from apps.core.models import Organization, QuotaUsageDaily
from django.utils import timezone

org = Organization.objects.get(slug='iamkt')
today = timezone.now().date()

usage, created = QuotaUsageDaily.objects.get_or_create(
    organization=org,
    date=today,
    defaults={
        'pautas_requested': 0,
        'posts_created': 0,
        'videos_created': 0,
        'cost_usd': 0
    }
)

print(f"Uso criado: {usage}")
```

---

### **Alertas não estão sendo enviados**

**Verificar:**
1. Organization tem `alert_enabled=True`
2. Organization tem `alert_email` configurado
3. Celery Beat está rodando
4. Configuração de email está correta

**Testar manualmente:**
```bash
docker compose exec -u root iamkt_web python manage.py shell

from apps.core.tasks import check_quota_alerts
result = check_quota_alerts()
print(result)
```

---

## ✅ Checklist de Validação

Marque conforme testa:

- [ ] Containers rodando e healthy
- [ ] Dashboard carrega sem erros
- [ ] Dashboard mostra quotas corretamente
- [ ] Admin acessível
- [ ] Organization visível no Admin
- [ ] QuotaUsageDaily visível no Admin
- [ ] Pode criar Pauta
- [ ] Pode criar Post
- [ ] Quotas incrementam após criação
- [ ] Dashboard atualiza após criação
- [ ] Sistema de alertas funciona (opcional)

---

## 🎉 Sistema Validado!

Se todos os itens acima funcionarem, o sistema está **100% operacional** e pronto para uso!

**Próximos passos:**
- Usar o sistema normalmente
- Monitorar quotas no dashboard
- Ajustar quotas conforme necessário
- Implementar FASE 4 (Autenticação/Onboarding) quando necessário
