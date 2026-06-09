from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.utils import timezone
from .models import (
    User, Area, AuditLog, SystemConfig, PlanTemplate,
    Organization, QuotaUsageDaily, QuotaAdjustment, QuotaAlert
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'organization', 'profile', 'is_active']
    list_filter = ['organization', 'profile', 'is_active', 'is_staff', 'areas']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    filter_horizontal = ['areas', 'groups', 'user_permissions']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informações Adicionais', {
            'fields': ('organization', 'profile', 'areas', 'phone')
        }),
    )


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'created_at']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def has_add_permission(self, request):
        """Apenas superuser pode criar áreas"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Apenas superuser pode editar áreas"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Apenas superuser pode deletar áreas"""
        return request.user.is_superuser


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_repr', 'created_at']
    list_filter = ['action', 'model_name', 'created_at']
    search_fields = ['user__username', 'object_repr']
    readonly_fields = ['user', 'action', 'model_name', 'object_id', 'object_repr', 
                      'changes', 'ip_address', 'user_agent', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PlanTemplate)
class PlanTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'plan_type', 'quota_pautas_dia', 
        'quota_posts_dia', 'quota_posts_mes',
        'videos_avatar_enabled', 'is_active', 'is_default', 'display_order'
    ]
    list_filter = ['plan_type', 'is_active', 'is_default', 'videos_avatar_enabled']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('plan_type', 'name', 'description')
        }),
        ('Quotas de Conteúdo', {
            'fields': (
                'quota_pautas_dia',
                'quota_posts_dia',
                'quota_posts_mes'
            ),
            'description': 'Limites de criação de pautas e posts'
        }),
        ('Quotas de Vídeos Avatar', {
            'fields': (
                'videos_avatar_enabled',
                'quota_videos_dia',
                'quota_videos_mes'
            ),
            'description': 'Configurações de vídeos com avatar IA'
        }),
        ('Configurações', {
            'fields': ('is_active', 'is_default', 'display_order'),
            'description': 'is_default: Plano aplicado automaticamente em aprovações'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        """Apenas superuser pode deletar templates de plano"""
        return request.user.is_superuser
    
    def save_model(self, request, obj, form, change):
        """Se marcar como padrão, desmarcar outros"""
        if obj.is_default:
            PlanTemplate.objects.filter(is_default=True).exclude(pk=obj.pk).update(is_default=False)
        super().save_model(request, obj, form, change)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'status_badge', 'plan_type', 'modules_summary', 'uso_hoje',
        'billing_cycle_day', 'created_at'
    ]
    list_filter = ['plan_type', 'is_active', 'suspension_reason', 'requested_plan', 'created_at']
    search_fields = ['name', 'slug', 'cpf']
    readonly_fields = ['created_at', 'updated_at', 'approved_at', 'approved_by',
                       'requested_plan', 'payment_reference']
    
    actions = [
        'approve_with_template',
        'approve_as_free',
        'approve_as_basic',
        'approve_as_premium',
        'suspend_for_payment',
        'suspend_for_terms',
        'suspend_canceled',
        'reactivate_organizations'
    ]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'slug', 'tagline', 'owner')
        }),
        ('Plano e Status', {
            'fields': ('plan_type', 'is_active', 'suspension_reason', 'approved_at', 'approved_by')
        }),
        ('Cadastro e Cobrança', {
            'fields': ('cpf', 'requested_plan', 'payment_reference'),
            'description': 'CPF do responsável e dados do cadastro vindo do site '
                           '(plano solicitado e referência do pagamento são preenchidos pelo fluxo)'
        }),
        ('Módulos e Ferramentas', {
            'fields': (
                'pautas_enabled',
                'posts_enabled',
                'trends_enabled',
                'videos_avatar_enabled',
                'email_marketing_enabled'
            ),
            'description': 'Habilite/desabilite ferramentas para esta empresa'
        }),
        ('Quotas de Conteúdo', {
            'fields': (
                'quota_pautas_dia',
                'quota_posts_dia',
                'quota_posts_mes',
                'max_image_revisions'
            ),
            'description': 'Limites de criação de conteúdo e alterações de imagem'
        }),
        ('Quotas de Vídeos Avatar', {
            'fields': (
                'quota_videos_dia',
                'quota_videos_mes'
            )
        }),
        ('Billing Cycle', {
            'fields': ('billing_cycle_day',),
            'description': 'Dia do mês que reseta a quota mensal (1-28)'
        }),
        ('Alertas', {
            'fields': ('alert_80_enabled', 'alert_100_enabled', 'alert_email'),
            'classes': ('collapse',)
        }),
        ('Notas Internas', {
            'fields': ('internal_notes',),
            'classes': ('collapse',),
            'description': 'Notas internas da equipe (não visível para cliente)'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # ========================================
    # MÉTODOS CUSTOMIZADOS - List Display
    # ========================================
    
    def status_badge(self, obj):
        """Badge colorido de status"""
        from django.utils.html import format_html
        
        if obj.is_active:
            return format_html(
                '<span style="background:#28a745;color:white;padding:4px 8px;border-radius:4px;font-weight:600;">✅ Ativa</span>'
            )
        else:
            reason = obj.get_suspension_reason_display()
            if obj.suspension_reason == 'pending':
                color = '#ffc107'  # Amarelo
                icon = '⚠️'
            elif obj.suspension_reason == 'payment':
                color = '#dc3545'  # Vermelho
                icon = '💳'
            elif obj.suspension_reason == 'terms':
                color = '#dc3545'  # Vermelho
                icon = '⚠️'
            elif obj.suspension_reason == 'canceled':
                color = '#6c757d'  # Cinza
                icon = '🚫'
            else:
                color = '#6c757d'
                icon = '⚠️'
            
            return format_html(
                '<span style="background:{};color:#000;padding:4px 8px;border-radius:4px;font-weight:600;">{} {}</span>',
                color, icon, reason
            )
    status_badge.short_description = 'Status'
    
    def uso_hoje(self, obj):
        """Mostra uso de quotas hoje"""
        usage = obj.get_quota_usage_today()
        return f"Pautas: {usage['pautas_used']}/{obj.quota_pautas_dia} | Posts: {usage['posts_used']}/{obj.quota_posts_dia}"
    uso_hoje.short_description = 'Uso Hoje'
    
    def modules_summary(self, obj):
        """Mostra resumo dos módulos habilitados"""
        modules = []
        if obj.pautas_enabled:
            modules.append('<span style="color:green;">✅ Pautas</span>')
        if obj.posts_enabled:
            modules.append('<span style="color:green;">✅ Posts</span>')
        if obj.trends_enabled:
            modules.append('<span style="color:green;">✅ Trends</span>')
        if obj.videos_avatar_enabled:
            modules.append('<span style="color:green;">✅ Vídeos</span>')
        if obj.email_marketing_enabled:
            modules.append('<span style="color:green;">✅ Email</span>')
        
        if not modules:
            modules.append('<span style="color:red;">❌ Nenhum</span>')
            
        return ' '.join(modules)
    modules_summary.short_description = 'Módulos'
    modules_summary.allow_tags = True
    
    # ========================================
    # ACTIONS - Aprovação e Gestão de Planos
    # ========================================
    
    def approve_with_template(self, request, queryset):
        """✅ Aprovar usando template de plano configurável"""
        # Buscar template padrão ou primeiro ativo
        template = PlanTemplate.objects.filter(is_active=True, is_default=True).first()
        
        if not template:
            template = PlanTemplate.objects.filter(is_active=True).first()
        
        if not template:
            self.message_user(
                request,
                'Nenhum template de plano ativo encontrado. Configure em Templates de Planos.',
                messages.ERROR
            )
            return
        
        count = 0
        users_activated = 0
        for org in queryset:
            # Definir approved_at se ainda não tiver (primeira aprovação)
            if not org.approved_at:
                org.approved_at = timezone.now()
                org.approved_by = request.user
            
            org.is_active = True
            org.suspension_reason = ''
            
            # Aplicar template
            template.apply_to_organization(org)
            org.save()
            
            # ✅ Ativar todos os usuários da organização
            users_activated += org.users.filter(is_active=False).update(is_active=True)
            
            count += 1
        
        self.message_user(
            request,
            f'{count} organização(ões) aprovada(s) com template "{template.name}". {users_activated} usuário(s) ativado(s).',
            messages.SUCCESS
        )
    approve_with_template.short_description = "✅ Aprovar com Template Configurável"
    
    def approve_as_free(self, request, queryset):
        """✅ Aprovar organizações como plano FREE"""
        # Tentar usar template
        template = PlanTemplate.objects.filter(plan_type='free', is_active=True).first()
        
        count = 0
        users_activated = 0
        for org in queryset:
            # Definir approved_at se ainda não tiver (primeira aprovação)
            if not org.approved_at:
                org.approved_at = timezone.now()
                org.approved_by = request.user
            
            org.is_active = True
            org.suspension_reason = ''
            
            if template:
                # Usar template configurável
                template.apply_to_organization(org)
            else:
                # Fallback: valores hardcoded (compatibilidade)
                org.plan_type = 'free'
                org.quota_pautas_dia = 3
                org.quota_posts_dia = 3
                org.quota_posts_mes = 15
            
            org.save()
            
            # ✅ Ativar todos os usuários da organização
            users_activated += org.users.filter(is_active=False).update(is_active=True)
            
            count += 1
        
        quota_info = f"({org.quota_pautas_dia}/{org.quota_posts_dia}/{org.quota_posts_mes})"
        self.message_user(
            request,
            f'{count} organização(ões) aprovada(s) como FREE {quota_info}. {users_activated} usuário(s) ativado(s).',
            messages.SUCCESS
        )
    approve_as_free.short_description = "✅ Aprovar como FREE (3/3/15)"
    
    def approve_as_basic(self, request, queryset):
        """✅ Aprovar organizações como plano BASIC"""
        # Tentar usar template
        template = PlanTemplate.objects.filter(plan_type='basic', is_active=True).first()
        
        count = 0
        users_activated = 0
        for org in queryset:
            # Definir approved_at se ainda não tiver (primeira aprovação)
            if not org.approved_at:
                org.approved_at = timezone.now()
                org.approved_by = request.user
            
            org.is_active = True
            org.suspension_reason = ''
            
            if template:
                # Usar template configurável
                template.apply_to_organization(org)
            else:
                # Fallback: valores hardcoded (compatibilidade)
                org.plan_type = 'basic'
                org.quota_pautas_dia = 5
                org.quota_posts_dia = 5
                org.quota_posts_mes = 30
            
            org.save()
            
            # ✅ Ativar todos os usuários da organização
            users_activated += org.users.filter(is_active=False).update(is_active=True)
            
            count += 1
        
        quota_info = f"({org.quota_pautas_dia}/{org.quota_posts_dia}/{org.quota_posts_mes})"
        self.message_user(
            request,
            f'{count} organização(ões) aprovada(s) como BASIC {quota_info}. {users_activated} usuário(s) ativado(s).',
            messages.SUCCESS
        )
    approve_as_basic.short_description = "✅ Aprovar como BASIC (5/5/30)"
    
    def approve_as_premium(self, request, queryset):
        """✅ Aprovar organizações como plano PREMIUM"""
        # Tentar usar template
        template = PlanTemplate.objects.filter(plan_type='premium', is_active=True).first()
        
        count = 0
        users_activated = 0
        for org in queryset:
            # Definir approved_at se ainda não tiver (primeira aprovação)
            if not org.approved_at:
                org.approved_at = timezone.now()
                org.approved_by = request.user
            
            org.is_active = True
            org.suspension_reason = ''
            
            if template:
                # Usar template configurável
                template.apply_to_organization(org)
            else:
                # Fallback: valores hardcoded (compatibilidade)
                org.plan_type = 'premium'
                org.quota_pautas_dia = 10
                org.quota_posts_dia = 10
                org.quota_posts_mes = 60
            
            org.save()
            
            # ✅ Ativar todos os usuários da organização
            users_activated += org.users.filter(is_active=False).update(is_active=True)
            
            count += 1
        
        quota_info = f"({org.quota_pautas_dia}/{org.quota_posts_dia}/{org.quota_posts_mes})"
        self.message_user(
            request,
            f'{count} organização(ões) aprovada(s) como PREMIUM {quota_info}. {users_activated} usuário(s) ativado(s).',
            messages.SUCCESS
        )
    approve_as_premium.short_description = "✅ Aprovar como PREMIUM (10/10/60)"
    
    def suspend_for_payment(self, request, queryset):
        """💳 Suspender por pagamento atrasado"""
        count = 0
        for org in queryset:
            org.is_active = False
            org.suspension_reason = 'payment'
            org.internal_notes += f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] Suspensa por pagamento atrasado - {request.user.email}"
            org.save()
            count += 1
        
        self.message_user(
            request,
            f'{count} organização(ões) suspensa(s) por pagamento atrasado.',
            messages.WARNING
        )
    suspend_for_payment.short_description = "💳 Suspender por pagamento atrasado"
    
    def suspend_for_terms(self, request, queryset):
        """⚠️ Suspender por violação de termos"""
        count = 0
        for org in queryset:
            org.is_active = False
            org.suspension_reason = 'terms'
            org.internal_notes += f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] Suspensa por violação de termos - {request.user.email}"
            org.save()
            count += 1
        
        self.message_user(
            request,
            f'{count} organização(ões) suspensa(s) por violação de termos.',
            messages.WARNING
        )
    suspend_for_terms.short_description = "⚠️ Suspender por violação de termos"
    
    def suspend_canceled(self, request, queryset):
        """🚫 Marcar como cancelada pelo cliente"""
        count = 0
        for org in queryset:
            org.is_active = False
            org.suspension_reason = 'canceled'
            org.internal_notes += f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] Cancelada pelo cliente - {request.user.email}"
            org.save()
            count += 1
        
        self.message_user(
            request,
            f'{count} organização(ões) marcada(s) como canceladas.',
            messages.WARNING
        )
    suspend_canceled.short_description = "🚫 Marcar como cancelada"
    
    def reactivate_organizations(self, request, queryset):
        """✅ Reativar organizações"""
        count = 0
        for org in queryset.filter(is_active=False, approved_at__isnull=False):
            org.is_active = True
            org.suspension_reason = ''
            org.internal_notes += f"\n[{timezone.now().strftime('%d/%m/%Y %H:%M')}] Reativada - {request.user.email}"
            org.save()
            count += 1
        
        self.message_user(
            request,
            f'{count} organização(ões) reativada(s).',
            messages.SUCCESS
        )
    reactivate_organizations.short_description = "✅ Reativar organizações"


@admin.register(QuotaUsageDaily)
class QuotaUsageDailyAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'date', 'pautas_requested', 'posts_created',
        'cost_usd', 'get_total_items'
    ]
    list_filter = ['date', 'organization']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'
    
    def get_total_items(self, obj):
        return obj.pautas_used + obj.posts_used
    get_total_items.short_description = 'Total Usado'


@admin.register(QuotaAdjustment)
class QuotaAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'adjustment_type', 'resource_type',
        'amount', 'reason', 'created_at'
    ]
    list_filter = ['adjustment_type', 'resource_type', 'created_at']
    search_fields = ['organization__name', 'reason']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Ajuste', {
            'fields': ('organization', 'adjustment_type', 'resource_type', 'amount')
        }),
        ('Detalhes', {
            'fields': ('reason', 'reference_pauta', 'reference_post')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(QuotaAlert)
class QuotaAlertAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'alert_type', 'resource_type',
        'date', 'sent_to', 'created_at'
    ]
    list_filter = ['alert_type', 'resource_type', 'date']
    search_fields = ['organization__name', 'sent_to']
    readonly_fields = ['created_at']
    date_hierarchy = 'date'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
