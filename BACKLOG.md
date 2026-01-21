# 📋 BACKLOG - Tarefas Futuras do Projeto IAMKT Multi-Tenant

**Última Atualização:** 2026-01-20 22:00:00

---

## ✅ ITEM #001 - Adaptar Dashboard para novo sistema de quotas
**Data de Cadastro:** 2025-01-20 21:03:00  
**Data de Conclusão:** 2026-01-20 22:00:00  
**Status:** ✅ **CONCLUÍDO**  
**Prioridade:** MÉDIA  
**Fase:** FASE 5 - Adaptar Views e Templates

### O que será feito:
Adaptar a view `dashboard()` em `/opt/iamkt/app/apps/core/views.py` (linhas 68-77) para usar o novo sistema de quotas baseado em `Organization` e `QuotaUsageDaily` ao invés de `UsageLimit`.

### Como fazer:
1. Remover código que busca `UsageLimit` por área:
   ```python
   # REMOVER:
   limite = UsageLimit.objects.get(area=user_area, month=current_month)
   ```

2. Substituir por busca de quotas da Organization:
   ```python
   # ADICIONAR:
   organization = request.user.organization
   today = timezone.now().date()
   
   # Buscar uso diário
   quota_usage = QuotaUsageDaily.objects.filter(
       organization=organization,
       date=today
   ).first()
   
   # Calcular uso mensal
   posts_month = organization.get_posts_this_month()
   
   limite_info = {
       'pautas_used': quota_usage.pautas_used if quota_usage else 0,
       'pautas_max': organization.quota_pautas_dia,
       'posts_used': quota_usage.posts_used if quota_usage else 0,
       'posts_max': organization.quota_posts_dia,
       'posts_month_used': posts_month,
       'posts_month_max': organization.quota_posts_mes,
       'cost_current': quota_usage.cost_usd if quota_usage else 0,
   }
   ```

3. Atualizar template `dashboard.html` para exibir novos dados

### Por que é importante:
- Dashboard é a página principal do sistema
- Usuários precisam ver seus limites e uso atual
- Informação crítica para controle de quotas
- Sem isso, usuários não saberão quanto já usaram

### Dependências:
- Aguarda conclusão da FASE 1 (limpeza de duplicidades)
- Aguarda migrations aplicadas
- Aguarda migração de dados existentes

### Impacto se não for feito:
- Dashboard continuará tentando buscar `UsageLimit` (que será removido)
- Erro 500 ao acessar dashboard após migrations
- Usuários não verão informações de quota

---

## ✅ ITEM #002 - Remover UsageLimit do Admin
**Data de Cadastro:** 2025-01-20 21:03:00  
**Data de Conclusão:** 2026-01-20 22:00:00  
**Status:** ✅ **CONCLUÍDO**  
**Prioridade:** BAIXA  
**Fase:** FASE 1 - Limpeza e Correção de Estrutura

### O que será feito:
Remover registro de `UsageLimitAdmin` do Django Admin em `/opt/iamkt/app/apps/core/admin.py` (linhas 28-40).

### Como fazer:
1. Remover import: `from .models import UsageLimit`
2. Remover decorator e classe completa:
   ```python
   # REMOVER:
   @admin.register(UsageLimit)
   class UsageLimitAdmin(admin.ModelAdmin):
       # ... todo o código ...
   ```

3. Adicionar novos admins para models de quota:
   ```python
   @admin.register(QuotaUsageDaily)
   class QuotaUsageDailyAdmin(admin.ModelAdmin):
       list_display = ['organization', 'date', 'pautas_used', 'posts_used', 'videos_created', 'cost_usd']
       list_filter = ['date', 'organization']
       search_fields = ['organization__name']
       readonly_fields = ['created_at', 'updated_at']
   
   @admin.register(QuotaAlert)
   class QuotaAlertAdmin(admin.ModelAdmin):
       list_display = ['organization', 'alert_type', 'resource_type', 'date', 'sent_at']
       list_filter = ['alert_type', 'resource_type', 'date']
       search_fields = ['organization__name']
       readonly_fields = ['sent_at']
   ```

### Por que é importante:
- Manter admin limpo e organizado
- Evitar confusão com models obsoletas
- Admins precisam gerenciar quotas pelo novo sistema

### Dependências:
- Aguarda remoção completa de UsageLimit do código
- Aguarda migrations aplicadas

### Impacto se não for feito:
- Admin terá link para model que não existe mais
- Erro ao tentar acessar UsageLimit no admin

---

## 📌 ITEM #003 - Criar sistema de envio de alertas de quota
**Data de Cadastro:** 2025-01-20 21:03:00  
**Prioridade:** ALTA  
**Fase:** FASE 6 - Testes e Validação (após implementação básica)

### O que será feito:
Implementar sistema automatizado de envio de alertas quando organization atingir 80% ou 100% das quotas diárias/mensais.

### Como fazer:
1. Criar task Celery (ou management command) para verificar quotas:
   ```python
   # apps/core/tasks.py
   from celery import shared_task
   
   @shared_task
   def check_quota_alerts():
       """Verifica quotas e envia alertas se necessário"""
       today = timezone.now().date()
       
       for org in Organization.objects.filter(is_active=True):
           usage = org.get_quota_usage_today()
           
           # Verificar pautas (80%)
           if usage['pautas_used'] >= org.quota_pautas_dia * 0.8:
               send_quota_alert(org, 'pauta', '80')
           
           # Verificar posts diários (100%)
           if usage['posts_used'] >= org.quota_posts_dia:
               send_quota_alert(org, 'post', '100')
   ```

2. Criar função de envio de email:
   ```python
   def send_quota_alert(organization, resource_type, alert_type):
       # Verificar se já enviou hoje
       if QuotaAlert.objects.filter(
           organization=organization,
           resource_type=resource_type,
           alert_type=alert_type,
           date=timezone.now().date()
       ).exists():
           return
       
       # Enviar email para owner
       send_mail(
           subject=f'Alerta de Quota - {alert_type}% atingido',
           message=f'Sua organização atingiu {alert_type}% da quota de {resource_type}',
           recipient_list=[organization.owner.email]
       )
       
       # Registrar alerta enviado
       QuotaAlert.objects.create(
           organization=organization,
           resource_type=resource_type,
           alert_type=alert_type,
           date=timezone.now().date()
       )
   ```

3. Configurar Celery Beat para rodar a cada hora:
   ```python
   # settings.py
   CELERY_BEAT_SCHEDULE = {
       'check-quota-alerts': {
           'task': 'apps.core.tasks.check_quota_alerts',
           'schedule': crontab(minute=0),  # A cada hora
       },
   }
   ```

### Por que é importante:
- Usuários precisam ser notificados quando estão próximos do limite
- Evita surpresas quando quota é atingida
- Permite planejamento de upgrade de plano
- Funcionalidade existente no sistema antigo (UsageLimit)

### Dependências:
- Aguarda model QuotaAlert criada
- Aguarda Celery configurado (ou usar management command)
- Aguarda sistema de emails configurado

### Impacto se não for feito:
- Usuários não serão avisados quando quota estiver acabando
- Podem atingir limite sem aviso prévio
- Experiência do usuário prejudicada

---

## 📊 Estatísticas do Backlog
- **Total de Itens:** 3
- **Prioridade Alta:** 1
- **Prioridade Média:** 1
- **Prioridade Baixa:** 1
- **Fase 1:** 1 item
- **Fase 5:** 1 item
- **Fase 6:** 1 item

---

## 📝 Notas
- Este arquivo será atualizado conforme novas tarefas forem identificadas
- Cada item deve ter data de cadastro e descrição detalhada
- Prioridades podem ser ajustadas conforme necessidade do projeto
- Itens concluídos devem ser movidos para seção "Concluídos" (criar quando necessário)
