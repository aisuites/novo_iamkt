# 📋 Estratégia de Migração: UsageLimit → Novo Sistema de Quotas

**Data:** 2025-01-20  
**Fase:** FASE 1.1 - Resolver Duplicidades  
**Status:** Planejado (aguardando aprovação)

---

## 🎯 Objetivo

Migrar o sistema antigo de limites (`UsageLimit`) para o novo sistema multi-tenant baseado em `Organization`, `QuotaUsageDaily` e `QuotaAlert`, mantendo todas as funcionalidades existentes.

---

## 📊 Análise Comparativa

### Sistema ANTIGO (UsageLimit)
```python
class UsageLimit(models.Model):
    area = models.ForeignKey(Area)           # ← Por ÁREA
    month = models.DateField()               # ← Mensal
    max_generations = models.IntegerField()
    max_cost_usd = models.DecimalField()
    current_generations = models.IntegerField()
    current_cost_usd = models.DecimalField()
    alert_80_sent = models.BooleanField()    # ← Alertas por registro
    alert_100_sent = models.BooleanField()
```

**Usado em:**
- `core/admin.py` - UsageLimitAdmin
- `core/views.py` - Dashboard (linhas 68-77)

### Sistema NOVO (Multi-tenant)
```python
# Configuração de limites
class Organization(TimeStampedModel):
    quota_pautas_dia = models.PositiveIntegerField()
    quota_posts_dia = models.PositiveIntegerField()
    quota_posts_mes = models.PositiveIntegerField()
    quota_videos_dia = models.PositiveSmallIntegerField()
    quota_videos_mes = models.PositiveSmallIntegerField()
    alert_80_enabled = models.BooleanField()
    alert_100_enabled = models.BooleanField()
    alert_email = models.EmailField()

# Tracking diário de uso
class QuotaUsageDaily(TimeStampedModel):
    organization = models.ForeignKey(Organization)  # ← Por ORGANIZAÇÃO
    date = models.DateField()                       # ← Diário
    pautas_requested = models.PositiveIntegerField()
    posts_created = models.PositiveIntegerField()
    videos_created = models.PositiveIntegerField()
    cost_usd = models.DecimalField()                # ← Migrado
    pautas_adjustments = models.IntegerField()
    posts_adjustments = models.IntegerField()
    videos_adjustments = models.IntegerField()

# Registro de alertas enviados
class QuotaAlert(TimeStampedModel):
    organization = models.ForeignKey(Organization)
    alert_type = models.CharField()  # '80' ou '100'
    resource_type = models.CharField()  # pauta/post/video
    date = models.DateField()
    sent_to = models.EmailField()
```

---

## 🔄 Estratégia de Migração

### ETAPA 1: Preparação (ATUAL)
✅ **Concluído:**
- [x] Adicionar `cost_usd` em `QuotaUsageDaily`
- [x] Adicionar campos de alertas em `Organization`
- [x] Criar model `QuotaAlert`
- [x] Documentar estratégia

### ETAPA 2: Migration de Dados (PRÓXIMA)

#### 2.1. Criar Organization "FEMME"
```python
# Data migration
organization = Organization.objects.create(
    name='FEMME',
    slug='femme',
    is_active=True,
    approved_at=timezone.now(),
    plan_type='premium',
    
    # Definir quotas baseadas nos limites atuais
    quota_pautas_dia=10,  # Ajustar conforme necessário
    quota_posts_dia=10,
    quota_posts_mes=100,
    quota_videos_dia=5,
    quota_videos_mes=20,
    
    # Alertas habilitados
    alert_80_enabled=True,
    alert_100_enabled=True,
)
```

#### 2.2. Vincular Users e Areas existentes
```python
# Vincular todos os usuários à Organization FEMME
User.objects.all().update(organization=organization)

# Vincular todas as áreas à Organization FEMME
Area.objects.all().update(organization=organization)

# Vincular KnowledgeBase à Organization FEMME
kb = KnowledgeBase.objects.first()
if kb:
    kb.organization = organization
    kb.save()
```

#### 2.3. Migrar dados de UsageLimit → QuotaUsageDaily
```python
from datetime import timedelta
from decimal import Decimal

# Para cada UsageLimit existente
for usage_limit in UsageLimit.objects.all():
    # Calcular quantos dias tem o mês
    month_start = usage_limit.month
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1, day=1)
    
    days_in_month = (month_end - month_start).days
    
    # Distribuir gerações proporcionalmente pelos dias
    avg_generations_per_day = usage_limit.current_generations / days_in_month
    avg_cost_per_day = usage_limit.current_cost_usd / days_in_month
    
    # Criar QuotaUsageDaily para cada dia do mês
    current_date = month_start
    while current_date < month_end:
        QuotaUsageDaily.objects.get_or_create(
            organization=organization,
            date=current_date,
            defaults={
                'pautas_requested': int(avg_generations_per_day),
                'posts_created': 0,  # Não temos dados históricos
                'videos_created': 0,
                'cost_usd': Decimal(str(avg_cost_per_day)),
            }
        )
        current_date += timedelta(days=1)
```

#### 2.4. Migrar alertas enviados
```python
# Para cada UsageLimit que enviou alerta
for usage_limit in UsageLimit.objects.filter(alert_80_sent=True):
    QuotaAlert.objects.get_or_create(
        organization=organization,
        alert_type='80',
        resource_type='pauta_daily',  # Assumindo que era pauta
        date=usage_limit.month,
        defaults={
            'sent_to': organization.owner.email if organization.owner else 'admin@example.com'
        }
    )

for usage_limit in UsageLimit.objects.filter(alert_100_sent=True):
    QuotaAlert.objects.get_or_create(
        organization=organization,
        alert_type='100',
        resource_type='pauta_daily',
        date=usage_limit.month,
        defaults={
            'sent_to': organization.owner.email if organization.owner else 'admin@example.com'
        }
    )
```

### ETAPA 3: Remover UsageLimit

#### 3.1. Remover do Admin
```python
# core/admin.py
# REMOVER:
from .models import UsageLimit
@admin.register(UsageLimit)
class UsageLimitAdmin(admin.ModelAdmin):
    # ...
```

#### 3.2. Remover do Views
```python
# core/views.py
# REMOVER:
from apps.core.models import UsageLimit

# REMOVER (linhas 68-77):
limite = UsageLimit.objects.get(area=user_area, month=current_month)
# ...
```

#### 3.3. Remover model e criar migration
```python
# Criar migration que remove a tabela
python manage.py makemigrations core --name remove_usagelimit
```

---

## ⚠️ Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Perda de dados históricos | Baixa | Alto | Backup completo antes da migração |
| Dashboard quebrar | Média | Alto | Adaptar views antes de remover UsageLimit |
| Alertas não funcionarem | Baixa | Médio | Testar sistema de alertas após migração |
| Distribuição de gerações incorreta | Média | Baixo | Dados históricos são aproximados, não críticos |

---

## ✅ Checklist de Execução

### Pré-Migração
- [ ] Backup completo do banco de dados
- [ ] Testar migrations em ambiente de desenvolvimento
- [ ] Validar que todos os campos necessários existem
- [ ] Confirmar que Organization FEMME será criada

### Durante Migração
- [ ] Executar migrations em ordem correta
- [ ] Criar Organization FEMME
- [ ] Vincular Users, Areas, KnowledgeBase
- [ ] Migrar dados de UsageLimit → QuotaUsageDaily
- [ ] Migrar alertas enviados
- [ ] Validar integridade dos dados migrados

### Pós-Migração
- [ ] Adaptar dashboard (ver BACKLOG.md #001)
- [ ] Remover UsageLimit do admin (ver BACKLOG.md #002)
- [ ] Remover model UsageLimit
- [ ] Testar sistema de quotas
- [ ] Testar sistema de alertas (ver BACKLOG.md #003)
- [ ] Validar que nenhuma query quebrou

---

## 📈 Benefícios do Novo Sistema

1. **Multi-tenant nativo:** Suporta múltiplas organizações
2. **Granularidade diária:** Tracking mais preciso
3. **Tipos específicos:** Distingue pautas, posts e vídeos
4. **Ajustes manuais:** Sistema de devoluções e bônus
5. **Billing cycles:** Ciclos customizáveis por organização
6. **Alertas centralizados:** Sistema unificado de notificações
7. **Escalabilidade:** Preparado para crescimento

---

## 📞 Contato

Em caso de dúvidas ou problemas durante a migração, consultar:
- Documentação: `/opt/iamkt/docs/`
- Backlog: `/opt/iamkt/BACKLOG.md`
- Models: `/opt/iamkt/app/apps/core/models.py`

---

**Última atualização:** 2025-01-20 21:10:00
